"""The DocFiler contact form: the submitter is thanked ONLY when the job engine confirms the write.
Every failure must say so and give an address to email instead. Run: python -m pytest tests -q
"""
import io
import json
import logging
import queue
import socket
import sys
import urllib.error
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import homepage  # noqa: E402
import jobstats  # noqa: E402
import leads  # noqa: E402
import main  # noqa: E402
import visits  # noqa: E402

THANKS = "Thanks - I'll be in touch shortly."
FALLBACK = "kevin.miller@montelattice.com"
LEAD = {"name": "Dana Ruiz", "email": "dana@firm.com", "message": "40k PDFs across 3 offices"}


class _Resp:
    def __init__(self, status, body):
        self.status = status
        self._body = body if isinstance(body, bytes) else json.dumps(body).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def engine(monkeypatch):
    """Stub the network at urllib.request.urlopen. Set engine['reply'] to a _Resp or an
    exception; every request the route makes is recorded in engine['calls']."""
    monkeypatch.setenv("LEAD_INGEST_TOKEN", "lead-t")
    monkeypatch.delenv("LEAD_FALLBACK_EMAIL", raising=False)
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setattr(visits, "_QUEUE", queue.Queue(maxsize=1000))
    state = {"reply": _Resp(200, {"status": "ok", "id": 7}), "calls": []}

    def fake_urlopen(req, timeout=None):
        state["calls"].append({"url": req.full_url, "headers": dict(req.header_items()),
                               "body": json.loads(req.data), "timeout": timeout})
        if isinstance(state["reply"], BaseException):
            raise state["reply"]
        return state["reply"]

    monkeypatch.setattr(leads.urllib.request, "urlopen", fake_urlopen)
    return state


def _submit(payload=LEAD):
    return main.app.test_client().post("/api/docfiler/contact", json=payload)


def _http_error(code, body=b"{}"):
    return urllib.error.HTTPError("https://engine/leads/ingest", code, "err", {}, io.BytesIO(body))


def test_confirmed_write_thanks_the_submitter_and_sends_the_lead(engine):
    r = _submit()
    assert r.status_code == 200 and r.get_json()["message"] == THANKS
    (call,) = engine["calls"]
    assert call["url"] == f"{jobstats.ENGINE_URL}/leads/ingest"
    assert call["headers"]["X-lead-token"] == "lead-t"
    assert call["body"] == {**LEAD, "source": "montelattice.com/docfiler"}
    assert call["timeout"] and call["timeout"] <= 10


@pytest.mark.parametrize("reply", [
    socket.timeout("timed out"),
    TimeoutError("timed out"),
    urllib.error.URLError(ConnectionRefusedError(10061, "refused")),
    ConnectionResetError(10054, "reset"),
    _http_error(500),
    _http_error(502),
    _http_error(503, b'{"status": "disabled"}'),
    _http_error(403, b'{"status": "forbidden"}'),
    _Resp(200, {"status": "error"}),
    _Resp(200, {"status": "ok"}),            # no row id: not a confirmed write
    _Resp(200, b"<html>Render is waking up</html>"),
    _Resp(204, {"status": "ok", "id": 3}),
], ids=["socket-timeout", "timeout", "refused", "reset", "500", "502", "503-no-token", "403-bad-secret",
        "status-error", "no-id", "html", "204"])
def test_any_engine_failure_is_honest_and_never_thanks(engine, reply, caplog):
    engine["reply"] = reply
    with caplog.at_level(logging.ERROR):
        r = _submit()
    body = r.get_json()
    assert r.status_code == 502
    assert "message" not in body and "Thanks" not in r.get_data(as_text=True)
    assert "did not go through" in body["error"] and FALLBACK in body["error"]
    # The lead survives in the log, so it can be recovered even though nothing stored it.
    logged = caplog.text
    assert "LEAD NOT STORED" in logged and "dana@firm.com" in logged and "40k PDFs" in logged


def test_engine_validation_error_is_passed_through_with_the_fallback(engine):
    engine["reply"] = _http_error(400, b'{"status": "invalid", "error": "A valid email address is required."}')
    r = _submit()
    assert r.status_code == 400
    err = r.get_json()["error"]
    assert err.startswith("A valid email address is required.") and FALLBACK in err


def test_no_token_on_the_site_means_no_send_and_no_thanks(engine, monkeypatch):
    monkeypatch.delenv("LEAD_INGEST_TOKEN")
    r = _submit()
    assert r.status_code == 502 and FALLBACK in r.get_json()["error"]
    assert engine["calls"] == []


def test_fallback_address_is_configurable(engine, monkeypatch):
    monkeypatch.setenv("LEAD_FALLBACK_EMAIL", "other@example.com")
    engine["reply"] = _http_error(500)
    assert "other@example.com" in _submit().get_json()["error"]


@pytest.mark.parametrize("payload", [
    {"email": "dana@firm.com"}, {"name": "Dana"}, {"name": "  ", "email": "dana@firm.com"}, {},
])
def test_missing_name_or_email_is_a_400_and_never_reaches_the_engine(engine, payload):
    r = _submit(payload)
    assert r.status_code == 400 and r.get_json() == {"error": "Name and email are required."}
    assert engine["calls"] == []


def test_nothing_is_written_to_the_ephemeral_disk(engine):
    _submit()
    assert not (ROOT / "docfiler_leads.txt").exists()


# ---- Profile: the phone is a tel: link like the email and LinkedIn beside it ----

def test_profile_phone_is_a_tel_link_with_the_display_unchanged(monkeypatch):
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setattr(homepage, "load_bank", lambda: {"identity": {"name": "K", "phone": "248-709-6326",
                                                                     "site_email": "k@x.com"}})
    html = main.app.test_client().get("/").get_data(as_text=True)
    assert '<a class="line-v" href="tel:2487096326">248-709-6326</a>' in html


def test_tel_href_keeps_a_leading_plus_and_drops_punctuation():
    assert homepage.build_profile({"identity": {"phone": "+1 (248) 709.6326"}})["phone_tel"] == "tel:+12487096326"


def test_form_page_carries_the_fallback_for_failures_the_api_cannot_describe(engine):
    # A proxy error page or a dropped connection never reaches the API's JSON error, so the page
    # itself must hold the address the visitor is told to use instead.
    html = main.app.test_client().get("/docfiler").get_data(as_text=True)
    assert f'data-fallback="{FALLBACK}"' in html
