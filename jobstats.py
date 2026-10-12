"""Live Job Engine figures for /job-engine and the /lattice teaser.

Every number comes from the job engine's public, read-only /public/dashboard endpoint, fetched at
request time (cached JOBSTATS_TTL_SECONDS, last good copy served if a fetch fails). The templates
hold no figures: this module turns the payload into tiles, and a tile with no data behind it gets
an honest sentence instead of a number.

PUBLIC_FUNNEL_STATS (default "false") gates reply / interview / offer. They are real, but at this
sample size a stranger comparing them to a cold-email benchmark learns the wrong thing. The
throughput grid is complete without them; the funnel is its own section, so hiding it removes a
section, not tiles from a grid.

No benchmark is shown. Each figure is the engine's own number; a comparison appears only with a
citable, measured source behind it, and none was found for these metrics (see BENCHMARKS).
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.request
from datetime import datetime

ENGINE_URL = os.environ.get("JOB_ENGINE_PUBLIC_URL", "https://job-outreach-engine.onrender.com").rstrip("/")
TTL_SECONDS = int(os.environ.get("JOBSTATS_TTL_SECONDS", "300"))
# How often the ENGINE recomputes /public/dashboard: PUBLIC_DASHBOARD_TTL_SECONDS, default 900,
# in job-outreach-engine main.py (~:16010, cache use ~:16157-16170), measured 2026-10-12. The site
# cannot read the engine's env, so this mirrors that default; it exists only to word the cadence
# label honestly. Change it here if the engine's default changes.
ENGINE_FEED_TTL_SECONDS = 900
_FETCH_TIMEOUT_SECONDS = 6

# Each entry needs a visible, clickable, measured source; render() refuses any that lacks one.
BENCHMARKS: dict[str, dict] = {}

_lock = threading.Lock()
_cache = {"payload": None, "fetched_at": 0.0}


def public_funnel_stats() -> bool:
    return os.environ.get("PUBLIC_FUNNEL_STATS", "false").strip().lower() in ("1", "true", "yes", "on")


def _every(seconds: int) -> str:
    """90 -> "90 seconds", 300 -> "5 minutes", 3600 -> "1 hour". Whole units only, else seconds."""
    if seconds >= 3600 and seconds % 3600 == 0:
        n, unit = seconds // 3600, "hour"
    elif seconds >= 60 and seconds % 60 == 0:
        n, unit = seconds // 60, "minute"
    else:
        n, unit = seconds, "second"
    return f"{n} {unit}{'' if n == 1 else 's'}"


def cadence_label() -> str:
    """What the page may honestly say about freshness, built from the two cache lifetimes.

    The pages do not poll: a figure changes on the next page load after both caches expire.
    """
    engine = _every(ENGINE_FEED_TTL_SECONDS)
    if TTL_SECONDS <= 0:  # caching switched off: every load re-reads the engine
        site, oldest = "on every page load", engine
    else:
        site, oldest = f"at most every {_every(TTL_SECONDS)}", _every(ENGINE_FEED_TTL_SECONDS + TTL_SECONDS)
    # The two caches stack, so the oldest a figure can be is the sum, not the longer one.
    return (f"These update themselves: the engine recomputes them every {engine}, and this page "
            f"re-reads them {site}. A figure can be up to {oldest} old.")


def feed_url() -> str:
    return f"{ENGINE_URL}/public/dashboard"


def fetch() -> dict | None:
    now = time.time()
    with _lock:
        if _cache["payload"] is not None and now - _cache["fetched_at"] < TTL_SECONDS:
            return _cache["payload"]
    try:
        with urllib.request.urlopen(feed_url(), timeout=_FETCH_TIMEOUT_SECONDS) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        if payload.get("status") != "ok":
            raise ValueError(f"status {payload.get('status')!r}")
    except (OSError, ValueError) as e:
        logging.error("Job engine feed fetch failed (%s): %s", feed_url(), e)
        with _lock:
            cached = _cache["payload"]
        return dict(cached, stale=True) if cached is not None else None
    with _lock:
        _cache["payload"] = payload
        _cache["fetched_at"] = now
    return payload


def _n(v) -> str:
    return f"{int(v):,}" if isinstance(v, (int, float)) and float(v).is_integer() else f"{v:,}"


def _tile(label, value=None, sub="", empty="", cite=None) -> dict:
    """One tile. value None means 'show the empty sentence instead of a number'."""
    if cite is not None and not (cite.get("source") and cite.get("url")):
        raise ValueError(f"benchmark on {label!r} has no visible source")
    return {"label": label, "value": value, "sub": sub, "empty": empty, "cite": cite}


def _date(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        return datetime.strptime(iso[:10], "%Y-%m-%d").strftime("%b %d, %Y").replace(" 0", " ")
    except ValueError:
        return iso


def build_view(p: dict | None, show_funnel: bool) -> dict | None:
    """Pure: payload in, template context out. None when there is no payload at all."""
    if not p:
        return None

    view = _build_view(p, show_funnel)
    # Not while the engine is down: "updates itself" over a frozen last copy would be untrue.
    view["cadence"] = "" if p.get("stale") else cadence_label()
    return view


def _build_view(p: dict, show_funnel: bool) -> dict:
    screened = p.get("roles_screened")
    discovered = p.get("listings_discovered")
    if screened is None:
        t_screened = _tile("Roles screened", empty="Screener count unavailable right now.")
    elif screened == 0:
        t_screened = _tile("Roles screened", empty="No roles screened yet.")
    else:
        t_screened = _tile("Roles screened", _n(screened),
                           f"AI-evaluated, from {_n(discovered)} listings discovered" if discovered else "AI-evaluated")

    apps = p.get("applications_sent")
    days = p.get("days_running")
    if apps is None:
        t_apps = _tile("Applications sent", empty="CRM unreachable right now.")
    elif apps == 0:
        t_apps = _tile("Applications sent", empty="No applications logged yet.")
    else:
        t_apps = _tile("Applications sent", _n(apps), f"logged in the CRM over {_n(days)} days" if days else "logged in the CRM")

    live = p.get("live_conversations")
    if live is None:
        t_live = _tile("Live conversations", empty="Inbox tray unavailable right now.")
    elif live == 0:
        t_live = _tile("Live conversations", empty="No open recruiter threads right now.")
    else:
        t_live = _tile("Live conversations", _n(live), "open recruiter threads")

    dead = p.get("dead_links")
    if dead is None:
        t_dead = _tile("Dead links retired", empty="Link sweep unavailable right now.")
    elif not dead.get("detected"):
        t_dead = _tile("Dead links retired", empty="No dead links detected yet.")
    else:
        week = dead.get("this_week") or 0
        t_dead = _tile("Dead links retired", _n(dead.get("retired", 0)),
                       f"of {_n(dead['detected'])} detected · "
                       + (f"{_n(week)} this week" if week else "none this week"))

    fit = p.get("median_fit_score")
    if fit is None:
        t_fit = _tile("Median fit score", empty="No scored roles yet.")
    else:
        scored = p.get("scored_roles") or 0
        t_fit = _tile("Median fit score", f"{fit:g}",
                      f"out of 100, across {_n(scored)} role{'' if scored == 1 else 's'} that cleared the screen")

    total, used = p.get("tracks_total"), p.get("tracks_used")
    if not total:
        t_tracks = _tile("Résumé tracks", empty="Track registry unavailable right now.")
    elif used is None:
        t_tracks = _tile("Résumé tracks", _n(total), "tailored résumé tracks the router chooses between")
    else:
        t_tracks = _tile("Résumé tracks", f"{_n(used)} of {_n(total)}", "tracks routed to so far")

    docs = p.get("documents_compiled")
    since = _date(p.get("documents_since"))
    if docs is None:
        t_docs = _tile("Documents compiled", empty="Document counter unavailable right now.")
    elif docs == 0:
        t_docs = _tile("Documents compiled", empty="None since counting began.")
    else:
        t_docs = _tile("Documents compiled", _n(docs), f"résumés and cover letters since {since}")

    d = p.get("drafting")
    drafting = None
    if d and d.get("median_ms") is not None:
        drafting = {
            "value": f"{d['median_ms']:g} ms",
            "detail": f"Median of {_n(d.get('runs', 0))} warm runs on the engine's own server, "
                      f"measured {d.get('measured_at', '').replace('T', ' ').replace('Z', ' UTC')}.",
            "steps": " + ".join(d.get("steps") or []),
        }

    timeline = []
    for w in p.get("timeline") or []:
        timeline.append({"week": w.get("week"), "screened": w.get("ai_screened", 0),
                         "discovered": w.get("listing_discovered", 0)})

    funnel = None
    f = p.get("funnel")
    # Shown only when BOTH services allow it: the engine leaves the funnel out of its payload
    # unless its own PUBLIC_FUNNEL_STATS is true. A CRM outage is already stated on the
    # Applications tile, so an absent funnel just means no Conversion section.
    if show_funnel and f:
        def rate(r):
            return f"{r:g}% of applications" if r is not None else "no applications to rate against yet"
        funnel = {"tiles": [
            _tile("Replies", _n(f.get("replies") or 0), rate(f.get("reply_rate_pct"))),
            _tile("Interviews", _n(f.get("interviews") or 0), rate(f.get("interview_rate_pct"))),
            _tile("Offers", _n(f.get("offers") or 0), rate(f.get("offer_rate_pct"))),
        ], "empty": ""}

    return {
        "primary": [t_screened, t_apps, t_live, t_dead],
        "secondary": [t_fit, t_tracks, t_docs],
        "drafting": drafting,
        "timeline": timeline,
        "funnel": funnel,
        "as_of": _date(p.get("as_of")),
        "stale": bool(p.get("stale")),
        "feed_url": feed_url(),
    }


class Teaser(list):
    """The strip's figures. A list so the template just loops it; .cadence is the freshness label
    (the route passes only this object, so it travels with it). Empty when the figures came from a
    stale copy, so the template shows nothing rather than "updates itself" over frozen numbers."""

    stale = False

    @property
    def cadence(self) -> str:
        return "" if self.stale else cadence_label()


def teaser(p: dict | None) -> list[dict]:
    """Three figures for the /lattice strip; [] when there is nothing real to show."""
    if not p:
        return Teaser()
    out = Teaser()
    if p.get("roles_screened"):
        out.append({"value": p["roles_screened"], "label": "Roles Screened", "suffix": ""})
    if p.get("applications_sent"):
        out.append({"value": p["applications_sent"], "label": "Applications Sent", "suffix": ""})
    d = p.get("drafting") or {}
    if d.get("median_ms") is not None:
        out.append({"value": d["median_ms"], "label": "Match to Draft", "suffix": " ms"})
    out.stale = bool(p.get("stale"))
    return out
