"""Contact-form lead forwarding.

This service has no persistent disk, so a lead written here would be wiped on the next deploy or
restart. Each submission is POSTed to the job engine's /leads/ingest, which commits it to its
SQLite on a persistent disk. The submitter is only thanked once the engine confirms that write;
any failure is logged here with the lead's contents (so it can be recovered from the logs) and
the submitter is told plainly that it did not go through, with an address to email instead.

Env: LEAD_INGEST_TOKEN (shared with the engine; without it no lead can be sent),
JOB_ENGINE_PUBLIC_URL (shared with jobstats.py), LEAD_FALLBACK_EMAIL.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

import jobstats

_POST_TIMEOUT_SECONDS = 6


def _token() -> str:
    return os.environ.get("LEAD_INGEST_TOKEN", "")


def fallback_email() -> str:
    return os.environ.get("LEAD_FALLBACK_EMAIL", "kevin.miller@montelattice.com")


def ingest_url() -> str:
    return f"{jobstats.ENGINE_URL}/leads/ingest"


def send(lead: dict) -> tuple[bool, str]:
    """POST one lead to the engine. (True, "") only when the engine answered 200 with
    status "ok" and a row id - nothing short of a confirmed write counts. Otherwise
    (False, reason), where reason is the engine's validation message on a 400 and "" for
    anything else (network, timeout, auth, 5xx, a malformed reply)."""
    if not _token():
        logging.error("[LEAD NOT STORED] LEAD_INGEST_TOKEN is unset on the site - cannot forward "
                      "lead %s", _describe(lead))
        return False, ""
    req = urllib.request.Request(
        ingest_url(),
        data=json.dumps(lead).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Lead-Token": _token()},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_POST_TIMEOUT_SECONDS) as resp:
            status = resp.status
            body = json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        reason = ""
        if e.code == 400:
            try:
                reason = str(json.loads(e.read().decode("utf-8")).get("error") or "")
            except (OSError, ValueError, AttributeError):
                reason = ""
        logging.error("[LEAD NOT STORED] engine answered HTTP %s at %s for lead %s",
                      e.code, ingest_url(), _describe(lead))
        return False, reason
    except (OSError, ValueError) as e:  # URLError, timeouts and resets are OSError; bad JSON is ValueError
        logging.error("[LEAD NOT STORED] engine unreachable or unreadable at %s (%s: %s) for lead %s",
                      ingest_url(), type(e).__name__, e, _describe(lead))
        return False, ""
    if status == 200 and isinstance(body, dict) and body.get("status") == "ok" and body.get("id"):
        logging.info("Lead forwarded to engine as #%s", body.get("id"))
        return True, ""
    logging.error("[LEAD NOT STORED] engine answered %s without confirming the write (%r) for lead %s",
                  status, body, _describe(lead))
    return False, ""


def _describe(lead: dict) -> str:
    """The lead as one log line, so a failed submission can be recovered from the logs."""
    return (f"name={lead.get('name', '')!r} email={lead.get('email', '')!r} "
            f"message={str(lead.get('message', ''))[:1000]!r}")
