"""The /job-engine dashboard and the /lattice teaser render only what the engine's feed says,
through the real Flask routes. Run: python -m pytest tests -q
"""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import jobstats  # noqa: E402
import main  # noqa: E402

# Exactly what the engine's shape_public_dashboard() returns for an empty database with the
# CRM unreachable (see test_public_dashboard_empty_dataset_is_honest in the engine repo).
EMPTY = {
    "status": "ok", "roles_screened": 0, "listings_discovered": 0, "applications_sent": None,
    "days_running": None, "start_date": None, "live_conversations": 0,
    "dead_links": {"detected": 0, "retired": 0, "this_week": 0}, "median_fit_score": None,
    "scored_roles": 0, "tracks_total": 8, "tracks_used": 0, "documents_compiled": 0,
    "documents_since": None, "timeline": [], "drafting": None, "funnel": None, "as_of": "2026-09-26",
}

FULL = dict(EMPTY, **{
    "roles_screened": 1234, "listings_discovered": 5678, "applications_sent": 82, "days_running": 57,
    "live_conversations": 2, "dead_links": {"detected": 9, "retired": 7, "this_week": 3},
    "median_fit_score": 84.5, "scored_roles": 311, "tracks_used": 6, "documents_compiled": 14,
    "documents_since": "2026-09-26",
    "timeline": [{"week": "2026-09-14", "ai_screened": 40, "listing_discovered": 120}],
    "drafting": {"median_ms": 151.2, "runs": 3, "measured_at": "2026-09-26T19:39:15Z",
                 "steps": ["resume PDF", "cover letter PDF", "email body"]},
    "funnel": {"replies": 2, "interviews": 0, "offers": 0, "reply_rate_pct": 2.4,
               "interview_rate_pct": 0.0, "offer_rate_pct": 0.0},
})


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("PUBLIC_FUNNEL_STATS", raising=False)
    return main.app.test_client()


def _feed(monkeypatch, payload):
    monkeypatch.setattr(jobstats, "fetch", lambda: payload)


def _page(client, path="/job-engine"):
    r = client.get(path)
    assert r.status_code == 200
    return r.get_data(as_text=True)


def _values(html):
    return re.findall(r'<span class="kpi-value">([^<]*)</span>', html)


def test_empty_dataset_renders_honest_empty_states_not_numbers(client, monkeypatch):
    _feed(monkeypatch, EMPTY)
    html = _page(client)
    for sentence in ("No roles screened yet.", "CRM unreachable right now.",
                     "No open recruiter threads right now.", "No dead links detected yet.",
                     "No scored roles yet.", "None since counting began.",
                     "No cached role to time against yet.",
                     "No pipeline activity logged in the last twelve weeks."):
        assert sentence in html, sentence
    assert _values(html) == ["0 of 8"]  # the one real figure: the registry has 8 tracks, none used yet
    assert 'id="chart-volume"' not in html


def test_unreachable_feed_renders_no_figures(client, monkeypatch):
    _feed(monkeypatch, None)
    html = _page(client)
    assert "feed is not reachable" in html
    assert _values(html) == []


def test_full_payload_renders_every_live_figure(client, monkeypatch):
    _feed(monkeypatch, FULL)
    html = _page(client)
    assert _values(html) == ["1,234", "82", "2", "7", "84.5", "6 of 8", "14"]
    assert "151.2 ms" in html and "resume PDF + cover letter PDF + email body" in html
    assert 'id="chart-volume"' in html
    assert jobstats.feed_url() in html  # the raw numbers are one click away


def test_funnel_hidden_by_default(client, monkeypatch):
    _feed(monkeypatch, FULL)
    html = _page(client)
    assert "Conversion" not in html
    for label in ("Replies", "Interviews", "Offers"):
        assert f'<span class="kpi-label">{label}</span>' not in html


def test_funnel_shown_when_flag_true(client, monkeypatch):
    _feed(monkeypatch, FULL)
    monkeypatch.setenv("PUBLIC_FUNNEL_STATS", "true")
    html = _page(client)
    assert "Conversion" in html
    assert "2.4% of applications" in html
    for label in ("Replies", "Interviews", "Offers"):
        assert f'<span class="kpi-label">{label}</span>' in html


def test_primary_and_secondary_rows_are_full_in_both_flag_states(client, monkeypatch):
    """The grid must read as finished with the funnel hidden: 4 + 3 tiles, no gaps."""
    _feed(monkeypatch, FULL)
    for flag in ("false", "true"):
        monkeypatch.setenv("PUBLIC_FUNNEL_STATS", flag)
        html = _page(client)
        rows = re.findall(r'<div class="kpi-row kpi-row--(\d)[^"]*">(.*?)</div>\s*(?=<div class="kpi-row|<div class="data-card|<h2)', html, re.S)
        assert [(n, r.count('class="kpi-tile"')) for n, r in rows[:2]] == [("4", 4), ("3", 3)]


def test_template_holds_no_hardcoded_figures():
    src = (ROOT / "templates" / "job_engine.html").read_text(encoding="utf-8")
    src = re.sub(r"\{#.*?#\}", "", src, flags=re.S)          # template comments
    src = re.sub(r"<script.*?</script>", "", src, flags=re.S)  # chart wiring
    src = re.sub(r'\b(height|width)="\d+"', "", src)           # canvas size
    src = re.sub(r"kpi-row--\d", "", src)                     # grid class names
    src = re.sub(r"</?h\d", "", src)                          # heading tag names
    assert re.findall(r"\d", src) == []


def test_benchmark_without_a_visible_source_is_refused():
    with pytest.raises(ValueError):
        jobstats._tile("Reply rate", "4%", cite={"value": "5-10%"})
    assert jobstats._tile("x", "1", cite={"value": "2", "source": "S", "url": "https://e.x"})["cite"]


def test_teaser_shows_live_figures_or_an_honest_line(client, monkeypatch):
    _feed(monkeypatch, FULL)
    html = _page(client, "/lattice")
    assert 'data-target="1234"' in html and 'data-target="82"' in html and 'data-target="151.2"' in html
    assert "Populates once" not in html and "Reply Rate" not in html
    _feed(monkeypatch, None)
    html = _page(client, "/lattice")
    assert "feed is not answering" in html and "data-count" not in html


def test_funnel_needs_the_engine_to_send_it_too(client, monkeypatch):
    """Site flag on, engine flag off: the payload has no funnel, so no Conversion section and
    no misleading 'CRM unreachable' line either."""
    _feed(monkeypatch, dict(FULL, funnel=None))
    monkeypatch.setenv("PUBLIC_FUNNEL_STATS", "true")
    html = _page(client)
    assert "Conversion" not in html and "CRM unreachable" not in html
