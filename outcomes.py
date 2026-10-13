"""The one big measured number on each /lattice project card that has one.

Pure: the live engine payload and the build snapshot go in, a dict keyed by the card's href comes
out. Only two figures on this site are measured and received by it: the engine's own totals
(jobstats.fetch) and the build snapshot (buildstats.load). DocFiler, Budget and Crypto have no
measured figure, so they get no entry, and a figure that is unavailable gets no entry either:
there is no fallback number and no placeholder.
"""
from __future__ import annotations


def _count(v) -> int | None:
    """A positive whole number, else None (None, zero, bool, text and fractions all show nothing)."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return int(v) if float(v).is_integer() and v > 0 else None


def card_figures(payload: dict | None, build: dict | None) -> dict[str, dict]:
    out: dict[str, dict] = {}

    applications = _count((payload or {}).get("applications_sent"))
    # A last-good copy served while the engine is down (stale) is not shown as a current figure; the
    # /lattice strip drops its cadence label for the same reason.
    if applications is not None and not (payload or {}).get("stale"):
        out["/job-engine"] = {"value": f"{applications:,}", "label": "Applications sent",
                              "sub": "logged in the CRM"}

    lines = _count((build or {}).get("tracked_lines"))
    repos = _count((build or {}).get("repo_count"))
    when = (build or {}).get("generated_at")
    if lines is not None and repos is not None and hasattr(when, "day"):
        # Spans every repo, never this site alone: the same wording as homepage.LIVE_FIGURES.
        out["/code"] = {"value": f"{lines:,}",
                        "label": f"Lines of tracked code across {repos} repo{'' if repos == 1 else 's'}",
                        "sub": f"As of {when:%b} {when.day}"}
    return out
