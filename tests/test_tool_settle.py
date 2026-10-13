"""The /lattice tool logos settle into their grid once; with JS off or reduced motion they are
simply the settled grid. Run: python -m pytest tests -q
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


def _page(client):
    return client.get("/lattice").get_data(as_text=True)


def test_tool_settle_markup_is_the_settled_grid_by_default(client):
    html = _page(client)
    svg = re.search(r'<svg class="([^"]*)"', html[html.index('<svg class="tool-grid'):]).group(1)
    assert "settling" not in svg and "scattered" not in svg
    assert "is-settling" not in html and "is-scattered" not in html


def test_tool_settle_every_position_has_a_deterministic_scatter_offset_in_css(client):
    css = client.get("/static/css/toolweb.css").get_data(as_text=True)
    rules = re.findall(
        r"\.tool-grid \.tool:nth-of-type\((\d+)\) \.tool__mark \{ --sx: (-?\d+)px; --sy: (-?\d+)px; "
        r"--sr: (-?\d+)deg; --i: (\d+); \}", css)
    assert len(rules) == len(tools.TOOLS)
    assert [int(r[0]) for r in rules] == list(range(2, len(tools.TOOLS) + 2))  # core <g> is the first <g>
    slots = [(56, 50), (168, 50), (280, 50), (392, 50), (504, 50), (56, 150), (168, 150), (392, 150),
             (504, 150), (112, 250), (224, 250), (336, 250), (448, 250)]
    for (_, sx, sy, _sr, _i), (x, y) in zip(rules, slots):
        # the START position (slot + offset) must lie inside the 560x300 viewBox, or it is clipped
        assert 0 <= x + int(sx) <= 560 and 0 <= y + int(sy) <= 300, (x, y, sx, sy)
    assert len({r[1:4] for r in rules}) == len(rules)  # not all the same scatter


def test_tool_settle_markup_has_the_core_first_then_one_g_per_tool(client):
    """:nth-of-type(k + 2) in the CSS relies on this order."""
    html = _page(client)
    svg = html[html.index('<svg class="tool-grid"'):]
    svg = svg[:svg.index("</svg>\n</div>") if "</svg>\n</div>" in svg else None]
    top = re.findall(r'<g class="(tool-grid__core|tool)"', svg)
    assert top[0] == "tool-grid__core" and top[1:] == ["tool"] * len(tools.TOOLS)


def test_tool_settle_css_has_the_keyframes_and_a_reduced_motion_block(client):
    css = client.get("/static/css/toolweb.css").get_data(as_text=True)
    assert "@keyframes tool-settle" in css
    block = re.search(r"@media \(prefers-reduced-motion: reduce\) \{\s*\.tool-grid \.tool__mark \{([^}]*)\}", css)
    assert block, "no reduced-motion block for the tool marks"
    assert "animation: none" in block.group(1) and "transform: none" in block.group(1)
    # the animation targets the inner group, never the positioned outer one
    assert ".tool-grid.is-settling .tool__mark" in css
    assert not re.search(r"\.tool-grid\.is-settling \.tool\s*\{", css)


def test_tool_settle_script_only_adds_the_classes_behind_the_reduced_motion_check(client):
    js = client.get("/static/js/toolweb.js").get_data(as_text=True)
    fn = js[js.index("function armToolSettle"):]
    assert fn.index("REDUCE_MOTION") < fn.index('classList.add("is-scattered")')
    assert fn.index("REDUCE_MOTION") < fn.index('classList.add("is-settling")')
    assert "IntersectionObserver" in fn and "observer.disconnect()" in fn  # plays once
    assert "the site's ONE animation" not in js


def test_tool_settle_adds_no_script_file(client):
    html = _page(client)
    assert re.findall(r'<script[^>]+src="([^"]+)"', html) == \
        re.findall(r'<script[^>]+src="([^"]+)"', client.get("/job-engine").get_data(as_text=True))


def test_tool_settle_has_a_failsafe_and_a_print_rule_so_nothing_stays_invisible(client):
    js = client.get("/static/js/toolweb.js").get_data(as_text=True)
    assert "setTimeout(settle" in js
    css = client.get("/static/css/toolweb.css").get_data(as_text=True)
    assert re.search(r"@media print \{\s*\.tool-grid \.tool__mark \{[^}]*opacity: 1", css)
