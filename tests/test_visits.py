"""The pageview hook: queues real pageviews for the engine, never fails or slows a request, and
sets no cookie. Run: python -m pytest tests -q
"""
import queue
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import jobstats  # noqa: E402
import main  # noqa: E402
import visits  # noqa: E402

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0.0.0 Safari/537.36"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ANALYTICS_ENABLED", "true")
    monkeypatch.setenv("ANALYTICS_INGEST_TOKEN", "t")
    monkeypatch.setattr(visits, "_QUEUE", queue.Queue(maxsize=1000))
    monkeypatch.setattr(visits, "_ensure_worker", lambda: None)
    monkeypatch.setattr(jobstats, "fetch", lambda: None)
    return main.app.test_client()


def _queued():
    return visits.drain(wait=0.05)


def test_pageview_is_queued_with_forwarded_ip_and_referrer(client):
    r = client.get("/lattice", headers={"User-Agent": UA, "Referer": "https://www.linkedin.com/feed/",
                                        "X-Forwarded-For": "192.0.2.7, 10.0.0.1"})
    assert r.status_code == 200
    (view,) = _queued()
    assert view["path"] == "/lattice" and view["ip"] == "192.0.2.7" and view["self"] is False
    assert view["referrer"] == "https://www.linkedin.com/feed/"


def test_assets_and_api_calls_are_not_pageviews(client):
    client.get("/static/css/tokens.css")
    client.get("/api/crypto/summary")
    client.get("/favicon.ico")
    assert _queued() == []


def test_a_broken_hook_never_costs_the_visitor_the_page(client, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("queue exploded")
    monkeypatch.setattr(visits, "capture", boom)
    assert client.get("/lattice").status_code == 200


def test_a_full_buffer_drops_the_view_instead_of_blocking(client, monkeypatch):
    monkeypatch.setattr(visits, "_QUEUE", queue.Queue(maxsize=1))
    assert client.get("/lattice").status_code == 200
    assert client.get("/lattice").status_code == 200  # second view has nowhere to go
    assert len(_queued()) == 1


def test_disabled_collects_nothing(client, monkeypatch):
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    client.get("/lattice")
    assert _queued() == []


def test_without_the_shared_token_nothing_is_queued(client, monkeypatch):
    monkeypatch.delenv("ANALYTICS_INGEST_TOKEN")
    client.get("/lattice")
    assert _queued() == []


def test_no_cookie_is_set_for_a_visitor(client):
    r = client.get("/lattice", headers={"User-Agent": UA})
    assert "Set-Cookie" not in r.headers


def test_signed_in_console_session_is_flagged_self(client):
    with client.session_transaction() as s:
        s["console_authed"] = True
    client.get("/lattice")
    (view,) = _queued()
    assert view["self"] is True
