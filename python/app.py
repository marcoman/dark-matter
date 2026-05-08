"""
Dark Matter - A simple Flask application with feature-flagged navigation.
Uses LaunchDarkly for feature flags (about, banner color, inline about, etc.).
Written by Marco, 2026.

"""
from __future__ import annotations

import json
import os
import platform
import random
import sys

import psutil
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from ldclient import Context, LDClient
from ldclient.config import Config
from ldclient.evaluation import EvaluationDetail

from ld_context_builder import (
    LD_FAVORITE_COLOR_CODES,
    LD_FAVORITE_COLORS,
    LD_LOCATIONS,
    LD_ORG_TEAMS,
    LD_ROLES,
    build_multi_context,
    ld_profile_for_display_name,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dark-matter-dev-secret-change-in-production")

_AUTHOR = "Marco"
_LIBRARIES = ["flask", "launchdarkly-server-sdk", "psutil"]


def _build_sys_info() -> dict:
    return {
        "python_version": sys.version,
        "os": platform.system(),
        "os_release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor() or "N/A",
        "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
        "memory_available_gb": round(psutil.virtual_memory().available / (1024**3), 2),
        "cpu_count": psutil.cpu_count(),
    }


def get_about_inline_context() -> dict:
    """Shared About content for /about and inline block on nav pages."""
    return {
        "sys_info": _build_sys_info(),
        "libraries": _LIBRARIES,
        "author": _AUTHOR,
    }

# LaunchDarkly client (lazy init)
_ld_client = None
# Track which contexts we've attached a BG color listener for
_bg_color_listener_context_keys: set[str] = set()

# Session `from_page` slug -> valid direction -> (Flask endpoint name, target slug for metrics)
_NAV_TRANSITIONS: dict[str, dict[str, tuple[str, str]]] = {
    "upper-left": {
        "right": ("upper_right", "upper-right"),
        "down": ("lower_left", "lower-left"),
    },
    "upper-right": {
        "left": ("upper_left", "upper-left"),
        "down": ("lower_right", "lower-right"),
    },
    "lower-left": {
        "right": ("lower_right", "lower-right"),
        "up": ("upper_left", "upper-left"),
    },
    "lower-right": {
        "up": ("upper_right", "upper-right"),
        "left": ("lower_left", "lower-left"),
    },
}
_VALID_NAV_DIRECTIONS = frozenset({"up", "down", "left", "right"})

_DEFAULT_MAM_BUTTON_TEXT: dict[str, str] = {
    "down": "Down",
    "left": "Left",
    "right": "Right",
    "up": "Up",
}


def _normalize_mam_button_text(raw: object) -> dict[str, str]:
    """Parse MAM_BUTTON_TEXT JSON flag; merge with English defaults for missing keys."""
    data: object = raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = None
    if not isinstance(data, dict):
        return dict(_DEFAULT_MAM_BUTTON_TEXT)
    out = dict(_DEFAULT_MAM_BUTTON_TEXT)
    for key in _DEFAULT_MAM_BUTTON_TEXT:
        val = data.get(key)
        if val is not None and str(val).strip() != "":
            out[key] = str(val)
    return out


_LD_FLAG_ORDER: tuple[str, ...] = (
    "MAM_ABOUT",
    "MAM_BG_COLOR",
    "MAM_TOGGLE_CASE",
    "MAM_DARK_MODE",
    "MAM_INLINE_ABOUT",
    "MAM_ABOUT_SIZE",
    "MAM_BUTTON_TEXT",
)


def _ld_eval_default(flag_key: str) -> object:
    if flag_key == "MAM_ABOUT":
        return False
    if flag_key == "MAM_BG_COLOR":
        return "white"
    if flag_key in ("MAM_TOGGLE_CASE", "MAM_DARK_MODE", "MAM_INLINE_ABOUT"):
        return False
    if flag_key == "MAM_ABOUT_SIZE":
        return 1
    if flag_key == "MAM_BUTTON_TEXT":
        return dict(_DEFAULT_MAM_BUTTON_TEXT)
    raise KeyError(flag_key)


def _ld_flag_eval_report_enabled() -> bool:
    return os.environ.get("LD_FLAG_EVAL_REPORT", "1").lower() not in ("0", "false", "no")


def _ld_flag_eval_colors_enabled() -> bool:
    if os.environ.get("NO_COLOR", "").strip():
        return False
    return sys.stderr.isatty()


def _ld_reason_color(kind: object, colors: bool) -> str:
    if not colors:
        return ""
    k = str(kind or "").upper()
    return {
        "OFF": "\033[90m",
        "FALLTHROUGH": "\033[36m",
        "TARGET_MATCH": "\033[32m",
        "RULE_MATCH": "\033[32m",
        "SEGMENT_MATCH": "\033[32m",
        "PREREQUISITE_FAILED": "\033[31m",
        "ERROR": "\033[31m",
    }.get(k, "\033[33m")


def _log_ld_variation_detail(flag_key: str, detail: EvaluationDetail) -> None:
    """Print flag name, served value, and evaluation reason (ANSI colors when stderr is a TTY)."""
    colors = _ld_flag_eval_colors_enabled()
    reset = "\033[0m" if colors else ""
    bold = "\033[1m" if colors else ""
    c_flag = f"{bold}\033[96m" if colors else ""
    c_var = f"{bold}\033[92m" if colors else ""
    reason_obj = detail.reason
    reason_dict = reason_obj if isinstance(reason_obj, dict) else {"_non_dict_reason": repr(reason_obj)}
    kind = reason_dict.get("kind")
    c_reason = _ld_reason_color(kind, colors)
    val = detail.value
    if isinstance(val, (dict, list)):
        val_s = json.dumps(val, ensure_ascii=False)
    else:
        val_s = repr(val)
    reason_s = json.dumps(reason_dict, ensure_ascii=False, sort_keys=True)
    idx = detail.variation_index
    default_note = ""
    try:
        if detail.is_default_value():
            default_note = " default_value=True"
    except Exception:
        pass
    line = (
        f"{c_flag}flag={flag_key}{reset}  "
        f"{c_var}variation_index={idx} value={val_s}{default_note}{reset}  "
        f"{c_reason}reason={reason_s}{reset}"
    )
    print(line, file=sys.stderr, flush=True)


def get_ld_client():
    global _ld_client
    if _ld_client is None:
        sdk_key = os.environ.get("LAUNCHDARKLY_SDK_KEY")
        if sdk_key:
            config = Config(sdk_key=sdk_key)
            # Wait up to 15s for initial connection so variation() doesn't run before init
            client = LDClient(config=config, start_wait=15)
            if not client.is_initialized():
                # Invalid key (e.g. 401), network failure, etc. Close and disable so we
                # don't keep retrying and spamming "invalid SDK key" errors.
                client.close()
                _ld_client = False
            else:
                _ld_client = client
        else:
            _ld_client = False  # disabled
    return _ld_client if _ld_client else None


def get_ld_context(user_name: str | None = None) -> Context | None:
    """LaunchDarkly multi-context (user + organization) from the logged-in session."""
    name = session.get("name")
    if not name:
        return None
    if user_name is not None and user_name != name:
        return None
    if "test" in name.lower():
        return Context.builder(f"anon-{name}").name(name).anonymous(True).build()
    if session.get("ld_role") is None or session.get("ld_favorite_color") is None:
        prof = ld_profile_for_display_name(name)
        session["ld_role"] = prof["role"]
        session["ld_location"] = prof["location"]
        session["ld_org_team"] = prof["org_team"]
        session["ld_org_team_size"] = prof["org_team_size"]
        session["ld_favorite_color"] = prof["favorite_color"]
        session["ld_favorite_color_code"] = prof["favorite_color_code"]
    return build_multi_context(
        display_name=name,
        role=str(session["ld_role"]),
        location=str(session["ld_location"]),
        org_team=str(session["ld_org_team"]),
        org_team_size=int(session["ld_org_team_size"]),
        favorite_color=str(session["ld_favorite_color"]),
        favorite_color_code=str(session["ld_favorite_color_code"]),
    )


def get_feature_flags(user_name: str) -> dict:
    flags = {
        "MAM_ABOUT": False,
        "MAM_BG_COLOR": "white",
        "MAM_TOGGLE_CASE": False,
        "MAM_DARK_MODE": False,
        "MAM_INLINE_ABOUT": False,
        "MAM_ABOUT_SIZE": 1,
        "MAM_BUTTON_TEXT": dict(_DEFAULT_MAM_BUTTON_TEXT),
    }
    client = get_ld_client()
    if not client or not client.is_initialized():
        return flags
    ctx = get_ld_context(user_name)
    if not ctx:
        return flags
    # Attach a flag-specific listener for MAM_BG_COLOR for this context once
    try:
        fq = ctx.fully_qualified_key
        if fq not in _bg_color_listener_context_keys:
            def _on_bg_color_change(change):
                # change has .key, .old_value, .new_value
                print(
                    f"[LaunchDarkly] MAM_BG_COLOR changed for {fq}: "
                    f"{change.old_value!r} -> {change.new_value!r}",
                    flush=True,
                )

            client.flag_tracker.add_flag_value_change_listener("MAM_BG_COLOR", ctx, _on_bg_color_change)
            _bg_color_listener_context_keys.add(fq)
    except Exception:
        # Listener attachment failure should not break the app; continue with defaults/eval
        pass
    try:
        if _ld_flag_eval_report_enabled():
            hdr = f"[LaunchDarkly evaluation] context={ctx.fully_qualified_key}"
            if _ld_flag_eval_colors_enabled():
                hdr = f"\033[1;35m{hdr}\033[0m"
            print(hdr, file=sys.stderr, flush=True)
        for fk in _LD_FLAG_ORDER:
            try:
                detail = client.variation_detail(fk, ctx, _ld_eval_default(fk))
                if _ld_flag_eval_report_enabled():
                    _log_ld_variation_detail(fk, detail)
                flags[fk] = detail.value
            except Exception:
                continue
        flags["MAM_BG_COLOR"] = flags.get("MAM_BG_COLOR") or "white"
        try:
            flags["MAM_ABOUT_SIZE"] = int(flags.get("MAM_ABOUT_SIZE", 1))
        except (TypeError, ValueError):
            flags["MAM_ABOUT_SIZE"] = 1
        flags["MAM_BUTTON_TEXT"] = _normalize_mam_button_text(flags.get("MAM_BUTTON_TEXT"))
    except Exception:
        pass
    return flags


def track_inline_about_load(user_name: str, load_ms: float, mam_inline_about: bool) -> None:
    """Custom metric `inline_about`: page load time (ms) with flag on/off for experiments."""
    client = get_ld_client()
    if not client or not client.is_initialized():
        return
    ctx = get_ld_context(user_name)
    if not ctx:
        return
    try:
        print(f"Tracking inline_about for {user_name} with load_ms: {load_ms} and mam_inline_about: {mam_inline_about}")
        client.track(
            "inline_about",
            ctx,
            data={"mam_inline_about": mam_inline_about, "load_ms": round(load_ms, 2)},
            metric_value=load_ms,
        )
    except Exception:
        pass


def track_ui_color_mode(user_name: str, mode: str) -> None:
    """LaunchDarkly custom event for nav area color mode (metric key: ui_color_mode)."""
    if mode not in ("light", "dark"):
        return
    client = get_ld_client()
    if not client or not client.is_initialized():
        return
    ctx = get_ld_context(user_name)
    if not ctx:
        return
    try:
        client.track("ui_color_mode", ctx, data={"mode": mode})
    except Exception:
        pass


def report_ui_color_mode_when_flag_off(user_name: str, flags: dict) -> None:
    """When MAM_DARK_MODE is off, effective mode is always light; report once per login session."""
    if flags.get("MAM_DARK_MODE"):
        return
    if session.get("_ld_ui_color_mode_metric_sent"):
        return
    track_ui_color_mode(user_name, "light")
    session["_ld_ui_color_mode_metric_sent"] = True


def track_nav_click(user_name: str, direction: str, from_slug: str, to_slug: str) -> None:
    """Send a LaunchDarkly custom event for compass navigation (custom metrics in LD)."""
    client = get_ld_client()
    if not client or not client.is_initialized():
        return
    ctx = get_ld_context(user_name)
    if not ctx:
        return
    try:
        client.track(
            f"nav_click_{direction}",
            ctx,
            data={
                "from_page": from_slug,
                "to_page": to_slug,
            },
        )
    except Exception:
        pass


def track_nav_case_toggle(user_name: str, previous_case: str, new_case: str) -> None:
    """LaunchDarkly custom event when the switch-case button is used (separate from nav_click_*)."""
    client = get_ld_client()
    if not client or not client.is_initialized():
        return
    ctx = get_ld_context(user_name)
    if not ctx:
        return
    try:
        client.track(
            "nav_case_toggle_clicked",
            ctx,
            data={
                "previous_case": previous_case,
                "new_case": new_case,
                "from_page": session.get("from_page"),
            },
        )
    except Exception:
        pass


def require_login(f):
    """Redirect to login if no session name."""
    from functools import wraps

    @wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get("name"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return wrapped


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            return render_template("login.html", error="Please enter your name.")
        session["name"] = name
        session["from_page"] = None
        session["nav_case"] = "lower"
        session.pop("_ld_ui_color_mode_metric_sent", None)
        if "test" not in name.lower():
            org_team, org_team_size = random.choice(LD_ORG_TEAMS)
            favorite_color = random.choice(LD_FAVORITE_COLORS)
            session["ld_role"] = random.choice(LD_ROLES)
            session["ld_location"] = random.choice(LD_LOCATIONS)
            session["ld_org_team"] = org_team
            session["ld_org_team_size"] = org_team_size
            session["ld_favorite_color"] = favorite_color
            session["ld_favorite_color_code"] = LD_FAVORITE_COLOR_CODES[favorite_color]
        else:
            session.pop("ld_role", None)
            session.pop("ld_location", None)
            session.pop("ld_org_team", None)
            session.pop("ld_org_team_size", None)
            session.pop("ld_favorite_color", None)
            session.pop("ld_favorite_color_code", None)
        return redirect(url_for("upper_left"))
    if session.get("name"):
        return redirect(url_for("upper_left"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/toggle-nav-case", methods=["POST"])
@require_login
def toggle_nav_case():
    flags = get_feature_flags(session["name"])
    if flags["MAM_TOGGLE_CASE"]:
        current = session.get("nav_case", "lower")
        new_case = "upper" if current == "lower" else "lower"
        track_nav_case_toggle(session["name"], current, new_case)
        session["nav_case"] = new_case
    next_page = request.form.get("next_page")
    if next_page:
        return redirect(next_page)
    return redirect(url_for("upper_left"))


@app.route("/api/ld-flags", methods=["GET"])
@require_login
def api_ld_flags():
    """Current LaunchDarkly flag snapshot for the logged-in session (multi-context)."""
    return jsonify(get_feature_flags(session["name"]))


@app.route("/api/ui-color-mode", methods=["POST"])
@require_login
def api_ui_color_mode():
    """Browser reports light/dark when MAM_DARK_MODE is enabled (custom metric ui_color_mode)."""
    flags = get_feature_flags(session["name"])
    if not flags.get("MAM_DARK_MODE"):
        return jsonify({"ok": True, "ignored": True})
    payload = request.get_json(silent=True) or {}
    mode = (payload.get("mode") or "").lower()
    if mode not in ("light", "dark"):
        return jsonify({"error": "mode must be light or dark"}), 400
    track_ui_color_mode(session["name"], mode)
    return jsonify({"ok": True})


@app.route("/api/inline-about-load", methods=["POST"])
@require_login
def api_inline_about_load():
    """Browser-reported navigation timing for `inline_about` metric (compare with/without MAM_INLINE_ABOUT)."""
    flags = get_feature_flags(session["name"])
    payload = request.get_json(silent=True) or {}
    raw = payload.get("load_ms")
    print(f"load_ms: {raw}")
    try:
        load_ms = float(raw)
    except (TypeError, ValueError):
        return jsonify({"error": "invalid load_ms"}), 400
    if load_ms < 0 or load_ms > 600000:
        return jsonify({"error": "load_ms out of range"}), 400
    track_inline_about_load(session["name"], load_ms, bool(flags.get("MAM_INLINE_ABOUT")))
    return jsonify({"ok": True})


@app.route("/nav/go/<direction>")
@require_login
def nav_go(direction: str):
    """Compass clicks: validate move, track LaunchDarkly event, redirect to destination."""
    d = (direction or "").lower()
    if d not in _VALID_NAV_DIRECTIONS:
        return redirect(url_for("upper_left"))

    current = session.get("from_page")
    if current not in _NAV_TRANSITIONS:
        current = "upper-left"

    edges = _NAV_TRANSITIONS.get(current) or {}
    if d not in edges:
        return redirect(url_for("upper_left"))

    endpoint, to_slug = edges[d]
    track_nav_click(session["name"], d, current, to_slug)
    return redirect(url_for(endpoint))


@app.route("/upper-left")
@require_login
def upper_left():
    from_page = session.get("from_page")
    session["from_page"] = "upper-left"
    flags = get_feature_flags(session["name"])
    report_ui_color_mode_when_flag_off(session["name"], flags)
    extras = {"show_inline_about": flags["MAM_INLINE_ABOUT"]}
    if flags["MAM_INLINE_ABOUT"]:
        extras.update(get_about_inline_context())
    return render_template(
        "upper_left.html",
        name=session["name"],
        from_page=from_page,
        show_about=flags["MAM_ABOUT"],
        bg_color=flags["MAM_BG_COLOR"],
        show_toggle_case=flags["MAM_TOGGLE_CASE"],
        show_dark_mode_toggle=flags["MAM_DARK_MODE"],
        nav_case_upper=session.get("nav_case", "lower") == "upper",
        button_text=flags["MAM_BUTTON_TEXT"],
        **extras,
    )


@app.route("/upper-right")
@require_login
def upper_right():
    from_page = session.get("from_page")
    session["from_page"] = "upper-right"
    flags = get_feature_flags(session["name"])
    report_ui_color_mode_when_flag_off(session["name"], flags)
    ctx = {"show_inline_about": flags["MAM_INLINE_ABOUT"]}
    if flags["MAM_INLINE_ABOUT"]:
        ctx.update(get_about_inline_context())
    return render_template(
        "upper_right.html",
        name=session["name"],
        from_page=from_page,
        show_about=flags["MAM_ABOUT"],
        bg_color=flags["MAM_BG_COLOR"],
        show_toggle_case=flags["MAM_TOGGLE_CASE"],
        show_dark_mode_toggle=flags["MAM_DARK_MODE"],
        nav_case_upper=session.get("nav_case", "lower") == "upper",
        button_text=flags["MAM_BUTTON_TEXT"],
        **ctx,
    )


@app.route("/lower-left")
@require_login
def lower_left():
    from_page = session.get("from_page")
    session["from_page"] = "lower-left"
    flags = get_feature_flags(session["name"])
    report_ui_color_mode_when_flag_off(session["name"], flags)
    ctx = {"show_inline_about": flags["MAM_INLINE_ABOUT"]}
    if flags["MAM_INLINE_ABOUT"]:
        ctx.update(get_about_inline_context())
    return render_template(
        "lower_left.html",
        name=session["name"],
        from_page=from_page,
        show_about=flags["MAM_ABOUT"],
        bg_color=flags["MAM_BG_COLOR"],
        show_toggle_case=flags["MAM_TOGGLE_CASE"],
        show_dark_mode_toggle=flags["MAM_DARK_MODE"],
        nav_case_upper=session.get("nav_case", "lower") == "upper",
        button_text=flags["MAM_BUTTON_TEXT"],
        **ctx,
    )


@app.route("/lower-right")
@require_login
def lower_right():
    from_page = session.get("from_page")
    session["from_page"] = "lower-right"
    flags = get_feature_flags(session["name"])
    report_ui_color_mode_when_flag_off(session["name"], flags)
    ctx = {"show_inline_about": flags["MAM_INLINE_ABOUT"]}
    if flags["MAM_INLINE_ABOUT"]:
        ctx.update(get_about_inline_context())
    return render_template(
        "lower_right.html",
        name=session["name"],
        from_page=from_page,
        show_about=flags["MAM_ABOUT"],
        bg_color=flags["MAM_BG_COLOR"],
        show_toggle_case=flags["MAM_TOGGLE_CASE"],
        show_dark_mode_toggle=flags["MAM_DARK_MODE"],
        nav_case_upper=session.get("nav_case", "lower") == "upper",
        button_text=flags["MAM_BUTTON_TEXT"],
        **ctx,
    )


@app.route("/about")
@require_login
def about():
    flags = get_feature_flags(session["name"])
    if not flags["MAM_ABOUT"]:
        return redirect(url_for("upper_left"))
    about_ctx = get_about_inline_context()
    about_size = flags.get("MAM_ABOUT_SIZE", 1)
    if isinstance(about_size, bool):
        about_size = 1
    try:
        about_size_int = int(about_size)
    except (TypeError, ValueError):
        about_size_int = 1
    if about_size_int <= 1:
        about_size_class = "about-text--small"
    elif about_size_int <= 10:
        about_size_class = "about-text--medium"
    else:
        about_size_class = "about-text--large"
    report_ui_color_mode_when_flag_off(session["name"], flags)
    return render_template(
        "about.html",
        name=session["name"],
        bg_color=flags["MAM_BG_COLOR"],
        show_about=True,
        show_toggle_case=flags["MAM_TOGGLE_CASE"],
        show_dark_mode_toggle=flags["MAM_DARK_MODE"],
        show_inline_about=False,
        record_inline_load_metric=False,
        nav_case_upper=session.get("nav_case", "lower") == "upper",
        about_size=about_size_int,
        about_size_class=about_size_class,
        **about_ctx,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=os.environ.get("FLASK_DEBUG", "0") == "1")
