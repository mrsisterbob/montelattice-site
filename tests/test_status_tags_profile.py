"""The homepage's "Proof: the systems" cards carry the same status tags as /lattice, from the same
siteflags.PROJECT_STATUS. Run: python -m pytest tests -q
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

BANK = {"identity": {"name": "K"}, "site_profile": {"resume_note": "Available on request, tailored to the role."}}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setattr(homepage, "load_bank", lambda: BANK)
    return main.app.test_client()


def _systems(html):
    """{system name: its .sys-name row html}"""
    rows = re.findall(r'<div class="sys-name">(.*?)</div>', html, re.S)
    out = {}
    for row in rows:
        name = re.sub(r"<[^>]+>", "", re.sub(r'<span class="status-tag[^>]*>[^<]*</span>', "", row)).strip()
        out[name] = row
    return out


def _tag(row):
    m = re.search(r'<span class="status-tag status-tag--([\w-]+)">([^<]+)</span>', row)
    return (m.group(1), m.group(2)) if m else None


def test_profile_status_tags_match_lattice_live_beta_live_and_crypto_untagged(client):
    systems = _systems(client.get("/").get_data(as_text=True))
    assert _tag(systems["Job Outreach Engine"]) == ("live", "Live")
    assert _tag(systems["DocFiler"]) == ("beta", "Beta")
    assert _tag(systems["Budget Tracker"]) == ("live", "Live")
    assert _tag(systems["Crypto Trading Engine"]) is None


def test_profile_status_tags_follow_the_module_not_the_template(client, monkeypatch):
    monkeypatch.setenv("PUBLIC_CRYPTO", "true")
    monkeypatch.setattr(siteflags, "PROJECT_STATUS", {})
    html = client.get("/").get_data(as_text=True)
    assert 'class="status-tag' not in html
    monkeypatch.setattr(siteflags, "PROJECT_STATUS", {"crypto": "Beta", "budget": "Coming Soon"})
    systems = _systems(client.get("/").get_data(as_text=True))
    assert _tag(systems["Crypto Trading Engine"]) == ("beta", "Beta")
    assert _tag(systems["Budget Tracker"]) == ("coming-soon", "Coming Soon")
    assert _tag(systems["Job Outreach Engine"]) is None


def test_profile_status_tags_are_the_same_words_the_lattice_page_shows(client, monkeypatch):
    monkeypatch.setattr(main.jobstats, "fetch", lambda: None)
    lattice = client.get("/lattice").get_data(as_text=True)
    home = client.get("/").get_data(as_text=True)
    on_lattice = sorted(re.findall(r'class="status-tag status-tag--[\w-]+">([^<]+)<', lattice))
    on_home = sorted(re.findall(r'class="status-tag status-tag--[\w-]+">([^<]+)<', home))
    assert on_lattice == on_home == ["Beta", "Live", "Live"]


def test_profile_status_tags_css_uses_tokens_only(client):
    css = client.get("/static/css/profile.css").get_data(as_text=True)
    block = css[css.index(".status-tag {"):css.index(".sys-desc")]
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", block)
    assert "var(--ok)" in block and "var(--brass-text)" in block


def test_profile_503_page_does_not_need_the_flags(monkeypatch):
    monkeypatch.setattr(homepage, "load_bank", lambda: None)
    assert main.app.test_client().get("/").status_code == 503


def test_profile_a_hidden_project_advertises_no_status(client, monkeypatch):
    monkeypatch.delenv("PUBLIC_CRYPTO", raising=False)
    monkeypatch.setattr(siteflags, "PROJECT_STATUS", {"crypto": "Live", "budget": "Live"})
    systems = _systems(client.get("/").get_data(as_text=True))
    assert _tag(systems["Crypto Trading Engine"]) is None
    assert _tag(systems["Budget Tracker"]) == ("live", "Live")
