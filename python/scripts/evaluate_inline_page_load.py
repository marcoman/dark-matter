#!/usr/bin/env python3
"""
Measure first-page load after login for user1..user300 and record MAM_INLINE_ABOUT.

The app evaluates flags with a LaunchDarkly multi-context (user + organization). After each
login this script calls GET /api/ld-flags with the same session cookie so the CSV matches
the server's evaluation.

Environment:
  DARK_MATTER_BASE_URL   Optional, default http://127.0.0.1:5000

Output CSV (repo root): inline_time_YYYYMMDD_HHMMSS.csv
Columns: username, start_time, end_time, page_load_time_us, mam_inline_about

Usage (from the python/ directory, with app running):
  python scripts/evaluate_inline_page_load.py
"""

from __future__ import annotations

import argparse
import csv
import os
import time
from datetime import datetime
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_BASE = "http://127.0.0.1:5000"
USER_COUNT = 300


def measure_one_user(
    base_url: str,
    username: str,
    session: requests.Session,
    timeout: float,
) -> tuple[datetime, datetime, int, int]:
    """
    POST / login, follow redirects to first nav page. Returns (start, end, load_us, http_status).
    load_us is total time for the login POST + redirect chain in microseconds.
    """
    url = base_url.rstrip("/") + "/"
    start = datetime.now()
    t0 = time.perf_counter_ns()
    try:
        r = session.post(
            url,
            data={"name": username},
            allow_redirects=True,
            timeout=timeout,
        )
        t1 = time.perf_counter_ns()
        end = datetime.now()
        load_us = (t1 - t0) // 1000
        return start, end, load_us, r.status_code
    except requests.RequestException:
        t1 = time.perf_counter_ns()
        end = datetime.now()
        load_us = (t1 - t0) // 1000
        return start, end, load_us, 0


def report_inline_about_load(
    base_url: str,
    session: requests.Session,
    load_us: int,
    timeout: float,
) -> int:
    """
    POST measured load time to app API so server can emit LD `inline_about`.
    Returns API status code (0 if request failed).
    """
    url = base_url.rstrip("/") + "/api/inline-about-load"
    try:
        r = session.post(
            url,
            json={"load_ms": load_us / 1000.0},  # API expects milliseconds
            timeout=timeout,
        )
        return r.status_code
    except requests.RequestException:
        return 0


def fetch_mam_inline_about(base_url: str, session: requests.Session, timeout: float) -> bool:
    """Read MAM_INLINE_ABOUT from the app after login (same LD multi-context as pages)."""
    url = base_url.rstrip("/") + "/api/ld-flags"
    try:
        r = session.get(url, timeout=timeout)
        if r.status_code != 200:
            return False
        data = r.json()
        return bool(data.get("MAM_INLINE_ABOUT"))
    except (requests.RequestException, ValueError, TypeError):
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate first-page load per user and MAM_INLINE_ABOUT.")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("DARK_MATTER_BASE_URL", DEFAULT_BASE),
        help=f"Flask app base URL (default: {DEFAULT_BASE})",
    )
    parser.add_argument(
        "--users",
        type=int,
        default=USER_COUNT,
        help=f"Number of users user1..userN (default: {USER_COUNT})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT,
        help="Directory for CSV (default: repository root)",
    )
    parser.add_argument("--timeout", type=float, default=60.0, help="HTTP timeout seconds")
    args = parser.parse_args()

    test_start = datetime.now()
    stamp = test_start.strftime("%Y%m%d_%H%M%S")
    out_path = args.output_dir / f"inline_time_{stamp}.csv"
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Test start: {test_start.isoformat()}")
    print(f"Output: {out_path}")
    print(f"Base URL: {args.base_url}")

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "username",
                "start_time",
                "end_time",
                "page_load_time_us",
                "mam_inline_about",
            ]
        )
        for i in range(1, args.users + 1):
            username = f"user{i}"
            sess = requests.Session()
            sess.headers.setdefault("User-Agent", "dark-matter-evaluate-inline-page-load/1.0")
            start, end, load_us, status = measure_one_user(
                args.base_url, username, sess, args.timeout
            )
            mam_inline = False
            metric_status = 0
            if status == 200:
                mam_inline = fetch_mam_inline_about(args.base_url, sess, args.timeout)
                metric_status = report_inline_about_load(
                    args.base_url, sess, load_us, args.timeout
                )
            w.writerow(
                [
                    username,
                    start.isoformat(),
                    end.isoformat(),
                    load_us,
                    "true" if mam_inline else "false",
                ]
            )
            f.flush()
            if i % 50 == 0 or i == 1:
                print(
                    f"  ... {username} status={status} metric_status={metric_status} "
                    f"load_us={load_us} mam_inline_about={mam_inline}"
                )

    print(f"Done. Wrote {args.users} rows to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
