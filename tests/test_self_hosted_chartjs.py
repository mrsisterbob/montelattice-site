"""Chart.js is served from static/js/vendor at a pinned version; no page loads it from a CDN.
Run: python -m pytest tests -q
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

# "/" (profile.html) does not extend base.html and loads no Chart.js.
PAGES = ["/lattice", "/job-engine", "/docfiler", "/budget", "/code", "/crypto", "/console/demo"]
CHART_SRC = re.compile(r'<script[^>]+src="([^"]*js/vendor/chart-(4\.\d+\.\d+)\.umd\.min\.js)"')


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setattr(homepage, "load_bank", lambda: BANK)
    return main.app.test_client()


@pytest.mark.parametrize("path", PAGES)
def test_chartjs_self_hosted_page_has_one_local_script_and_no_cdn(client, path):
    r = client.get(path)
    assert r.status_code == 200, path
    html = r.get_data(as_text=True)
    assert "cdn.jsdelivr.net" not in html
    assert len(CHART_SRC.findall(html)) == 1
    assert len(re.findall(r"<script[^>]+src=[^>]*chart", html, re.I)) == 1


@pytest.mark.parametrize("path", PAGES)
def test_chartjs_self_hosted_script_is_served_at_its_pinned_version(client, path):
    html = client.get(path).get_data(as_text=True)
    src, version = CHART_SRC.search(html).groups()
    r = client.get(src)
    assert r.status_code == 200
    assert len(r.data) > 100_000
    assert f"Chart.js v{version}".encode() in r.data


def test_chartjs_self_hosted_script_stays_synchronous(client):
    # Inline scripts on the console pages call new Chart(...) and expect the global to exist.
    html = client.get("/lattice").get_data(as_text=True)
    tag = re.search(r"<script[^>]+js/vendor/chart-[^>]*>", html).group(0)
    assert "defer" not in tag and "async" not in tag
