"""The footer line "This site sets no cookies and loads no trackers." is shown on every public
page, and for each page the test checks the browser-side half of it: no Set-Cookie, and no third-party resource
in the HTML or in the first-party stylesheets it links. It does NOT cover server-side visit
capture (visits.py records path, referrer, IP and User-Agent; ANALYTICS_ENABLED is off here), which
loads nothing in the visitor's browser. Run: python -m pytest tests -q
"""
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import homepage  # noqa: E402
import main  # noqa: E402

LINE = "This site sets no cookies and loads no trackers."
BANK = {"identity": {"name": "K"}, "site_profile": {"resume_note": "Available on request, tailored to the role."}}
WITH_LINE = ["/", "/lattice", "/job-engine", "/docfiler", "/budget", "/code", "/crypto", "/console/demo"]
CLEAN_ONLY = ["/console/login"]
LOAD_TAGS = {"script", "link", "img", "iframe", "video", "audio", "source", "embed", "object"}
LOAD_ATTRS = ("src", "href", "srcset", "poster")
ABSOLUTE = re.compile(r"^\s*(https?:)?//", re.I)
CSS_ABSOLUTE = re.compile(r"""(url\(\s*['"]?|@import\s+['"]?)\s*(https?:)?//""", re.I)


class _Loads(HTMLParser):
    def __init__(self):
        super().__init__()
        self.absolute = []
        self.stylesheets = []

    def handle_starttag(self, tag, attrs):
        if tag not in LOAD_TAGS:
            return
        a = dict(attrs)
        for name in LOAD_ATTRS:
            v = a.get(name)
            if not v:
                continue
            urls = [p.split()[0] for p in v.split(",") if p.strip()] if name == "srcset" else [v]
            for u in urls:
                if ABSOLUTE.match(u):
                    self.absolute.append((tag, name, u))
        if tag == "link" and "stylesheet" in (a.get("rel") or "").lower() and a.get("href") \
                and not ABSOLUTE.match(a["href"]):
            self.stylesheets.append(a["href"])


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setattr(homepage, "load_bank", lambda: BANK)
    return main.app.test_client()


def _assert_clean(client, path):
    r = client.get(path)
    assert r.status_code == 200, path
    assert "Set-Cookie" not in r.headers, path
    p = _Loads()
    p.feed(r.get_data(as_text=True))
    assert p.absolute == [], (path, p.absolute)
    for href in p.stylesheets:
        css = client.get(href)
        assert css.status_code == 200, (path, href)
        assert not CSS_ABSOLUTE.search(css.get_data(as_text=True)), (path, href)
    return r.get_data(as_text=True)


@pytest.mark.parametrize("path", WITH_LINE)
def test_privacy_line_shown_and_true(client, path):
    html = _assert_clean(client, path)
    assert html.count(LINE) == 1, path


@pytest.mark.parametrize("path", CLEAN_ONLY)
def test_privacy_line_login_page_is_clean(client, path):
    _assert_clean(client, path)


def test_privacy_line_hidden_when_signed_in(client):
    with client.session_transaction() as s:
        s["console_authed"] = True
    assert LINE not in client.get("/lattice").get_data(as_text=True)
    assert LINE not in client.get("/").get_data(as_text=True)


def test_privacy_line_on_profile_503_page(client, monkeypatch):
    monkeypatch.setattr(homepage, "load_bank", lambda: None)
    r = client.get("/")
    assert LINE in r.get_data(as_text=True)
