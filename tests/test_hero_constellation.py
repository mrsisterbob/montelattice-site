"""A faint constellation sits behind the two heroes, themed by a token, behind the text, and
static under prefers-reduced-motion. Run: python -m pytest tests -q
"""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import homepage  # noqa: E402
import main  # noqa: E402

BANK = {"identity": {"name": "K"}, "site_profile": {"resume_note": "Available on request, tailored to the role."}}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setattr(homepage, "load_bank", lambda: BANK)
    monkeypatch.setattr(main.jobstats, "fetch", lambda: None)
    return main.app.test_client()


def _rule(css, selector):
    m = re.search(r"(?:^|\n)" + re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert m, selector
    return m.group(1)


def test_constellation_svg_is_a_small_black_mask_of_points_and_lines(client):
    r = client.get("/static/img/constellation.svg")
    assert r.status_code == 200
    svg = r.get_data(as_text=True)
    assert 'xmlns="http://www.w3.org/2000/svg"' in svg and "viewBox=" in svg
    colours = set(re.findall(r'(?:fill|stroke)="([^"]*)"', svg))
    assert colours <= {"#000", "#000000", "black", "none", "currentColor"}, colours
    assert "<circle" in svg and "<path" in svg and "<image" not in svg and "<text" not in svg
    assert len(svg.encode()) < 4096


@pytest.mark.parametrize("sheet,selector,token", [
    ("rapture.css", ".intro::before", "var(--brass-warm)"),
    ("profile.css", ".masthead::before", "var(--on-teal)"),
])
def test_constellation_pseudo_element_is_a_masked_token_behind_the_text(client, sheet, selector, token):
    css = client.get(f"/static/css/{sheet}").get_data(as_text=True)
    body = _rule(css, selector)
    assert "constellation.svg" in body
    assert "-webkit-mask:" in body and re.search(r"(?<!-)mask:", body)
    assert "pointer-events: none" in body
    assert f"background-color: {token}" in body
    assert re.search(r"z-index:\s*-1", body)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", body)
    opacity = float(re.search(r"opacity:\s*([\d.]+)", body).group(1))
    assert 0.05 <= opacity <= 0.2, opacity


@pytest.mark.parametrize("sheet,selector", [("rapture.css", ".intro::before"), ("profile.css", ".masthead::before")])
def test_constellation_is_static_or_its_animation_is_cancelled_under_reduced_motion(client, sheet, selector):
    css = client.get(f"/static/css/{sheet}").get_data(as_text=True)
    if "animation:" not in _rule(css, selector):
        assert "twinkle" not in css and "constellation-" not in css.replace("constellation.svg", "")
        return
    block = re.search(r"@media \(prefers-reduced-motion: reduce\) \{\s*" + re.escape(selector)
                      + r"\s*\{([^}]*)\}", css)
    assert block, f"{selector} has an animation but no reduced-motion rule"
    assert "animation: none" in block.group(1)


def test_constellation_keeps_its_scale_on_a_tall_hero_and_stays_inside_the_band(client):
    rapture = client.get("/static/css/rapture.css").get_data(as_text=True)
    profile = client.get("/static/css/profile.css").get_data(as_text=True)
    intro = _rule(rapture, ".intro::before")
    # The .intro section is very tall on a phone; `cover` over all of it would blow the 2:1 art up.
    assert "inset: 0 0 auto 0" in intro and re.search(r"height:\s*min\(100%,\s*\d+px\)", intro)
    assert "center top / cover" in intro
    assert "isolation: isolate" in _rule(rapture, ".intro")
    masthead = _rule(profile, ".masthead")
    assert "isolation: isolate" in masthead and "position: relative" in masthead
    assert "inset: 0" in _rule(profile, ".masthead::before")


def test_constellation_the_heroes_still_render(client):
    assert 'class="masthead' in client.get("/").get_data(as_text=True)
    assert 'class="wrap intro"' in client.get("/lattice").get_data(as_text=True)
