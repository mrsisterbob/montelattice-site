"""The /job-engine figures use the site's existing count-up, and still read as the real number
with JS off. Run: python -m pytest tests -q
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


def _values(html):
    return re.findall(r'<span class="kpi-value"([^>]*)>([^<]*)</span>', html)


def _attrs(raw):
    return dict(re.findall(r'(data-[\w-]+)(?:="([^"]*)")?', raw))


def test_countup_every_single_number_tile_carries_its_raw_target(client):
    html = client.get("/job-engine").get_data(as_text=True)
    tiles = {text: _attrs(raw) for raw, text in _values(html)}
    # Roles screened, applications, live conversations, dead links retired, fit, documents, and the
    # three funnel tiles. ("6 of 8" tracks is not a single number, so it is checked separately.)
    for text in ("1,234", "82", "2", "7", "84.5", "14", "1", "0"):
        assert text in tiles, text
    assert tiles["1,234"]["data-target"] == "1234"
    assert tiles["82"]["data-target"] == "82"
    assert tiles["84.5"]["data-target"] == "84.5"
    assert tiles["14"]["data-target"] == "14"
    for text, attrs in tiles.items():
        if "data-count" in attrs:
            assert "data-group" in attrs, text
            assert "data-target" in attrs, text


def test_countup_text_is_still_the_formatted_number_for_no_js(client):
    html = client.get("/job-engine").get_data(as_text=True)
    texts = [t for _, t in _values(html)]
    assert "1,234" in texts and "84.5" in texts
    assert "6 of 8" in texts
    assert all("data-count" not in raw for raw, t in _values(html) if t == "6 of 8")


def test_countup_drafting_time_keeps_its_unit(client):
    html = client.get("/job-engine").get_data(as_text=True)
    m = re.search(r'<span class="dash-drafting__value"([^>]*)>([^<]*)</span>', html)
    attrs = _attrs(m.group(1))
    assert m.group(2) == "151.2 ms"
    assert attrs["data-target"] == "151.2"
    assert re.search(r'data-suffix=" ms"', m.group(1))


def test_countup_page_arms_it_and_site_js_groups_thousands(client):
    html = client.get("/job-engine").get_data(as_text=True)
    assert "armCountUp()" in html
    js = client.get("/static/js/site.js").get_data(as_text=True)
    assert 'hasAttribute("data-group")' in js
    assert 'toLocaleString("en-US")' in js
    assert "job_engine" in js or "/job-engine" in js  # header comment names both pages


def test_countup_a_number_that_would_change_when_animated_is_not_animated():
    assert jobstats._target(84.0) == 84 and jobstats._target(84.5) == 84.5
    assert jobstats._target(84.55) is None
    assert jobstats._target(None) is None and jobstats._target(True) is None


def test_countup_lattice_strip_output_is_unchanged(client, monkeypatch):
    html = client.get("/lattice").get_data(as_text=True)
    assert "data-group" not in html
    assert 'data-count data-target="1234"' in html
