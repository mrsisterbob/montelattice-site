"""Site-wide switches, in one place, exposed to every template through main.py's context processor.

A flag lives here rather than as hard-coded markup so changing what the site says about itself is
a one-line edit with a test behind it. main.py merges template_context() into its context
processor once; a new flag is added to the dict below and never needs a main.py change.
"""
from __future__ import annotations

# Status shown as a small tag on the /lattice project cards, keyed by the card's path slug
# (/job-engine -> "job-engine"). A project with no entry carries no status tag. Values are the
# words shown, and the CSS modifier is derived from them (Live -> status-tag--live).
PROJECT_STATUS: dict[str, str] = {
    "job-engine": "Live",
    "docfiler": "Beta",
    "budget": "Live",
}


# The availability banner (templates/_availability.html), shown above the top bar of every page that
# extends base.html except the private Console. One switch: False hides it everywhere.
SHOW_AVAILABILITY_BANNER = True
AVAILABILITY_TEXT = "Open to operations and finance roles in Detroit · Taking on a few build projects"


def template_context() -> dict:
    """Read at call time (not import time), so a test or a later edit to the module attributes
    is what the next request renders."""
    return {
        "project_status": dict(PROJECT_STATUS),
        "availability": (AVAILABILITY_TEXT.strip() or None) if SHOW_AVAILABILITY_BANNER else None,
    }
