"""/job-engine reads like an app dashboard: four number cards, the charts directly beneath them
side by side, then the remaining tiles, the drafting card and Conversion. Run: python -m pytest tests -q
"""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import jobstats  # noqa: E402
import main  # noqa: E402
from test_job_dashboard import FULL  # noqa: E402

PAYLOAD = dict(FULL, funnel={"replies": 2, "interviews": 1, "offers": 0, "reply_rate_pct": 2.4,
                             "interview_rate_pct": 1.2, "offer_rate_pct": 0.0})


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("PUBLIC_FUNNEL_STATS", "true")
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setattr(jobstats, "fetch", lambda: PAYLOAD)
    return main.app.test_client()


@pytest.fixture
def html(client):
    r = client.get("/job-engine")
    assert r.status_code == 200
    return r.get_data(as_text=True)


def test_layout_order_four_cards_then_charts_then_the_rest(html):
    four = html.index("kpi-row kpi-row--4")
    charts = html.index('class="data-card dash-charts"')
    volume = html.index('id="chart-volume"')
    flow = html.index('<svg class="pipeline-flow"')
    three = html.index("kpi-row kpi-row--3")
    drafting = html.index("dash-drafting")
    conversion = html.index("Conversion</h2>")
    assert four < charts < volume < three
    assert charts < flow < three
    assert three < drafting < conversion


def test_layout_both_charts_are_inside_the_charts_wrapper(html):
    start = html.index('class="data-card dash-charts"')
    end = html.index("kpi-row kpi-row--3")
    wrapper = html[start:end]
    assert 'id="chart-volume"' in wrapper and '<svg class="pipeline-flow"' in wrapper
    assert 'id="volume-data"' in wrapper  # the Chart.js data script travels with its canvas


def test_layout_chart_js_wiring_is_intact_and_sizes_to_its_box(html):
    assert "document.getElementById('chart-volume')" in html
    assert "maintainAspectRatio: false" in html
    assert 'class="dash-chart-box"' in html


def test_layout_css_defines_the_charts_grid_with_a_narrow_screen_rule(client):
    css = client.get("/static/css/rapture.css").get_data(as_text=True)
    m = re.search(r"\.dash \.data-card\.dash-charts \{([^}]*)\}", css)
    assert m and "display: grid" in m.group(1) and "repeat(auto-fit" in m.group(1)
    assert re.search(r"@media \(max-width: 640px\) \{\s*\.dash \.data-card\.dash-charts \{[^}]*grid-template-columns: 1fr", css)
    assert re.search(r"\.dash-chart-box \{[^}]*height:", css)


def test_layout_new_css_uses_tokens_only(client):
    css = client.get("/static/css/rapture.css").get_data(as_text=True)
    block = css[css.index("/* App-dashboard layout"):css.index(".dash canvas { max-height: 260px; }")]
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", block)


def test_layout_empty_and_stale_states_are_untouched(client, monkeypatch):
    monkeypatch.setattr(jobstats, "fetch", lambda: None)
    html = client.get("/job-engine").get_data(as_text=True)
    assert "not reachable" in html and "dash-charts" not in html
    monkeypatch.setattr(jobstats, "fetch", lambda: dict(PAYLOAD, stale=True))
    assert "showing the last copy received" in client.get("/job-engine").get_data(as_text=True)
