"""Where the constellation lives, and where it does not.

2026-10-13: Kevin reverted the bar layers; the lines live in the masthead, contact band and tool webs
only. The top bar and the site footer are plain teal bars (see tests/test_contact_separation.py for
the measured side). What stays pinned here: the ONE shared @keyframes, and that every page has the
shared top bar and the shared footer. Run: python -m pytest tests -q
"""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import homepage  # noqa: E402
import jobstats  # noqa: E402
import main  # noqa: E402

BANK = {"identity": {"name": "K"}, "site_profile": {"resume_note": "Available on request."}}
PAGES = ["/", "/lattice", "/job-engine", "/docfiler", "/budget", "/code"]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setattr(homepage, "load_bank", lambda: BANK)
    monkeypatch.setattr(jobstats, "fetch", lambda *a, **k: None)
    return main.app.test_client()


def test_one_keyframes_for_the_whole_site_and_it_is_in_topbar_css(client):
    sheets = {p.name: p.read_text(encoding="utf-8") for p in (ROOT / "static" / "css").glob("*.css")}
    total = sum(len(re.findall(r"@keyframes constellation-drift", t)) for t in sheets.values())
    assert total == 1
    assert "@keyframes constellation-drift" in sheets["topbar.css"]


@pytest.mark.parametrize("path", PAGES)
def test_every_page_has_the_top_bar_and_the_footer(client, path):
    html = client.get(path).get_data(as_text=True)
    assert '<header class="topbar">' in html
    assert '<footer class="site-footer">' in html  # the homepage included since 2026-10-13


def test_crypto_page_has_both_bars_when_public(client, monkeypatch):
    monkeypatch.setenv("PUBLIC_CRYPTO", "true")
    html = client.get("/crypto").get_data(as_text=True)
    assert '<header class="topbar">' in html and '<footer class="site-footer">' in html
