"""Telegram-by-proxy alert when a visitor downloads the resume.

This site has no Telegram token and must not get one. A download is reported by POSTing one lead
to the job engine's /leads/ingest (via leads.send), which stores it and alerts Kevin. The send
runs in a daemon thread, so the PDF never waits on the engine and a failed send never fails the
download. No IP, user agent or referrer goes into the lead: the footer promises no trackers, and
the IP is held here only as a hash, in memory, for the 10-minute repeat window.
"""
from __future__ import annotations

import hashlib
import logging
import threading
import time
from datetime import datetime, timezone

import leads
import visits

SOURCE = "montelattice.com/resume"
_NAME = "R\u00e9sum\u00e9 download"
_EMAIL = "resume-download@montelattice.com"
_WINDOW_SECONDS = 600
_MAX_REMEMBERED = 2000
_BOT_MARKERS = ("bot", "crawler", "spider", "preview", "slurp", "curl", "python-requests",
                "headlesschrome")

_seen: dict[str, float] = {}
_lock = threading.Lock()


def _now() -> float:
    return time.time()


def _is_bot(user_agent: str) -> bool:
    ua = (user_agent or "").strip().lower()
    return not ua or any(m in ua for m in _BOT_MARKERS)


def _repeat(ip: str) -> bool:
    """True if this IP already alerted inside the window; otherwise remember it."""
    key = hashlib.sha256(ip.encode("utf-8")).hexdigest()
    now = _now()
    with _lock:
        for k in [k for k, t in _seen.items() if now - t >= _WINDOW_SECONDS]:
            del _seen[k]
        if key in _seen:
            return True
        while len(_seen) >= _MAX_REMEMBERED:
            del _seen[min(_seen, key=_seen.get)]
        _seen[key] = now
        return False


def _send(lead: dict) -> None:
    try:
        ok, _ = leads.send(lead)
        if not ok:
            logging.warning("Resume alert was not delivered")
    except Exception as e:  # noqa: BLE001 - an alert may never break anything
        logging.warning("Resume alert failed: %s", e)


def notify(request, session):
    """Start the alert thread and return it, or return None when no alert is due."""
    if request.method != "GET" or _is_bot(request.headers.get("User-Agent", "")):
        return None
    if session.get("console_authed"):
        return None
    if _repeat(visits.client_ip(request.headers, request.remote_addr)):
        return None
    stamp = datetime.fromtimestamp(_now(), timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    lead = {"name": _NAME, "email": _EMAIL,
            "message": f"R\u00e9sum\u00e9 downloaded at {stamp} UTC", "source": SOURCE}
    t = threading.Thread(target=_send, args=(lead,), daemon=True)
    t.start()
    return t
