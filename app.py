"""
Dark Matter - A simple Flask application with feature-flagged navigation.
Uses LaunchDarkly for MAM_ABOUT (about page) and MAM_BG_COLOR (background).
"""
import os
import platform
import sys

import psutil
from flask import Flask, redirect, render_template, request, session, url_for
from ldclient import Context, LDClient
from ldclient.config import Config

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dark-matter-dev-secret-change-in-production")

# LaunchDarkly client (lazy init)
_ld_client = None
# Track which contexts we've attached a BG color listener for
_bg_color_listener_context_keys: set[str] = set()


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


def get_ld_context(user_name: str) -> Context | None:
    return Context.builder(f"user-{user_name}").set("name", user_name).build() if user_name else None


def get_feature_flags(user_name: str) -> dict:
    flags = {"MAM_ABOUT": False, "MAM_BG_COLOR": "white"}
    client = get_ld_client()
    if not client or not client.is_initialized():
        return flags
    ctx = get_ld_context(user_name)
    if not ctx:
        return flags
    # Attach a flag-specific listener for MAM_BG_COLOR for this context once
    try:
        if ctx.key not in _bg_color_listener_context_keys:
            def _on_bg_color_change(change):
                # change has .key, .old_value, .new_value
                print(
                    f"[LaunchDarkly] MAM_BG_COLOR changed for {ctx.key}: "
                    f"{change.old_value!r} -> {change.new_value!r}",
                    flush=True,
                )

            client.flag_tracker.add_flag_value_change_listener("MAM_BG_COLOR", ctx, _on_bg_color_change)
            _bg_color_listener_context_keys.add(ctx.key)
    except Exception:
        # Listener attachment failure should not break the app; continue with defaults/eval
        pass
    try:
        flags["MAM_ABOUT"] = client.variation("MAM_ABOUT", ctx, False)
        flags["MAM_BG_COLOR"] = client.variation("MAM_BG_COLOR", ctx, "white") or "white"
    except Exception:
        pass
    return flags


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
        return redirect(url_for("upper_left"))
    if session.get("name"):
        return redirect(url_for("upper_left"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/upper-left")
@require_login
def upper_left():
    from_page = session.get("from_page")
    session["from_page"] = "upper-left"
    flags = get_feature_flags(session["name"])
    return render_template(
        "upper_left.html",
        name=session["name"],
        from_page=from_page,
        show_about=flags["MAM_ABOUT"],
        bg_color=flags["MAM_BG_COLOR"],
    )


@app.route("/upper-right")
@require_login
def upper_right():
    from_page = session.get("from_page")
    session["from_page"] = "upper-right"
    flags = get_feature_flags(session["name"])
    return render_template(
        "upper_right.html",
        name=session["name"],
        from_page=from_page,
        show_about=flags["MAM_ABOUT"],
        bg_color=flags["MAM_BG_COLOR"],
    )


@app.route("/lower-left")
@require_login
def lower_left():
    from_page = session.get("from_page")
    session["from_page"] = "lower-left"
    flags = get_feature_flags(session["name"])
    return render_template(
        "lower_left.html",
        name=session["name"],
        from_page=from_page,
        show_about=flags["MAM_ABOUT"],
        bg_color=flags["MAM_BG_COLOR"],
    )


@app.route("/lower-right")
@require_login
def lower_right():
    from_page = session.get("from_page")
    session["from_page"] = "lower-right"
    flags = get_feature_flags(session["name"])
    return render_template(
        "lower_right.html",
        name=session["name"],
        from_page=from_page,
        show_about=flags["MAM_ABOUT"],
        bg_color=flags["MAM_BG_COLOR"],
    )


@app.route("/about")
@require_login
def about():
    flags = get_feature_flags(session["name"])
    if not flags["MAM_ABOUT"]:
        return redirect(url_for("upper_left"))
    sys_info = {
        "python_version": sys.version,
        "os": platform.system(),
        "os_release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor() or "N/A",
        "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
        "memory_available_gb": round(psutil.virtual_memory().available / (1024**3), 2),
        "cpu_count": psutil.cpu_count(),
    }
    libraries = ["flask", "launchdarkly-server-sdk", "psutil"]
    return render_template(
        "about.html",
        name=session["name"],
        sys_info=sys_info,
        libraries=libraries,
        author="Marco",
        bg_color=flags["MAM_BG_COLOR"],
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=os.environ.get("FLASK_DEBUG", "0") == "1")
