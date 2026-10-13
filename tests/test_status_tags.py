"""Status tags on the /lattice project cards come from siteflags.py, not from markup. These drive
the real route. Run: python -m pytest tests -q
"""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import homepage  # noqa: E402
import main  # noqa: E402
import siteflags  # noqa: E402

BANK = {"identity": {"name": "K"}, "site_profile": {"resume_note": "Available on request, tailored to the role."}}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setenv("PUBLIC_CRYPTO", "true")
    monkeypatch.setattr(homepage, "load_bank", lambda: BANK)
    monkeypatch.setattr(main.jobstats, "fetch", lambda: None)
    return main.app.test_client()


def _cards(html):
    """{href: card body html} for every project card."""
    return {href: body for href, body in
            re.findall(r'<a class="card" href="([^"]+)">(.*?)</a>', html, re.S)}


def _status(body):
    m = re.search(r'<span class="status-tag status-tag--(\w+)">([^<]+)</span>', body)
    return (m.group(1), m.group(2)) if m else None


def test_status_tags_job_engine_live_docfiler_beta_budget_live(client):
    cards = _cards(client.get("/lattice").get_data(as_text=True))
    assert _status(cards["/job-engine"]) == ("live", "Live")
    assert _status(cards["/docfiler"]) == ("beta", "Beta")
    assert _status(cards["/budget"]) == ("live", "Live")


def test_status_tags_every_other_card_is_untagged(client):
    cards = _cards(client.get("/lattice").get_data(as_text=True))
    assert {"/crypto", "/code"} <= set(cards)  # PUBLIC_CRYPTO=true shows the crypto card
    for href in ("/crypto", "/code"):
        assert _status(cards[href]) is None, href
        assert "status-tag" not in cards[href]


def test_status_tags_the_tag_sits_inside_card_body_and_the_card_anchor_is_unchanged(client):
    html = client.get("/lattice").get_data(as_text=True)
    # tests/test_public_console_demo.py matches this exact opening tag.
    assert len(re.findall(r'<a class="card" href="[^"]+">', html)) == len(_cards(html))
    for body in _cards(html).values():
        if "status-tag" in body:
            assert body.index('class="card__body"') < body.index("status-tag")


def test_status_tags_come_from_the_module_not_from_markup(client, monkeypatch):
    monkeypatch.setattr(siteflags, "PROJECT_STATUS", {})
    html = client.get("/lattice").get_data(as_text=True)
    assert 'class="status-tag' not in html
    monkeypatch.setattr(siteflags, "PROJECT_STATUS", {"code": "Beta", "budget": "Beta"})
    cards = _cards(client.get("/lattice").get_data(as_text=True))
    assert _status(cards["/budget"]) == ("beta", "Beta")
    assert _status(cards["/job-engine"]) is None


def test_status_tags_template_context_is_a_function_main_merges_once():
    ctx = siteflags.template_context()
    assert ctx["project_status"] == siteflags.PROJECT_STATUS
    assert ctx["project_status"] is not siteflags.PROJECT_STATUS  # a copy: a template cannot mutate it
    assert "siteflags.template_context()" in (ROOT / "main.py").read_text(encoding="utf-8")


def test_status_tags_css_uses_tokens_only(client):
    css = client.get("/static/css/rapture.css").get_data(as_text=True)
    block = css[css.index(".status-tag {"):css.index(".card__tag.is-private")]
    assert ".status-tag--live" in block and ".status-tag--beta" in block
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", block)
    assert "var(--ok)" in block and "var(--brass-text)" in block


def test_status_tags_a_multi_word_status_is_one_class_and_still_a_pill(client, monkeypatch):
    monkeypatch.setattr(siteflags, "PROJECT_STATUS", {"budget": "Coming Soon"})
    body = _cards(client.get("/lattice").get_data(as_text=True))["/budget"]
    assert 'class="status-tag status-tag--coming-soon">Coming Soon</span>' in body
