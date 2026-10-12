"""Live figures say how they refresh, and the number comes from the two cache lifetimes rather
than being typed into a template. Run: python -m pytest tests -q
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import jobstats  # noqa: E402
import main  # noqa: E402

PAYLOAD = {
    "status": "ok", "as_of": "2026-10-12",
    "roles_screened": 120, "listings_discovered": 400, "applications_sent": 7,
    "drafting": {"median_ms": 151.2, "runs": 3, "measured_at": "2026-09-26T19:39:15Z",
                 "steps": ["resume PDF", "cover letter PDF", "email body"]},
}
PAGES = ["/lattice", "/job-engine"]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("PUBLIC_FUNNEL_STATS", raising=False)
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    return main.app.test_client()


def _feed(monkeypatch, payload):
    monkeypatch.setattr(jobstats, "fetch", lambda: payload)


@pytest.mark.parametrize("path", PAGES)
def test_live_cadence_label_states_both_real_lifetimes_by_default(client, monkeypatch, path):
    _feed(monkeypatch, PAYLOAD)
    html = client.get(path).get_data(as_text=True)
    assert "These update themselves" in html
    assert "every 15 minutes" in html
    assert "at most every 5 minutes" in html


@pytest.mark.parametrize("path", PAGES)
def test_live_cadence_numbers_come_from_the_constants_not_the_template(client, monkeypatch, path):
    _feed(monkeypatch, PAYLOAD)
    monkeypatch.setattr(jobstats, "TTL_SECONDS", 600)
    monkeypatch.setattr(jobstats, "ENGINE_FEED_TTL_SECONDS", 1800)
    html = client.get(path).get_data(as_text=True)
    assert "every 30 minutes" in html
    assert "at most every 10 minutes" in html
    assert "every 15 minutes" not in html


@pytest.mark.parametrize("path", PAGES)
def test_live_cadence_label_is_absent_when_the_feed_is_not_answering(client, monkeypatch, path):
    _feed(monkeypatch, None)
    html = client.get(path).get_data(as_text=True)
    assert "These update themselves" not in html
    assert "not answering" in html or "not reachable" in html


def test_live_cadence_wording_handles_other_units():
    assert jobstats._every(90) == "90 seconds"
    assert jobstats._every(60) == "1 minute"
    assert jobstats._every(3600) == "1 hour"
    assert jobstats._every(7200) == "2 hours"


@pytest.mark.parametrize("path", PAGES)
def test_live_cadence_label_says_the_two_caches_stack(client, monkeypatch, path):
    _feed(monkeypatch, PAYLOAD)
    assert "up to 20 minutes old" in client.get(path).get_data(as_text=True)


@pytest.mark.parametrize("path", PAGES)
def test_live_cadence_label_is_absent_over_a_stale_copy(client, monkeypatch, path):
    _feed(monkeypatch, dict(PAYLOAD, stale=True))
    html = client.get(path).get_data(as_text=True)
    assert "These update themselves" not in html
    assert "Raw data" in html or "Roles Screened" in html  # the figures themselves still show


def test_live_cadence_with_caching_off_says_every_page_load(monkeypatch):
    monkeypatch.setattr(jobstats, "TTL_SECONDS", 0)
    label = jobstats.cadence_label()
    assert "on every page load" in label and "0 seconds" not in label
