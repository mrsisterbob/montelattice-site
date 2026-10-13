"""Two /lattice cards carry one measured number each, from the engine feed and the build snapshot;
every other card, and any card whose figure is unavailable, carries none. Run: python -m pytest tests -q
"""
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import buildstats  # noqa: E402
import homepage  # noqa: E402
import jobstats  # noqa: E402
import main  # noqa: E402
import outcomes  # noqa: E402

BANK = {"identity": {"name": "K"}, "site_profile": {"resume_note": "Available on request, tailored to the role."}}
BUILD = {"commit_hours": 900, "tracked_lines": 56789, "repo_count": 4,
         "generated_at": datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setenv("PUBLIC_CRYPTO", "true")
    monkeypatch.setattr(homepage, "load_bank", lambda: BANK)
    monkeypatch.setattr(jobstats, "fetch", lambda: {"status": "ok", "applications_sent": 1234})
    monkeypatch.setattr(buildstats, "load", lambda *a, **k: BUILD)
    return main.app.test_client()


def _cards(html):
    return {href: re.sub(r"<[^>]+>", " ", body) for href, body in
            re.findall(r'<a class="card" href="([^"]+)">(.*?)</a>', html, re.S)}


def _html(client):
    r = client.get("/lattice")
    assert r.status_code == 200
    return r.get_data(as_text=True)


def test_outcomes_engine_card_shows_applications_sent(client):
    body = _cards(_html(client))["/job-engine"]
    assert "1,234" in body and "Applications sent" in body and "logged in the CRM" in body


def test_outcomes_site_card_shows_tracked_lines_across_all_repos_with_its_date(client):
    body = _cards(_html(client))["/code"]
    assert "56,789" in body and "across 4 repos" in body and "As of Oct 9" in body


def test_outcomes_cards_without_a_measured_figure_carry_no_number(client):
    cards = _cards(_html(client))
    for href in ("/docfiler", "/budget", "/crypto"):
        assert href in cards
        assert not re.search(r"[0-9]", cards[href]), href
        assert "card__figure" not in cards[href]


def test_outcomes_nothing_is_shown_when_both_sources_are_unavailable(client, monkeypatch):
    monkeypatch.setattr(jobstats, "fetch", lambda: None)
    monkeypatch.setattr(buildstats, "load", lambda *a, **k: None)
    html = _html(client)
    for href, body in _cards(html).items():
        assert not re.search(r"[0-9]", body), href
    assert "card__figure" not in html.replace(".card__figure", "").replace("card__figure-", "")


def test_outcomes_zero_applications_shows_no_figure(client, monkeypatch):
    monkeypatch.setattr(jobstats, "fetch", lambda: {"status": "ok", "applications_sent": 0})
    body = _cards(_html(client))["/job-engine"]
    assert "Applications sent" not in body and not re.search(r"[0-9]", body)
    assert "56,789" in _cards(_html(client))["/code"]  # the other card is independent


def test_outcomes_the_card_anchor_is_unchanged(client):
    html = _html(client)
    assert len(re.findall(r'<a class="card" href="[^"]+">', html)) == len(_cards(html)) == 5


def test_outcomes_card_figures_is_pure_and_keyed_by_href():
    assert outcomes.card_figures(None, None) == {}
    got = outcomes.card_figures({"applications_sent": 82}, BUILD)
    assert set(got) == {"/job-engine", "/code"}
    assert outcomes.card_figures({"applications_sent": None}, {"tracked_lines": 5}) == {}
    assert outcomes.card_figures({"applications_sent": True}, None) == {}


def test_outcomes_css_uses_tokens_only(client):
    css = client.get("/static/css/rapture.css").get_data(as_text=True)
    block = css[css.index(".card__figure {"):css.index("/* Project status pill")]
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", block)


def test_outcomes_a_stale_engine_copy_is_not_shown_as_current(client, monkeypatch):
    monkeypatch.setattr(jobstats, "fetch", lambda: {"status": "ok", "applications_sent": 1234, "stale": True})
    body = _cards(_html(client))["/job-engine"]
    assert "Applications sent" not in body and not re.search(r"[0-9]", body)


def test_outcomes_one_repo_is_singular(client, monkeypatch):
    monkeypatch.setattr(buildstats, "load", lambda *a, **k: dict(BUILD, repo_count=1))
    assert "across 1 repo " in _cards(_html(client))["/code"] + " "
