"""A faint constellation sits behind the contact band and the tool-web backdrop (not the masthead), themed by a token, behind the text, and
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
    """The declarations of every top-level rule whose selector list names `selector` (a shared
    rule such as `.masthead::before, .contact::before` counts), joined."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    bodies = [m.group(2) for m in re.finditer(r"(?:^|\n)([^\s{}@][^{}]*?)\s*\{([^}]*)\}", css)
              if selector in [x.strip() for x in m.group(1).split(",")]]
    assert bodies, selector
    return "\n".join(bodies)


def _rule_or_none(css, selector):
    """Like _rule, but yields nothing instead of failing when no rule names `selector`."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    for m in re.finditer(r"(?:^|\n)([^\s{}@][^{}]*?)\s*\{([^}]*)\}", css):
        if selector in [x.strip() for x in m.group(1).split(",")]:
            yield m.group(2)


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
    ("toolweb.css", ".web-backdrop::before", "var(--brass-warm)"),
    ("profile.css", ".contact::before", "var(--on-teal)"),
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
    assert 0.05 <= opacity <= 0.24, opacity


@pytest.mark.parametrize("sheet,selector", [("toolweb.css", ".web-backdrop::before"),
                                            ("profile.css", ".contact::before")])
def test_constellation_animation_is_cancelled_under_reduced_motion(client, sheet, selector):
    css = client.get(f"/static/css/{sheet}").get_data(as_text=True)
    assert "animation:" in _rule(css, selector)
    block = re.search(r"@media \(prefers-reduced-motion: reduce\) \{\s*" + re.escape(selector)
                      + r"\s*\{([^}]*)\}", css)
    assert block, f"{selector} has an animation but no reduced-motion rule"
    assert "animation: none" in block.group(1)


@pytest.mark.parametrize("sheet,selector,low,high", [
    ("toolweb.css", ".web-backdrop::before", 0.16, 0.24),
    # The contact band's 60%-opacity footnote is the limit (test_constellation_motion.py recomputes it).
    ("profile.css", ".contact::before", 0.08, 0.11),
])
def test_constellation_drifts_slowly_inside_its_opacity_range(client, sheet, selector, low, high):
    css = client.get(f"/static/css/{sheet}").get_data(as_text=True)
    body = _rule(css, selector)
    assert re.search(r"animation:[^;]*constellation-drift", body), f"{selector} does not move"
    assert re.search(r"animation:[^;]*\balternate\b", body)
    # How fast it moves is measured in Chrome (test_constellation_motion.py). This floor only keeps
    # the cycle slow enough to read as drift: every band runs 40s one way at every width
    # (one value, so a resize never jumps phase), and a cycle under 12s would read as scrolling.
    seconds = [float(x) for x in re.findall(r"constellation-drift\s+([\d.]+)s", body)]
    assert seconds and min(seconds) >= 12, seconds
    # One @keyframes for the whole site, in topbar.css (every page loads or imports it); the
    # heroes' sheets carry none of their own.
    assert "@keyframes constellation-drift" not in css
    sheets = {p.name: p.read_text(encoding="utf-8") for p in (ROOT / "static" / "css").glob("*.css")}
    holders = [n for n, text in sheets.items() if "@keyframes constellation-drift" in text]
    assert holders == ["topbar.css"], holders
    assert len(re.findall(r"@keyframes constellation-drift", sheets["topbar.css"])) == 1
    frames = re.search(r"@keyframes constellation-drift\s*\{(.*?)\}\s*\}", sheets["topbar.css"], re.S).group(1)
    assert "-webkit-mask-position" in frames and re.search(r"(?<!-)mask-position", frames)
    assert "transform" not in frames  # a transform widens the page
    opacity = float(re.search(r"opacity:\s*([\d.]+)", body).group(1))
    assert low <= opacity <= high, opacity


def test_constellation_keeps_its_scale_on_a_tall_hero_and_stays_inside_the_band(client):
    rapture = client.get("/static/css/rapture.css").get_data(as_text=True)
    toolweb = client.get("/static/css/toolweb.css").get_data(as_text=True)
    profile = client.get("/static/css/profile.css").get_data(as_text=True)
    # The hero's layer is the shared .web-backdrop, sized to its own box (a wrapper around the
    # wordmark, the line and the web), so `cover` cannot blow the art up over a tall section; its
    # coverage of the labels is measured in tests/test_web_backdrop.py. The old capped layer is gone.
    assert not list(_rule_or_none(rapture, ".intro::before"))
    backdrop = _rule(toolweb, ".web-backdrop")
    assert "isolation: isolate" in backdrop and "position: relative" in backdrop
    assert "inset: 0" in _rule(toolweb, ".web-backdrop::before")


def test_masthead_has_no_constellation_layer(client):
    css = re.sub(r"/\*.*?\*/", "", client.get("/static/css/profile.css").get_data(as_text=True), flags=re.S)
    assert ".masthead::before" not in css
    assert 'class="masthead' in client.get("/").get_data(as_text=True)


def test_constellation_the_heroes_still_render(client):
    assert 'class="masthead' in client.get("/").get_data(as_text=True)
    assert 'class="wrap intro"' in client.get("/lattice").get_data(as_text=True)
