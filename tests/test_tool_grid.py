"""/lattice shows one inline SVG: the M mark with the engine's tool logos around it, drawn only
from tools.py, themed by tokens, and adding no script. Run: python -m pytest tests -q
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
M_PATH = "M6 24V9h3l7 9 7-9h3v15h-3.2V14.2L16 22.4 9.2 14.2V24Z"
EXCLUDED = ("Apollo", "Jooble", "LinkedIn", "Indeed", "Workable", "SmartRecruiters")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setattr(homepage, "load_bank", lambda: BANK)
    monkeypatch.setattr(main.jobstats, "fetch", lambda: None)
    return main.app.test_client()


@pytest.fixture
def html(client):
    r = client.get("/lattice")
    assert r.status_code == 200
    return r.get_data(as_text=True)


def test_tool_grid_has_exactly_one_group_per_tools_py_entry(html):
    shown = re.findall(r'data-tool="([^"]+)"', html)
    assert sorted(shown) == sorted(t.name for t in tools.TOOLS)
    assert len(shown) == len(set(shown))


def test_tool_grid_is_one_svg_with_the_m_mark_and_an_accessible_name(html):
    svgs = re.findall(r'<svg class="tool-grid"[^>]*>', html)
    assert len(svgs) == 1
    assert 'role="img"' in svgs[0] and "aria-label=" in svgs[0]
    assert M_PATH in html
    assert "<title>The Monte Lattice mark" in html


def test_tool_grid_groups_keep_position_outside_and_drawing_inside(html):
    groups = re.findall(r'<g class="tool" data-tool="[^"]+" transform="translate\([\d.]+ [\d.]+\)">\s*<g class="tool__mark">', html)
    assert len(groups) == len(tools.TOOLS)


def test_tool_grid_a_tool_without_a_mark_is_its_name_as_text(html):
    for tool in tools.TOOLS:
        if tool.svg_path is None:
            assert f'<text class="tool__wordmark" y="6">{tool.name}</text>' in html, tool.name
        else:
            assert tool.svg_path in html, tool.name


def test_tool_grid_names_no_excluded_service(html):
    for name in EXCLUDED:
        assert name.lower() not in html.lower(), name


def test_tool_grid_adds_no_script(client, html):
    srcs = re.findall(r'<script[^>]+src="([^"]+)"', html)
    assert srcs and all(s.startswith("/static/") for s in srcs), srcs
    base = client.get("/job-engine").get_data(as_text=True)  # same base.html, no grid
    assert srcs == re.findall(r'<script[^>]+src="([^"]+)"', base)
    grid = html[html.index('<svg class="tool-grid"'):html.index("</svg>", html.index('<svg class="tool-grid"'))]
    assert "<script" not in grid and "onload" not in grid


def test_tool_grid_css_block_uses_tokens_only(client):
    css = client.get("/static/css/rapture.css").get_data(as_text=True)
    start = css.index("/* --- Tool grid")
    end = css.index("/* --- Project card grid")
    block = css[start:end]
    assert ".tool-grid" in block and ".tool__mark" in block
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", block)
    assert "var(--" in block
