"""Every public page serves its type from this site's own static/ and requests no font host.
Run: python -m pytest tests/test_self_hosted_fonts.py -q
"""
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import homepage  # noqa: E402
import main  # noqa: E402

BANK = {"identity": {"name": "K"}, "site_profile": {"resume_note": "Available on request, tailored to the role."}}
PAGES = ["/", "/lattice", "/job-engine", "/docfiler", "/budget", "/code", "/crypto",
         "/console/demo", "/console/login"]
FAMILIES = ["Cormorant Garamond", "Inter", "JetBrains Mono"]
FONTS_CSS = "/static/css/fonts.css"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setattr(homepage, "load_bank", lambda: BANK)
    return main.app.test_client()


@pytest.mark.parametrize("path", PAGES)
def test_fonts_self_hosted_page_requests_no_font_host(client, path):
    r = client.get(path)
    assert r.status_code == 200, path
    html = r.get_data(as_text=True)
    assert "fonts.googleapis.com" not in html
    assert "fonts.gstatic.com" not in html
    assert "css/fonts.css" in html


def test_fonts_self_hosted_css_declares_every_family(client):
    css = client.get(FONTS_CSS).get_data(as_text=True)
    for family in FAMILIES:
        assert f'font-family: "{family}"' in css, family
    assert "display: swap" in css


def test_fonts_self_hosted_every_url_serves_a_woff2(client):
    css = client.get(FONTS_CSS).get_data(as_text=True)
    urls = re.findall(r'url\(\s*["\']?([^"\')]+)["\']?\s*\)', css)
    assert urls, "fonts.css references no font files"
    for url in urls:
        assert not url.startswith(("http:", "https:", "//")), url
        r = client.get(urljoin("/static/css/", url))
        assert r.status_code == 200, url
        assert r.data[:4] == b"wOF2", url
