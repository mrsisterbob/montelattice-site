"""'Credentials and research' on `/` is grouped under five subheads: Education, Licenses and
certificates, Research, Memberships, Athletics. The athletics line (personal bests included)
stays on the page. Every string comes from the bank. Run: python -m pytest tests -q
"""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import homepage  # noqa: E402
import main  # noqa: E402

BANK = {
    "identity": {"name": "K"},
    "education": [{"degree": "Economics, B.A.", "school": "Test College", "end": "05/2025"}],
    "certificates": ["Series 99 (in progress)", "Test Exam Level 1"],
    "research": [{"kind": "Thesis", "title": "A Study", "course": "Seminar", "summary": "Honours"}],
    "memberships": ["Alpha Society", "Beta Society"],
    "athletics": [{"honor": "All-American", "sport": "Cross Country", "school": "Test College",
                   "personal_bests": [{"time": "16:34", "event": "5k"}, {"time": "28:01", "event": "8k"}]}],
    "site_profile": {"claim": "c"},
}


@pytest.fixture
def render(monkeypatch):
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")

    def go(bank):
        monkeypatch.setattr(homepage, "load_bank", lambda: bank)
        return main.app.test_client().get("/").get_data(as_text=True)
    return go


def _section(html):
    if "<h2>Credentials and research</h2>" not in html:
        return ""
    start = html.index("<h2>Credentials and research</h2>")
    return html[start:html.index("<h2>Proof", start)]


def _groups(html):
    """{heading: the list's text that follows it}, in page order."""
    sec = _section(html)
    parts = re.split(r"<h3[^>]*>([^<]+)</h3>", sec)
    return [(parts[i], parts[i + 1]) for i in range(1, len(parts), 2)]


def test_five_groups_appear_in_order(render):
    heads = [h for h, _ in _groups(render(BANK))]
    assert heads == ["Education", "Licenses and certificates", "Research", "Memberships", "Athletics"]


def test_the_degree_is_under_education_and_licenses_are_not(render):
    groups = dict(_groups(render(BANK)))
    assert "Economics and B.A., Test College, 2025" in groups["Education"]
    assert "Series 99" not in groups["Education"] and "Test Exam" not in groups["Education"]
    assert "Series 99" in groups["Licenses and certificates"] and "Test Exam" in groups["Licenses and certificates"]
    assert "Test College" not in groups["Licenses and certificates"]


def test_personal_bests_render_inside_the_athletics_group(render):
    html = render(BANK)
    athletics = dict(_groups(html))["Athletics"]
    assert "16:34 (5k) and 28:01 (8k)" in athletics
    assert "All-American, Cross Country, Test College" in athletics


def test_research_and_memberships_keep_their_own_groups(render):
    groups = dict(_groups(render(BANK)))
    assert "Thesis: <em>A Study</em>" in groups["Research"]
    assert "Alpha Society, Beta Society" in groups["Memberships"]


def test_an_empty_athletics_section_omits_the_heading(render):
    html = render(dict(BANK, athletics=[]))
    heads = [h for h, _ in _groups(html)]
    assert "Athletics" not in heads
    assert "16:34" not in html


@pytest.mark.parametrize("field,heading", [
    ("education", "Education"), ("certificates", "Licenses and certificates"),
    ("research", "Research"), ("memberships", "Memberships"),
])
def test_any_other_empty_group_is_omitted(render, field, heading):
    heads = [h for h, _ in _groups(render(dict(BANK, **{field: []})))]
    assert heading not in heads
    assert len(heads) == 4


def test_no_bank_content_means_no_credentials_section_at_all(render):
    bank = {"identity": {"name": "K"}, "site_profile": {"claim": "c"}}
    html = render(bank)
    assert "Credentials and research" not in html and "<h3" not in _section(html)


def test_blank_entries_do_not_make_a_group(render):
    bank = dict(BANK, certificates=["", "  "], education=[{}], athletics=[{}])
    heads = [h for h, _ in _groups(render(bank))]
    assert "Licenses and certificates" not in heads and "Education" not in heads
    assert "Athletics" not in heads
