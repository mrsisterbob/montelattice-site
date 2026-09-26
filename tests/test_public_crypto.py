"""PUBLIC_CRYPTO hides the crypto engine from public surfaces without removing it, and every page
shares one token file. Driven through the real Flask app (test client), not helper return values.

Run: python -m pytest tests -q
"""
import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import main  # noqa: E402

PUBLIC_PAGES = ["/", "/lattice", "/job-engine", "/docfiler", "/budget", "/code", "/console/demo"]


@pytest.fixture
def client(tmp_path, monkeypatch):
    bank = {
        "identity": {"name": "Test Person", "phone": "555-0100"},
        "experience": [{"company": "Acme", "title": "Analyst", "start": "01/2025", "end": "02/2026",
                        "bullets": ["Did a thing."]}],
    }
    path = tmp_path / "bank.json"
    path.write_text(json.dumps(bank), encoding="utf-8")
    monkeypatch.setenv("EVIDENCE_BANK_SOURCE", str(path))
    return main.app.test_client()


def _html(client, path):
    r = client.get(path)
    assert r.status_code == 200, (path, r.status_code)
    return r.get_data(as_text=True)


def _hidden(monkeypatch):
    monkeypatch.delenv("PUBLIC_CRYPTO", raising=False)  # default must be hidden


def _shown(monkeypatch):
    monkeypatch.setenv("PUBLIC_CRYPTO", "true")


# --- hidden (default) ---------------------------------------------------------------------

def test_default_hides_crypto_from_every_public_nav_and_listing(client, monkeypatch):
    _hidden(monkeypatch)
    for path in PUBLIC_PAGES:
        assert 'href="/crypto"' not in _html(client, path), path
    assert "card-crypto" not in _html(client, "/lattice")
    assert "market monitoring" not in _html(client, "/lattice")
    assert "crypto-trading-engine" not in _html(client, "/code")


def test_hidden_crypto_route_still_serves_200_with_noindex(client, monkeypatch):
    _hidden(monkeypatch)
    html = _html(client, "/crypto")
    assert '<meta name="robots" content="noindex">' in html
    assert "What It Tracks" in html  # the page itself is intact


def test_homepage_still_describes_crypto_engine_but_without_a_link(client, monkeypatch):
    _hidden(monkeypatch)
    html = _html(client, "/")
    assert "Crypto Trading Engine" in html
    assert "WebSocket reconciliation feed" in html
    assert 'href="/crypto"' not in html


def test_hidden_demo_console_carries_no_crypto_figures(client, monkeypatch):
    _hidden(monkeypatch)
    html = _html(client, "/console/demo")
    for el in ('id="c-open"', 'id="k-pnl"', 'id="k-open"', 'id="chart-equity"'):
        assert el not in html, el
    snap = client.get("/api/console/snapshot?demo=1").get_json()
    assert "crypto" not in snap
    assert "realized_pnl_usd" not in snap["kpis"] and "open_positions" not in snap["kpis"]
    assert all(s["system"] != "Crypto" for s in snap["status"]["systems"])
    assert not any(k.startswith("crypto") for k in snap.get("trends", {}))


def test_hidden_api_route_still_works(client, monkeypatch):
    _hidden(monkeypatch)
    assert client.get("/api/crypto/summary").status_code == 200


# --- shown --------------------------------------------------------------------------------

def test_public_crypto_true_restores_everything(client, monkeypatch):
    _shown(monkeypatch)
    for path in ["/", "/lattice", "/job-engine", "/docfiler", "/budget", "/code"]:
        assert 'href="/crypto"' in _html(client, path), path
    assert "card-crypto" in _html(client, "/lattice")
    assert "market monitoring" in _html(client, "/lattice")
    assert "crypto-trading-engine" in _html(client, "/code")
    assert "noindex" not in _html(client, "/crypto")
    demo = _html(client, "/console/demo")
    assert 'id="c-open"' in demo and 'id="k-pnl"' in demo
    snap = client.get("/api/console/snapshot?demo=1").get_json()
    assert "crypto" in snap and any(s["system"] == "Crypto" for s in snap["status"]["systems"])


def test_flag_is_read_per_request_not_at_import(client, monkeypatch):
    _hidden(monkeypatch)
    assert 'href="/crypto"' not in _html(client, "/lattice")
    _shown(monkeypatch)
    assert 'href="/crypto"' in _html(client, "/lattice")


# --- design tokens ------------------------------------------------------------------------

HEX = re.compile(r"(?<![&\w])#[0-9a-fA-F]{3,8}\b")


def test_no_color_hex_outside_tokens_css():
    files = list((ROOT / "templates").glob("*.html")) + list((ROOT / "static" / "js").glob("*.js")) + [
        p for p in (ROOT / "static" / "css").glob("*.css") if p.name != "tokens.css"]
    stray = {str(p.relative_to(ROOT)): HEX.findall(p.read_text(encoding="utf-8")) for p in files}
    assert {k: v for k, v in stray.items() if v} == {}


@pytest.mark.parametrize("path", PUBLIC_PAGES + ["/crypto", "/console/login"])
def test_every_page_loads_tokens_before_its_own_stylesheet(client, monkeypatch, path):
    _shown(monkeypatch)
    html = _html(client, path)
    tokens = html.find("css/tokens.css")
    assert tokens != -1, path
    own = [html.find(f"css/{n}") for n in ("rapture.css", "profile.css") if f"css/{n}" in html]
    assert own and all(tokens < i for i in own), path


def test_dark_blocks_are_identical_and_light_is_complete():
    css = (ROOT / "static" / "css" / "tokens.css").read_text(encoding="utf-8")
    media = re.search(r':root:not\(\[data-theme="light"\]\) \{(.*?)\}', css, re.S).group(1)
    forced = re.search(r':root\[data-theme="dark"\] \{(.*?)\}', css, re.S).group(1)
    norm = lambda b: sorted(l.strip() for l in b.strip().splitlines() if l.strip())
    assert norm(media) == norm(forced)
    light = re.search(r"^:root \{(.*?)^\}", css, re.S | re.M).group(1)
    light_names = set(re.findall(r"(--[\w-]+):", light))
    dark_names = set(re.findall(r"(--[\w-]+):", media))
    assert dark_names <= light_names, dark_names - light_names  # never defined only in dark
    assert "color-scheme: dark" in media and "color-scheme: dark" in forced
