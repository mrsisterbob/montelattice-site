"""A small static glyph of the settled tool grid sits above each section heading, drawn by a CSS
mask so a theme token colours it. Run: python -m pytest tests -q
"""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import homepage  # noqa: E402
import main  # noqa: E402
import tools  # noqa: E402

BANK = {"identity": {"name": "K"}, "site_profile": {"resume_note": "Available on request, tailored to the role."}}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setattr(homepage, "load_bank", lambda: BANK)
    monkeypatch.setattr(main.jobstats, "fetch", lambda: None)
    return main.app.test_client()


def _rule(css, selector):
    m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert m, selector
    return m.group(1)


def test_section_glyph_svg_is_a_standalone_black_mask(client):
    r = client.get("/static/img/lattice-glyph.svg")
    assert r.status_code == 200
    svg = r.get_data(as_text=True)
    assert 'xmlns="http://www.w3.org/2000/svg"' in svg and "viewBox=" in svg
    fills = set(re.findall(r'fill="([^"]*)"', svg))
    assert fills <= {"#000", "#000000", "black", "currentColor"}, fills
    assert "stroke=" not in svg and "<image" not in svg and "<text" not in svg


def test_section_glyph_has_one_cell_per_tool_plus_the_centre(client):
    svg = client.get("/static/img/lattice-glyph.svg").get_data(as_text=True)
    assert svg.count("<rect") == len(tools.TOOLS) + 1


def test_section_glyph_rapture_css_masks_it_with_a_token_background(client):
    css = client.get("/static/css/rapture.css").get_data(as_text=True)
    body = _rule(css, ".section-heading::before")
    assert "lattice-glyph.svg" in body
    assert "-webkit-mask:" in body and re.search(r"(?<!-)mask:", body)
    assert "background-color: var(--brass-warm)" in body
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", body)
    # Excluded: console headings, and the login card's heading (the only .section-heading that is
    # a direct child of a .data-card, so it is not under .console).
    hidden = re.search(r"\.console \.section-heading::before,\s*\.data-card > \.section-heading::before\s*\{([^}]*)\}", css)
    assert hidden and "display: none" in hidden.group(1)


def test_section_glyph_profile_css_does_the_same_for_its_headings(client):
    css = client.get("/static/css/profile.css").get_data(as_text=True)
    body = _rule(css, ".wrap > h2::before")
    assert "lattice-glyph.svg" in body
    assert "-webkit-mask:" in body and re.search(r"(?<!-)mask:", body)
    assert "background-color: var(--brass-warm)" in body


def test_section_glyph_the_css_url_resolves_to_the_served_file(client):
    css = client.get("/static/css/rapture.css").get_data(as_text=True)
    assert 'url("../img/lattice-glyph.svg")' in css  # rapture.css is at /static/css/


def test_section_glyph_has_headings_to_attach_to(client):
    assert 'class="section-heading' in client.get("/job-engine").get_data(as_text=True)
    assert "<h2>" in client.get("/").get_data(as_text=True)


def test_section_glyph_the_login_heading_is_the_only_section_heading_in_a_data_card():
    """The CSS exclusion for the login page relies on this: no public template nests one."""
    for path in (ROOT / "templates").glob("*.html"):
        src = path.read_text(encoding="utf-8")
        direct = re.findall(r'<div class="data-card[^"]*">\s*<h2 class="section-heading', src)
        assert (len(direct) == 1) == (path.name == "console_login.html"), path.name


def test_section_glyph_profile_contact_band_and_notice_are_not_ornamented(client):
    css = client.get("/static/css/profile.css").get_data(as_text=True)
    assert not re.search(r"^h2::before", css, re.M)
