"""Every public page opens dark whatever the OS prefers (2026-10-13: Kevin chose dark as the
default; before that every page opened light). The Flask test client cannot see a browser's OS
preference, so this proves the pages carry no OS-following rule at all; tests/test_dark_default.py
measures the default in a real browser. Run: python -m pytest tests -q
"""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import homepage  # noqa: E402
import main  # noqa: E402

BANK = {"identity": {"name": "K"}, "site_profile": {"resume_note": "Available on request, tailored to the role."}}
OS_RULE = "prefers-color-scheme: dark"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setattr(homepage, "load_bank", lambda: BANK)
    return main.app.test_client()


def _assets(client, html):
    srcs = re.findall(r'<link[^>]+rel="stylesheet"[^>]+href="([^"]+)"', html)
    srcs += re.findall(r'<script[^>]+src="([^"]+)"', html)
    out = {}
    for src in srcs:
        if src.startswith("/"):
            r = client.get(src)
            assert r.status_code == 200, src
            out[src] = r.get_data(as_text=True)
    return out


@pytest.mark.parametrize("path", ["/", "/lattice", "/job-engine", "/docfiler", "/budget", "/code", "/crypto", "/console/demo"])
def test_theme_default_nothing_a_page_serves_follows_the_os_dark_preference(client, path):
    html = client.get(path).get_data(as_text=True)
    assert OS_RULE not in html
    assets = _assets(client, html)
    assert any(name.endswith("tokens.css") for name in assets)
    for name, body in assets.items():
        assert OS_RULE not in body, name


def test_theme_default_dark_is_still_available_by_explicit_choice(client):
    tokens = client.get("/static/css/tokens.css").get_data(as_text=True)
    assert ':root[data-theme="dark"]' in tokens
    assert ':root[data-theme="light"]' in tokens


def test_theme_default_toggle_with_no_stored_choice_goes_to_light_first(client):
    js = client.get("/static/js/site.js").get_data(as_text=True)
    assert 'if (!current) current = "dark";' in js
    assert "prefers-color-scheme" not in js
    assert 'if (!current) current = "dark";' in client.get("/").get_data(as_text=True)
