"""
LaunchDarkly multi-context: user + organization.

User attributes: name, role (developer | tester | user), location (PHL | ORD | SFO | ATL).
Organization attributes: team (HR | OPS | Sales | Finance), team_size (5 | 10 | 15 | 20).

On each login the app picks role, location, and organization uniformly at random and
stores them in the session. ``ld_profile_for_display_name`` is only for migrating old
sessions missing LD keys and for tests/tools that need a deterministic profile from a name.
"""
from __future__ import annotations

import hashlib
import random

from ldclient import Context

LD_ROLES: tuple[str, ...] = ("developer", "tester", "user")
LD_LOCATIONS: tuple[str, ...] = ("PHL", "ORD", "SFO", "ATL")
LD_ORG_TEAMS: tuple[tuple[str, int], ...] = (
    ("HR", 5),
    ("OPS", 10),
    ("Sales", 15),
    ("Finance", 20),
)
LD_FAVORITE_COLORS: tuple[str, ...] = (
    "Red",
    "Orange",
    "Yellow",
    "Green",
    "Blue",
    "Indigo",
    "Violet",
)
LD_FAVORITE_COLOR_CODES: dict[str, str] = {
    "Red": "#FF0000",
    "Orange": "#FFA500",
    "Yellow": "#FFFF00",
    "Green": "#008000",
    "Blue": "#0000FF",
    "Indigo": "#4B0082",
    "Violet": "#EE82EE",
}


def _stable_seed(display_name: str) -> int:
    return int.from_bytes(hashlib.sha256(display_name.encode("utf-8")).digest()[:8], "big")


def ld_profile_for_display_name(display_name: str) -> dict[str, str | int]:
    """Stable pseudo-random traits for a display name (migration / offline tools only)."""
    r = random.Random(_stable_seed(display_name))
    org_team, org_team_size = r.choice(LD_ORG_TEAMS)
    favorite_color = r.choice(LD_FAVORITE_COLORS)
    return {
        "role": r.choice(LD_ROLES),
        "location": r.choice(LD_LOCATIONS),
        "org_team": org_team,
        "org_team_size": org_team_size,
        "favorite_color": favorite_color,
        "favorite_color_code": LD_FAVORITE_COLOR_CODES[favorite_color],
    }


def build_multi_context(
    display_name: str,
    role: str,
    location: str,
    org_team: str,
    org_team_size: int,
    favorite_color: str,
    favorite_color_code: str,
) -> Context:
    user_ctx = (
        Context.builder(f"user-{display_name}")
        .name(display_name)
        .set("role", role)
        .set("location", location)
        .set("favorite_color", favorite_color)
        .set("favorite_color_code", favorite_color_code)
        .private("favorite_color", "favorite_color_code")
        .build()
    )
    org_ctx = (
        Context.builder(f"org-{org_team}")
        .kind("organization")
        .set("team", org_team)
        .set("team_size", org_team_size)
        .build()
    )
    return Context.create_multi(user_ctx, org_ctx)
