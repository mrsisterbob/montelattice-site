"""Homepage profile: loads Kevin's evidence bank and shapes it for templates/profile.html.

The bank lives in the job-outreach-engine repo (evidence_bank.json), which is also what the résumé
compiler renders from. This site deliberately keeps no copy of it: a second copy drifts the moment
a bullet changes, and the drifted one is the version strangers see. So the page reads the bank at
request time from EVIDENCE_BANK_SOURCE, which is either a filesystem path or an http(s) URL.

Default source, in order:
  1. EVIDENCE_BANK_SOURCE env var, if set.
  2. The sibling checkout (../job-outreach-engine/evidence_bank.json), if it exists - local dev, so
     an edit to the bank shows on the next reload.
  3. The raw file on the public GitHub repo's main branch - production on Render, zero config.
     A bank edit goes live once it is pushed to main (GitHub's raw CDN caches ~5 min on top of
     the TTL below). No job-engine deploy is needed.

A local file is re-read on every request. A URL is cached for BANK_TTL_SECONDS, and a failed fetch
serves the last good copy rather than nothing.
"""
from __future__ import annotations

import html
import json
import logging
import os
import re
import threading
import time
import urllib.request

_SIBLING_BANK = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "job-outreach-engine", "evidence_bank.json"))
_GITHUB_BANK = "https://raw.githubusercontent.com/mrsisterbob/job-outreach-engine/main/evidence_bank.json"

BANK_TTL_SECONDS = int(os.environ.get("EVIDENCE_BANK_TTL_SECONDS", "300"))
# Short on purpose: Render health-checks "/", so a hung fetch must not hang the page.
_FETCH_TIMEOUT_SECONDS = 4

_cache_lock = threading.Lock()
_cache = {"bank": None, "fetched_at": 0.0}


def bank_source() -> str:
    explicit = os.environ.get("EVIDENCE_BANK_SOURCE", "").strip()
    if explicit:
        return explicit
    if os.path.exists(_SIBLING_BANK):
        return _SIBLING_BANK
    return _GITHUB_BANK


def load_bank() -> dict | None:
    """Return the evidence bank dict, or None when no copy has ever been readable."""
    source = bank_source()
    if not source.startswith(("http://", "https://")):
        try:
            with open(source, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError) as e:
            logging.error("Evidence bank read failed (%s): %s", source, e)
            return None

    now = time.time()
    with _cache_lock:
        if _cache["bank"] is not None and now - _cache["fetched_at"] < BANK_TTL_SECONDS:
            return _cache["bank"]
    try:
        with urllib.request.urlopen(source, timeout=_FETCH_TIMEOUT_SECONDS) as resp:
            bank = json.loads(resp.read().decode("utf-8"))
    except (OSError, ValueError) as e:
        logging.error("Evidence bank fetch failed (%s): %s", source, e)
        with _cache_lock:
            return _cache["bank"]  # stale beats nothing; None if we never had one
    with _cache_lock:
        _cache["bank"] = bank
        _cache["fetched_at"] = now
    return bank


def _emphasis(text: str) -> str:
    """Escape, then turn **x** into <strong>x</strong>. The only markup the bank's prose uses."""
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html.escape(str(text or "")))


def _year(mm_yyyy: str) -> str:
    return str(mm_yyyy or "").rsplit("/", 1)[-1]


def _span(start: str, end: str) -> str:
    a, b = _year(start), _year(end)
    return b if not a or a == b else f"{a}–{b}"


# Figures the bank marks {"live": key} are measured (buildstats.py), never typed into the bank.
# The labels live here, not in the bank, so the honest wording can't drift from what is measured.
LIVE_FIGURES = {
    "commit_hours": ("Hours with a commit", "A measured floor, not a total. As of {date}."),
    "tracked_lines": ("Lines of tracked code across {repos} repos", "As of {date}."),
}
LIVE_EMPTY = "Not measured right now."


def _live_figure(key: str, build: dict | None) -> dict | None:
    if key not in LIVE_FIGURES:
        logging.warning("Dropping homepage figure: unknown live key %r", key)
        return None
    label, note = LIVE_FIGURES[key]
    if not build:
        return {"value": None, "label": label.format(repos="my"), "note": "", "empty": LIVE_EMPTY,
                "live": True}
    date = f"{build['generated_at']:%b} {build['generated_at'].day}"
    return {"value": f"{build[key]:,}", "label": label.format(repos=build["repo_count"]),
            "note": note.format(date=date), "empty": "", "live": True}


def _figures(site: dict, experience: list, build: dict | None = None) -> list[dict]:
    """A figure citing a bullet is shown only while that bullet still contains its value, so a
    headline number can't outlive the bullet it came from."""
    by_company = {e.get("company"): e for e in experience}
    out = []
    for fig in site.get("figures", []):
        if fig.get("live"):
            live = _live_figure(fig["live"], build)
            if live:
                out.append(live)
            continue
        src = fig.get("source")
        if src:
            bullets = by_company.get(src.get("company"), {}).get("bullets", [])
            i = src.get("bullet")
            if not isinstance(i, int) or not 0 <= i < len(bullets) or str(fig.get("value")) not in bullets[i]:
                logging.warning("Dropping homepage figure %r: its source bullet no longer supports it", fig.get("value"))
                continue
        out.append({"value": fig.get("value", ""), "label": fig.get("label", ""), "note": "",
                    "empty": "", "live": False})
    return out


def _roles(site: dict, experience: list) -> list[dict]:
    picks = site.get("role_bullets", {})
    roles = []
    for e in experience:
        bullets = e.get("bullets", [])
        wanted = picks.get(e.get("company"))
        if wanted is None:
            chosen = bullets[:2]
        else:
            chosen = [bullets[i] for i in wanted if isinstance(i, int) and 0 <= i < len(bullets)]
        roles.append({
            "title": e.get("title", ""),
            "company": e.get("company", ""),
            "when": _span(e.get("start", ""), e.get("end", "")),
            "bullets": chosen,
        })
    return roles


def _credentials(bank: dict) -> list[str]:
    lines = []
    for edu in bank.get("education", []):
        degree = str(edu.get("degree", "")).replace(", B.A.", " and B.A.")
        lines.append(", ".join(p for p in (degree, edu.get("school", ""), _year(edu.get("end", ""))) if p))
    lines.extend(str(c) for c in bank.get("certificates", []))
    return lines


def _research(bank: dict) -> list[dict]:
    return [{
        "kind": r.get("kind", ""),
        "title": r.get("title", ""),
        "tail": ", ".join(p for p in (r.get("course", ""), r.get("summary", "")) if p),
    } for r in bank.get("research", [])]


def _athletics(bank: dict) -> list[str]:
    lines = []
    for a in bank.get("athletics", []):
        head = ", ".join(p for p in (a.get("honor", ""), a.get("sport", ""), a.get("school", "")) if p)
        pbs = [f"{pb.get('time')} ({pb.get('event')})" for pb in a.get("personal_bests", [])]
        lines.append(f"{head}. Personal bests {' and '.join(pbs)}" if pbs else head)
    return lines


def build_profile(bank: dict, build: dict | None = None) -> dict:
    """Pure: bank dict in, template context out. Every biographical string on the page comes
    through here."""
    identity = bank.get("identity", {})
    site = bank.get("site_profile", {})
    experience = bank.get("experience", [])
    linkedin_url = identity.get("linkedin_url") or (
        f"https://{identity['linkedin']}" if identity.get("linkedin") else "")
    github = identity.get("github", "")
    return {
        "name": identity.get("name", ""),
        "eyebrow": site.get("eyebrow", identity.get("location", "")),
        "claim_html": _emphasis(site.get("claim", "")),
        "figures": _figures(site, experience, build),
        "story": [{"text": s.get("text", ""), "pull": bool(s.get("pull"))} for s in site.get("story", [])],
        "roles": _roles(site, experience),
        "credentials": _credentials(bank),
        "research": _research(bank),
        "memberships": ", ".join(bank.get("memberships", [])),
        "athletics": _athletics(bank),
        "offhours": site.get("offhours", []),
        "email": identity.get("site_email") or identity.get("email", ""),
        "phone": identity.get("phone", ""),
        # tel: wants bare digits (and a leading + if there is one); the display keeps its dashes.
        "phone_tel": "tel:" + re.sub(r"(?!^\+)[^\d]", "", identity.get("phone", "").strip()),
        "resume_note": site.get("resume_note", ""),
        "github": github,
        "github_url": f"https://{github}" if github else "",
        "linkedin_url": linkedin_url,
        "linkedin_label": re.sub(r"^https?://(www\.)?", "", linkedin_url).rstrip("/"),
        "footnote": site.get("footnote", ""),
    }
