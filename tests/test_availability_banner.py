"""The availability banner shows on every page that extends base.html (except the private
Console) and one switch in siteflags.py turns it off. Run: python -m pytest tests -q
"""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import homepage  # noqa: E402
import main  # noqa: E402
import siteflags  # noqa: E402

TEXT = "Open to operations and finance roles in Detroit · Taking on a few build projects"
BANK = {"identity": {"name": "K"}, "site_profile": {"resume_note": "Available on request, tailored to the role."}}
PAGES = ["/lattice", "/job-engine", "/docfiler", "/budget", "/code"]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setattr(homepage, "load_bank", lambda: BANK)
    monkeypatch.setattr(main.jobstats, "fetch", lambda: None)
    return main.app.test_client()


@pytest.mark.parametrize("path", PAGES)
def test_availability_banner_shows_the_exact_text_once(client, path):
    html = client.get(path).get_data(as_text=True)
    assert html.count(TEXT) == 1, path
    assert '<aside class="availability" aria-label="Availability">' in html


def test_availability_banner_sits_above_the_top_bar(client):
    html = client.get("/lattice").get_data(as_text=True)
    assert html.index('class="availability"') < html.index('<header class="topbar">')
    assert html.index("<body>") < html.index('class="availability"')


@pytest.mark.parametrize("path", PAGES)
def test_availability_banner_one_switch_turns_it_off_everywhere(client, monkeypatch, path):
    monkeypatch.setattr(siteflags, "SHOW_AVAILABILITY_BANNER", False)
    html = client.get(path).get_data(as_text=True)
    assert TEXT not in html and 'class="availability"' not in html


def test_availability_banner_text_is_read_at_request_time(client, monkeypatch):
    monkeypatch.setattr(siteflags, "AVAILABILITY_TEXT", "Booked until spring")
    html = client.get("/lattice").get_data(as_text=True)
    assert "Booked until spring" in html and TEXT not in html


def test_availability_banner_is_not_on_the_console(client, monkeypatch):
    monkeypatch.setenv("PUBLIC_CONSOLE_DEMO", "true")
    r = client.get("/console/demo")
    assert r.status_code == 200
    assert TEXT not in r.get_data(as_text=True)


def test_availability_banner_is_not_a_section_element(client):
    """tests/test_public_console_demo.py takes the first </section> on /lattice to be the intro's."""
    src = (ROOT / "templates" / "_availability.html").read_text(encoding="utf-8")
    assert "<section" not in re.sub(r"\{#.*?#\}", "", src, flags=re.S)


def test_availability_banner_css_uses_tokens_only(client):
    css = client.get("/static/css/rapture.css").get_data(as_text=True)
    block = css[css.index(".availability {"):css.index("/* --- Top bar")]
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", block)
    assert "var(--teal-deep)" in block and "var(--on-teal)" in block


def test_availability_banner_a_blank_text_renders_no_empty_bar(client, monkeypatch):
    monkeypatch.setattr(siteflags, "AVAILABILITY_TEXT", "   ")
    assert 'class="availability"' not in client.get("/lattice").get_data(as_text=True)
