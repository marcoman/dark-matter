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


def _stable_seed(display_name: str) -> int:
    return int.from_bytes(hashlib.sha256(display_name.encode("utf-8")).digest()[:8], "big")


def ld_profile_for_display_name(display_name: str) -> dict[str, str | int]:
    """Stable pseudo-random traits for a display name (migration / offline tools only)."""
    r = random.Random(_stable_seed(display_name))
    org_team, org_team_size = r.choice(LD_ORG_TEAMS)
    return {
        "role": r.choice(LD_ROLES),
        "location": r.choice(LD_LOCATIONS),
        "org_team": org_team,
        "org_team_size": org_team_size,
    }


def build_multi_context(
    display_name: str,
    role: str,
    location: str,
    org_team: str,
    org_team_size: int,
) -> Context:
    user_ctx = (
        Context.builder(f"user-{display_name}")
        .name(display_name)
        .set("role", role)
        .set("location", location)
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
