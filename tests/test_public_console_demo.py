"""PUBLIC_CONSOLE_DEMO hides the sample-data Console from public surfaces without removing it,
and leaves the signed-in Console untouched. Driven through the real Flask app (test client).

Run: python -m pytest tests -q
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import main  # noqa: E402

PUBLIC_PAGES = ["/", "/lattice", "/job-engine", "/docfiler", "/budget", "/code", "/crypto",
                "/console/login", "/console/demo"]
NAV_CONSOLE = '<span>Console</span>'
NOINDEX = '<meta name="robots" content="noindex">'
PASSWORD = "test-pass"


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
    monkeypatch.setattr(main, "SITE_PASSWORD", PASSWORD)
    return main.app.test_client()


def _html(client, path):
    r = client.get(path)
    assert r.status_code == 200, (path, r.status_code)
    return r.get_data(as_text=True)


def _hidden(monkeypatch):
    monkeypatch.delenv("PUBLIC_CONSOLE_DEMO", raising=False)  # default must be hidden


def _shown(monkeypatch):
    monkeypatch.setenv("PUBLIC_CONSOLE_DEMO", "true")


def _sign_in(client):
    r = client.post("/console/login", data={"password": PASSWORD})
    assert r.status_code == 302 and r.headers["Location"].endswith("/console")


# --- hidden (default) ---------------------------------------------------------------------

def test_default_drops_console_from_every_public_nav(client, monkeypatch):
    _hidden(monkeypatch)
    for path in PUBLIC_PAGES:
        html = _html(client, path)
        assert NAV_CONSOLE not in html, path
        assert 'href="/console/demo"' not in html, path


def test_default_leaves_no_public_link_that_lands_on_sample_data(client, monkeypatch):
    _hidden(monkeypatch)
    # Every /console link still on a public page (footer, body copy) must land on sign-in.
    r = client.get("/console")
    assert r.status_code == 302 and r.headers["Location"].endswith("/console/login")
    for path in PUBLIC_PAGES:
        assert 'class="site-footer__link" href="/console"' not in _html(client, path), path
    assert 'class="site-footer__link" href="/console/login"' in _html(client, "/lattice")


def test_hidden_demo_route_still_serves_200_with_noindex(client, monkeypatch):
    _hidden(monkeypatch)
    html = _html(client, "/console/demo")
    assert NOINDEX in html
    assert "Sample data" in html  # the page itself is intact
    assert client.get("/api/console/snapshot?demo=1").get_json()["demo"] is True


# --- shown --------------------------------------------------------------------------------

def test_public_console_demo_true_restores_everything(client, monkeypatch):
    _shown(monkeypatch)
    # "/" (the profile) has its own header and never linked the Console, so it is not listed.
    for path in ["/lattice", "/job-engine", "/docfiler", "/budget", "/code"]:
        html = _html(client, path)
        assert NAV_CONSOLE in html, path
        assert 'class="site-footer__link" href="/console"' in html, path
    logged_out = _html(client, "/console")
    assert "Sample data" in logged_out and 'data-demo="1"' in logged_out
    assert NOINDEX not in logged_out
    demo = _html(client, "/console/demo")
    assert "Sample data" in demo and NOINDEX not in demo
    assert 'href="/console/demo"' in _html(client, "/console/login")


def test_flag_is_read_per_request_not_at_import(client, monkeypatch):
    _hidden(monkeypatch)
    assert NAV_CONSOLE not in _html(client, "/lattice")
    _shown(monkeypatch)
    assert NAV_CONSOLE in _html(client, "/lattice")


# --- signed-in Console is unaffected ------------------------------------------------------

@pytest.mark.parametrize("flag", ["hidden", "shown"])
def test_sign_in_live_console_and_logout_end_to_end(client, monkeypatch, flag):
    (_hidden if flag == "hidden" else _shown)(monkeypatch)
    assert client.post("/console/login", data={"password": "wrong"}).status_code == 200
    _sign_in(client)

    html = _html(client, "/console")
    assert 'data-demo="0"' in html and "Sample data" not in html
    assert NAV_CONSOLE in html  # the owner keeps the nav link
    assert NOINDEX not in html
    assert client.get("/api/console/snapshot").get_json()["demo"] is False

    r = client.get("/console/logout")
    assert r.status_code == 302 and r.headers["Location"].endswith("/lattice")
    after = client.get("/console")
    if flag == "hidden":
        assert after.status_code == 302 and after.headers["Location"].endswith("/console/login")
    else:
        assert 'data-demo="1"' in after.get_data(as_text=True)


# --- /lattice card grid: the site is its own fourth card ----------------------------------

def test_lattice_grid_has_four_cards_including_this_site(client, monkeypatch):
    monkeypatch.delenv("PUBLIC_CRYPTO", raising=False)
    html = _html(client, "/lattice")
    cards = re.findall(r'<a class="card" href="([^"]+)">', html)
    assert cards == ["/job-engine", "/docfiler", "/budget", "/code"]
    assert "img/card-site.webp" in html and "Monte Lattice (this site)" in html
    assert client.get("/code").status_code == 200
    assert (ROOT / "static" / "img" / "hero-home.webp").exists()  # the former hero art is kept on disk


# --- /lattice intro: copy replaces the skyline hero ----------------------------------------

def test_lattice_intro_replaces_hero_and_sits_above_live_strip(client):
    html = _html(client, "/lattice")
    assert "hero-home.webp" not in html and 'class="hero' not in html
    assert (ROOT / "static" / "img" / "card-site.webp").exists()
    intro = html[html.index('<section class="wrap intro">'):html.index("</section>")]
    assert html.index("</section>") < html.index("Live from the Job Engine")
    assert "What this is" in intro and "hundreds of people go cold" in intro
    assert "harder to find than the actual people" in intro and 'href="/code"' in intro
    assert "mothership" not in html and "internship ended abruptly" not in html  # the generic intro is gone


def _evidence_bank_path():
    """Kevin's real bank, beside the main site checkout. None when it is not on this machine.

    ROOT's sibling first (the main checkout). In a .worktrees/TASK-n checkout that sibling is
    .worktrees/job-outreach-engine, which never exists, so fall back to the main checkout the
    worktree belongs to: the parent of git's common dir. That fallback is only trusted when
    ROOT is itself the toplevel of its git tree, so a copy inside some unrelated repo finds nothing.
    """
    sibling = ROOT.parent / "job-outreach-engine" / "evidence_bank.json"
    if sibling.exists():
        return sibling
    try:
        top, common = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--show-toplevel", "--git-common-dir"],
            cwd=ROOT, capture_output=True, text=True, timeout=5,
        ).stdout.splitlines()[:2]
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    if not top or Path(top).resolve() != ROOT:
        return None
    main_bank = Path(common).resolve().parent.parent / "job-outreach-engine" / "evidence_bank.json"
    return main_bank if main_bank.exists() else None


def test_lattice_intro_has_no_banned_words(client, monkeypatch):
    # Reads the real bank or skips out loud. A missing bank used to become {}, so the loop ran
    # zero times and every worktree reported green having checked nothing.
    monkeypatch.setattr(main.jobstats, "fetch", lambda: None)  # no live dashboard call
    path = _evidence_bank_path()
    if path is None:
        pytest.skip(f"evidence bank not found beside {ROOT.parent} or the main checkout - banned words unchecked")
    words = json.loads(path.read_text(encoding="utf-8")).get("banned_words")
    assert words, f"{path} has no banned_words - nothing to check"
    html = _html(client, "/lattice")
    start = html.index('<section class="wrap intro">')
    intro = html[start:html.index("</section>", start)]
    assert "What this is" in intro  # an empty slice would check nothing and pass
    for word in words:
        assert word.lower() not in intro.lower(), word


@pytest.mark.parametrize("flag", ["hidden", "shown"])
def test_no_em_dash_on_any_public_page(client, monkeypatch, flag):
    # Kevin's copy rule. The Console's empty-tile placeholders are data, not prose, so the
    # console pages are out of scope; every page a logged-out visitor reads is in.
    monkeypatch.setenv("PUBLIC_CRYPTO", "true" if flag == "shown" else "false")
    for path in ["/", "/lattice", "/job-engine", "/docfiler", "/budget", "/code", "/crypto", "/console/login"]:
        html = _html(client, path)
        assert "&mdash;" not in html and "—" not in html, path
