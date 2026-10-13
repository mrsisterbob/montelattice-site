"""/docfiler shows the steps of working with Kevin and an FAQ, in positive wording with no prices
and no numbers. Run: python -m pytest tests -q
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import homepage  # noqa: E402
import main  # noqa: E402

QUESTION = "Why should I hire you over using AI myself?"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setattr(homepage, "load_bank", lambda: {"identity": {"name": "K"}, "site_profile": {}})
    return main.app.test_client()


@pytest.fixture
def html(client):
    r = client.get("/docfiler")
    assert r.status_code == 200
    return r.get_data(as_text=True)


def _steps(html):
    start = html.index('id="how-it-works"')
    return html[start:html.index('<div class="wrap section"', start + 10)]


def _faq(html):
    start = html.index('id="faq"')
    return html[start:html.index("<script", start)]


def _evidence_bank_path():
    """Kevin's real bank, beside the main site checkout. None when it is not on this machine.
    Same rule as tests/test_public_console_demo.py::_evidence_bank_path."""
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


def test_docfiler_order_learned_then_steps_then_form_then_faq(html):
    assert (html.index("What I Learned") < html.index('id="how-it-works"')
            < html.index('id="contact-form"') < html.index('id="faq"') < html.index("View source on GitHub"))


def test_docfiler_steps_are_an_ordered_list_that_starts_with_the_dry_run(html):
    steps = _steps(html)
    items = re.findall(r"<li>(.*?)</li>", steps, re.S)
    assert "<ol>" in steps and len(items) >= 4
    assert re.search(r"dry-run audit", items[0], re.I) and "free" in items[0].lower()


def test_docfiler_faq_has_the_exact_question_in_a_details_element(html):
    faq = _faq(html)
    assert f"<summary>{QUESTION}</summary>" in faq
    assert faq.count("<details>") >= 3 and "<script" not in faq


def test_docfiler_new_sections_have_no_digits_and_no_currency(html):
    for name, section in (("steps", _steps(html)), ("faq", _faq(html))):
        text = re.sub(r"<[^>]+>", " ", section)
        assert not re.search(r"[0-9]", text), (name, re.findall(r".{0,20}[0-9].{0,20}", text))
        assert not re.search(r"[$€£]", text), name


def test_docfiler_new_sections_use_none_of_the_banks_banned_words(html):
    path = _evidence_bank_path()
    if path is None:
        pytest.skip(f"evidence bank not found beside {ROOT.parent} or the main checkout - banned words unchecked")
    words = json.loads(path.read_text(encoding="utf-8")).get("banned_words")
    assert words, "the bank has no banned_words list; refusing to pass an empty check"
    text = re.sub(r"<[^>]+>", " ", _steps(html) + _faq(html)).lower()
    for word in words:
        assert not re.search(r"" + re.escape(word.lower()) + r"", text), word


def test_docfiler_the_audit_form_is_still_there_and_unchanged_in_wiring(html):
    assert 'id="contact-form"' in html and "/api/docfiler/contact" in html
