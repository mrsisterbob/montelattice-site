"""The resume route alerts Kevin through leads.send, never blocks the PDF, never leaks the visitor."""
import pytest

import homepage
import leads
import main
import resume_alert

BANK = {"identity": {"name": "K"}, "site_profile": {}}
BROWSER = "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 Chrome/120 Safari/537.36"
PDF = b"%PDF-1.7 test"
ROUTE = f"/resume/{main.RESUME_PDF}"


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setattr(homepage, "load_bank", lambda: BANK)
    (tmp_path / main.RESUME_PDF).write_bytes(PDF)
    monkeypatch.setattr(main.app, "static_folder", str(tmp_path))
    monkeypatch.setattr(resume_alert, "notify", _real_notify)
    resume_alert._seen.clear()
    sent = []

    def rec(lead):
        sent.append(lead)
        return True, ""
    monkeypatch.setattr(leads, "send", rec)
    return main.app.test_client(), sent, monkeypatch


_real_notify = resume_alert.notify  # captured at import, before conftest patches it per test


def _get(c, ua=BROWSER, ip="1.2.3.4", method="get"):
    h = {"X-Forwarded-For": ip}
    if ua is not None:
        h["User-Agent"] = ua
    return getattr(c, method)(ROUTE, headers=h)


def _wait(t):
    for th in __import__("threading").enumerate():
        if th is not __import__("threading").current_thread() and th.daemon:
            th.join(2)


def test_browser_get_sends_one_lead_and_returns_pdf(env):
    c, sent, _ = env
    r = _get(c)
    _wait(None)
    assert r.status_code == 200 and r.data == PDF
    assert len(sent) == 1
    assert sent[0]["source"] == "montelattice.com/resume" and sent[0]["name"] == "R\u00e9sum\u00e9 download"
    assert sent[0]["email"] == "resume-download@montelattice.com"


def test_lead_has_no_ip_or_user_agent(env):
    c, sent, _ = env
    _get(c, ip="9.8.7.6")
    _wait(None)
    text = " ".join(str(v) for v in sent[0].values())
    assert "9.8.7.6" not in text and "127.0.0.1" not in text and "Mozilla" not in text and "Chrome" not in text


@pytest.mark.parametrize("ua", ["Googlebot/2.1", "curl/8.0", "python-requests/2.31", "Slackbot-LinkExpanding",
                                "Mozilla HeadlessChrome/120", "WhatsApp link preview", ""])
def test_bots_and_empty_ua_send_nothing(env, ua):
    c, sent, _ = env
    r = _get(c, ua=ua)
    _wait(None)
    assert r.status_code == 200 and r.data == PDF and sent == []


def test_head_sends_nothing(env):
    c, sent, _ = env
    r = _get(c, method="head")
    _wait(None)
    assert r.status_code == 200 and sent == []


def test_signed_in_session_sends_nothing(env):
    c, sent, _ = env
    with c.session_transaction() as s:
        s["console_authed"] = True
    r = _get(c)
    _wait(None)
    assert r.status_code == 200 and r.data == PDF and sent == []


def test_same_ip_within_ten_minutes_is_silent_other_ip_alerts(env):
    c, sent, mp = env
    clock = [1000.0]
    mp.setattr(resume_alert, "_now", lambda: clock[0])
    _get(c); _wait(None)
    clock[0] += 599
    _get(c); _wait(None)
    assert len(sent) == 1
    _get(c, ip="5.5.5.5"); _wait(None)
    assert len(sent) == 2
    clock[0] += 2
    _get(c); _wait(None)
    assert len(sent) == 3


def test_memory_is_bounded_and_not_raw_ip(env):
    _, _, mp = env
    mp.setattr(resume_alert, "_MAX_REMEMBERED", 5)
    for i in range(20):
        resume_alert._repeat(f"10.0.0.{i}")
    assert len(resume_alert._seen) <= 5
    assert not any("10.0.0." in k for k in resume_alert._seen)


@pytest.mark.parametrize("mode", ["raise", "false"])
def test_failed_send_still_serves_pdf(env, mode):
    c, _, mp = env

    def bad(lead):
        if mode == "raise":
            raise RuntimeError("boom")
        return False, ""
    mp.setattr(leads, "send", bad)
    r = _get(c)
    _wait(None)
    assert r.status_code == 200 and r.data == PDF


def test_notify_raising_still_serves_pdf(env):
    c, _, mp = env

    def boom(request, session):
        raise RuntimeError("x")
    mp.setattr(resume_alert, "notify", boom)
    r = _get(c)
    assert r.status_code == 200 and r.data == PDF


def test_missing_pdf_is_404_and_silent(env, tmp_path):
    c, sent, mp = env
    empty = tmp_path / "empty"
    empty.mkdir()
    mp.setattr(main.app, "static_folder", str(empty))
    r = _get(c)
    _wait(None)
    assert r.status_code == 404 and sent == []


def test_home_links_to_route_twice_not_static(env):
    c, _, _ = env
    html = c.get("/").get_data(as_text=True)
    assert html.count(f'href="{ROUTE}"') == 2
    assert "/static/kevin-miller-resume.pdf" not in html


def test_response_sets_no_cookie(env):
    c, _, _ = env
    r = _get(c)
    assert r.status_code == 200 and "Set-Cookie" not in r.headers
