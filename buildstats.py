"""Build figures for the profile page, read from the committed snapshot build_stats.py writes.

Production (Render) has only this repo, so it never measures: it reads data/build_stats.json.
Nothing here shells out to git. The snapshot is read from disk at most once per CACHE_SECONDS
(24h), so a page load costs a dict lookup.

Honesty rules, in order:
  - A snapshot that is missing, unreadable, malformed, or older than MAX_AGE_DAYS yields None,
    and the page renders its empty state. There is no fallback number.
  - A figure is shown with the date it was measured, so a floor is never read as "today".
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone

SNAPSHOT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "build_stats.json")
CACHE_SECONDS = 24 * 3600
# Past this, the snapshot stops being "the build as of now" and becomes history: show nothing.
MAX_AGE_DAYS = 30

_lock = threading.Lock()
_cache = {"stats": None, "loaded_at": None}


def _read(path: str) -> dict | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            snap = json.load(f)
        hours, lines = snap["commit_hours"], snap["tracked_lines"]
        generated = datetime.fromisoformat(snap["generated_at"])
    except (OSError, ValueError, KeyError, TypeError) as e:
        logging.warning("Build stats snapshot unreadable (%s): %s", path, e)
        return None
    if not (isinstance(hours, int) and isinstance(lines, int) and hours > 0 and lines > 0):
        logging.warning("Build stats snapshot holds no usable figures: %r / %r", hours, lines)
        return None
    if generated.tzinfo is None:
        generated = generated.replace(tzinfo=timezone.utc)
    return {"commit_hours": hours, "tracked_lines": lines, "generated_at": generated,
            "repo_count": len(snap.get("repos", {})), "unreachable": list(snap.get("unreachable", []))}


def load(path: str | None = None, now: float | None = None) -> dict | None:
    """Snapshot figures, or None when there is nothing honest to show."""
    now = time.time() if now is None else now
    with _lock:
        if _cache["loaded_at"] is None or now - _cache["loaded_at"] >= CACHE_SECONDS:
            _cache["stats"] = _read(path or SNAPSHOT_PATH)
            _cache["loaded_at"] = now
        stats = _cache["stats"]
    if stats is None:
        return None
    age_days = (now - stats["generated_at"].timestamp()) / 86400
    return None if age_days > MAX_AGE_DAYS else stats


def reset_cache() -> None:
    with _lock:
        _cache["stats"], _cache["loaded_at"] = None, None
