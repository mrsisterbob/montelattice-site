"""Build figures for the profile page, read from the snapshot build_stats.py writes.

Production (Render) has only this repo, so it never measures. It reads two snapshots and keeps
the one with the later generated_at: the committed data/build_stats.json, and the one the
scheduled workflow publishes on the build-stats branch (SNAPSHOT_URL). Nothing here shells out
to git. Both are read at most once per CACHE_SECONDS (24h, a failed fetch included), so a page
load costs a dict lookup.

Honesty rules, in order:
  - A snapshot that is missing, unreadable, malformed, or older than MAX_AGE_DAYS yields None,
    and the page renders its empty state. There is no fallback number. A remote that cannot be
    reached or fails these rules is ignored, and the committed file stands.
  - A figure is shown with the date it was measured, so a floor is never read as "today".
"""
from __future__ import annotations

import http.client
import json
import logging
import os
import threading
import time
import urllib.request
from datetime import datetime, timedelta, timezone

SNAPSHOT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "build_stats.json")
# Published daily by .github/workflows/build-stats.yml. Empty means "no remote" (tests set it so).
SNAPSHOT_URL = "https://raw.githubusercontent.com/mrsisterbob/montelattice-site/build-stats/build_stats.json"
_FETCH_TIMEOUT_SECONDS = 5
_MAX_BYTES = 64 * 1024  # a snapshot is under 1 KB; refuse anything near this
CACHE_SECONDS = 24 * 3600
# Past this, the snapshot stops being "the build as of now" and becomes history: show nothing.
MAX_AGE_DAYS = 30

_lock = threading.Lock()
_cache = {"stats": None, "loaded_at": None}


def _parse(snap: dict) -> dict | None:
    """The one validity rule for a snapshot, whichever source it came from."""
    try:
        hours, lines = snap["commit_hours"], snap["tracked_lines"]
        generated = datetime.fromisoformat(snap["generated_at"])
    except (ValueError, KeyError, TypeError) as e:
        logging.warning("Build stats snapshot unreadable: %s", e)
        return None
    if not all(type(v) is int and v > 0 for v in (hours, lines)):
        logging.warning("Build stats snapshot holds no usable figures: %r / %r", hours, lines)
        return None
    if generated.tzinfo is None:
        generated = generated.replace(tzinfo=timezone.utc)
    if generated > datetime.now(timezone.utc) + timedelta(days=1):
        logging.warning("Build stats snapshot is dated in the future: %s", generated)
        return None
    return {"commit_hours": hours, "tracked_lines": lines, "generated_at": generated,
            "repo_count": len(snap.get("repos", {})), "unreachable": list(snap.get("unreachable", []))}


def _read(path: str) -> dict | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return _parse(json.load(f))
    except (OSError, ValueError) as e:
        logging.warning("Build stats snapshot unreadable (%s): %s", path, e)
        return None


def _fetch() -> dict | None:
    if not SNAPSHOT_URL:
        return None
    try:
        with urllib.request.urlopen(SNAPSHOT_URL, timeout=_FETCH_TIMEOUT_SECONDS) as resp:
            return _parse(json.loads(resp.read(_MAX_BYTES).decode("utf-8")))
    except (OSError, ValueError, http.client.HTTPException) as e:
        logging.warning("Build stats remote snapshot unavailable (%s): %s", SNAPSHOT_URL, e)
        return None


def _newest(*snaps: dict | None) -> dict | None:
    valid = [s for s in snaps if s is not None]
    return max(valid, key=lambda s: s["generated_at"]) if valid else None


def load(path: str | None = None, now: float | None = None) -> dict | None:
    """Snapshot figures, or None when there is nothing honest to show."""
    now = time.time() if now is None else now
    with _lock:
        due = _cache["loaded_at"] is None or now - _cache["loaded_at"] >= CACHE_SECONDS
    if due:
        # Outside the lock: a slow fetch must not hold up every other request behind it.
        fresh = _newest(_read(path or SNAPSHOT_PATH), _fetch())
        with _lock:
            _cache["stats"], _cache["loaded_at"] = fresh, now
    with _lock:
        stats = _cache["stats"]
    if stats is None:
        return None
    age_days = (now - stats["generated_at"].timestamp()) / 86400
    return None if age_days > MAX_AGE_DAYS else stats


def reset_cache() -> None:
    with _lock:
        _cache["stats"], _cache["loaded_at"] = None, None
