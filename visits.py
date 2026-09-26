"""Pageview forwarding for private visitor analytics.

This service has no persistent disk, so it keeps no log. A before_request hook hands each real
pageview to capture(), which only puts a small dict on a bounded in-memory queue - it never
touches the network, so it cannot slow a page down. A daemon thread posts batches to the job
engine's /analytics/ingest, where the visit is classified, the IP is hashed under a daily salt
held only in memory, and only (time, path, hashed id, referrer host, bot flag) is stored.

The IP and user agent therefore exist here only in memory, in transit over HTTPS, and in the
engine's memory. Nothing is written to disk on either side, no cookie is set, and no third-party
script is involved. Kevin's own signed-in Console session is flagged so it is not counted.

Env: ANALYTICS_ENABLED (default true), ANALYTICS_INGEST_TOKEN (shared with the engine; without
it nothing is sent), JOB_ENGINE_PUBLIC_URL (shared with jobstats.py).
"""
from __future__ import annotations

import json
import logging
import os
import queue
import threading
import time
import urllib.request
from datetime import datetime, timezone

import jobstats

_QUEUE: "queue.Queue[dict]" = queue.Queue(maxsize=1000)
_BATCH = 50
_FLUSH_SECONDS = 2.0
_POST_TIMEOUT_SECONDS = 5
_worker_lock = threading.Lock()
_worker = {"thread": None}

# Not pageviews: assets, JSON endpoints, and the browser's automatic fetches.
_SKIP_PREFIXES = ("/static/", "/api/")
_SKIP_PATHS = {"/favicon.ico", "/robots.txt", "/sitemap.xml", "/apple-touch-icon.png"}


def enabled() -> bool:
    return os.environ.get("ANALYTICS_ENABLED", "true").strip().lower() not in ("0", "false", "no", "off")


def _token() -> str:
    return os.environ.get("ANALYTICS_INGEST_TOKEN", "")


def is_pageview(method: str, path: str) -> bool:
    return method == "GET" and path not in _SKIP_PATHS and not path.startswith(_SKIP_PREFIXES)


def client_ip(headers, remote_addr) -> str:
    """Render's proxy puts the visitor first in X-Forwarded-For."""
    forwarded = headers.get("X-Forwarded-For", "")
    return forwarded.split(",")[0].strip() if forwarded else (remote_addr or "")


def capture(request, session) -> bool:
    """Queue one pageview if it is one. Returns True when queued. Never blocks, never raises
    past its caller's try/except (the hook wraps it anyway)."""
    if not enabled() or not _token() or not is_pageview(request.method, request.path):
        return False
    view = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
        "path": request.path,
        "referrer": request.headers.get("Referer", ""),
        "ip": client_ip(request.headers, request.remote_addr),
        "ua": request.headers.get("User-Agent", ""),
        "self": bool(session.get("console_authed")),
    }
    try:
        _QUEUE.put_nowait(view)
    except queue.Full:
        return False  # the engine is unreachable and the buffer is full: drop, never block
    _ensure_worker()
    return True


def _ensure_worker():
    with _worker_lock:
        t = _worker["thread"]
        if t is None or not t.is_alive():
            t = threading.Thread(target=_run, name="visit-forwarder", daemon=True)
            _worker["thread"] = t
            t.start()


def send_batch(views: list[dict]) -> bool:
    """POST one batch to the engine. False on any failure (the batch is dropped, not retried:
    losing a pageview is fine, an ever-growing retry buffer is not)."""
    req = urllib.request.Request(
        f"{jobstats.ENGINE_URL}/analytics/ingest",
        data=json.dumps({"views": views}).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Analytics-Token": _token()},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_POST_TIMEOUT_SECONDS) as resp:
            return 200 <= resp.status < 300
    except OSError as e:
        logging.warning("Visit forward failed (%d views dropped): %s", len(views), e)
        return False


def drain(max_items: int = _BATCH, wait: float = _FLUSH_SECONDS) -> list[dict]:
    """Take up to max_items queued views, waiting up to `wait` seconds for the first one."""
    batch = []
    try:
        batch.append(_QUEUE.get(timeout=wait))
    except queue.Empty:
        return batch
    while len(batch) < max_items:
        try:
            batch.append(_QUEUE.get_nowait())
        except queue.Empty:
            break
    return batch


def _run():
    while True:
        batch = drain()
        if batch:
            send_batch(batch)
        else:
            time.sleep(0.1)
