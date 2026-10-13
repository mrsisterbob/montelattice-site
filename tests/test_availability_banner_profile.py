"""The homepage shows the same availability banner as the base.html pages, from the same partial
and the same siteflags switch, including on the 503 page. Run: python -m pytest tests -q
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


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setattr(homepage, "load_bank", lambda: BANK)
    return main.app.test_client()


def test_availability_profile_shows_the_exact_text_once(client):
    html = client.get("/").get_data(as_text=True)
    assert html.count(TEXT) == 1
    assert html.index('class="availability"') < html.index('<header class="topbar"')


def test_availability_profile_503_page_still_shows_it(client, monkeypatch):
    monkeypatch.setattr(homepage, "load_bank", lambda: None)
    r = client.get("/")
    assert r.status_code == 503
    assert r.get_data(as_text=True).count(TEXT) == 1


def test_availability_profile_the_one_switch_removes_it_from_both(client, monkeypatch):
    monkeypatch.setattr(siteflags, "SHOW_AVAILABILITY_BANNER", False)
    assert TEXT not in client.get("/").get_data(as_text=True)
    monkeypatch.setattr(homepage, "load_bank", lambda: None)
    assert TEXT not in client.get("/").get_data(as_text=True)


def test_availability_profile_uses_the_shared_partial_not_a_copy(client):
    src = (ROOT / "templates" / "profile.html").read_text(encoding="utf-8")
    assert '{% include "_availability.html" %}' in src
    assert "Open to operations" not in src


def test_availability_profile_text_follows_siteflags(client, monkeypatch):
    monkeypatch.setattr(siteflags, "AVAILABILITY_TEXT", "Booked until spring")
    html = client.get("/").get_data(as_text=True)
    assert "Booked until spring" in html and TEXT not in html


def test_availability_profile_css_is_in_profile_css_with_tokens_only(client):
    css = client.get("/static/css/profile.css").get_data(as_text=True)
    m = re.search(r"\.availability \{([^}]*)\}", css)
    assert m, "profile.css has no .availability rule"
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", m.group(1))
    assert "var(--teal-deep)" in m.group(1) and "var(--on-teal)" in m.group(1)
