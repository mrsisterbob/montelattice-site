"""The homepage ends with a timeline built from the bank's DATED items only, each traceable to the
bank item it came from. Run: python -m pytest tests -q
"""
import copy
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import homepage  # noqa: E402
import main  # noqa: E402

BANK = {
    "identity": {"name": "K", "email": "k@example.com"},
    "site_profile": {"resume_note": "Available on request, tailored to the role."},
    "experience": [
        {"company": "Signal Advisors", "title": "Analyst Intern", "start": "05/2026", "end": "08/2026", "bullets": []},
        {"company": "Maple Group", "title": "Operations Intern", "start": "06/2025", "end": "08/2025", "bullets": []},
        {"company": "Undated Co", "title": "Mystery Role", "start": "Spring", "end": "Present", "bullets": []},
        {"company": "Oak Works", "title": "Crew Lead", "start": "05/2023", "end": "08/2023", "bullets": []},
    ],
    "education": [{"school": "Hillside University", "degree": "B.B.A., B.A.", "start": "08/2022", "end": "05/2026"}],
    "certificates": ["Series 65 (Expected Q4 2026)", "SIE"],
    "research": [{"kind": "Thesis", "title": "Undated Study", "course": "ECON 400", "school": "Hillside", "summary": "x"}],
}


@pytest.fixture
def make_client(monkeypatch):
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")

    def make(bank):
        monkeypatch.setattr(homepage, "load_bank", lambda: bank)
        return main.app.test_client()
    return make


def _entries(html):
    return re.findall(
        r'<li class="timeline__item timeline__item--(left|right)" data-source="([^"]+)">(.*?)</li>', html, re.S)


def _resolve(bank, source):
    name, idx = re.fullmatch(r"(\w+)\[(\d+)\]", source).groups()
    return bank[name][int(idx)]


def test_timeline_every_entry_traces_to_a_bank_item_whose_text_it_shows(make_client):
    html = make_client(BANK).get("/").get_data(as_text=True)
    entries = _entries(html)
    assert entries
    for _, source, body in entries:
        item = _resolve(BANK, source)
        text = item.get("title") or item.get("degree")
        org = item.get("company") or item.get("school")
        assert text in body and org in body, (source, body)


def test_timeline_is_newest_first_and_alternates_sides(make_client):
    entries = _entries(make_client(BANK).get("/").get_data(as_text=True))
    assert [s for _, s, _ in entries] == ["experience[0]", "education[0]", "experience[1]", "experience[3]"]
    assert [side for side, _, _ in entries] == ["left", "right", "left", "right"]


def test_timeline_labels_come_from_the_bank_dates_only(make_client):
    body = {s: b for _, s, b in _entries(make_client(BANK).get("/").get_data(as_text=True))}
    assert "May 2026 – Aug 2026" in body["experience[0]"]
    assert "Aug 2022 – May 2026" in body["education[0]"]


def test_timeline_leaves_off_undated_items(make_client):
    html = make_client(BANK).get("/").get_data(as_text=True)
    tl = html[html.index('<ol class="timeline">'):html.index("</ol>", html.index('<ol class="timeline">'))]
    for absent in ("Mystery Role", "Undated Co", "Series 65", "SIE", "Undated Study", "Expected Q4"):
        assert absent not in tl, absent


def test_timeline_a_dated_research_item_appears_on_its_own(make_client):
    bank = copy.deepcopy(BANK)
    bank["research"][0].update(title="Dated Study", date="05/2025")
    entries = _entries(make_client(bank).get("/").get_data(as_text=True))
    sources = [s for _, s, _ in entries]
    assert "research[0]" in sources
    body = dict((s, b) for _, s, b in entries)["research[0]"]
    assert "Dated Study" in body and "May 2025" in body
    # newest first: May 2025 sits between Jun 2025's neighbours correctly
    assert sources.index("experience[0]") < sources.index("research[0]") < sources.index("experience[3]")


def test_timeline_sits_after_off_the_clock_and_before_get_in_touch(make_client):
    bank = copy.deepcopy(BANK)
    bank["site_profile"]["offhours"] = [{"photo": "kevin-dog.jpg", "alt": "dog", "text": "Off hours text"}]
    html = make_client(bank).get("/").get_data(as_text=True)
    assert html.index("Off the clock") < html.index('<ol class="timeline">') < html.index("Get in touch")
    assert html.index("<h2>Timeline</h2>") < html.index('<ol class="timeline">')


def test_timeline_is_hidden_when_nothing_is_dated(make_client):
    bank = {"identity": {"name": "K"}, "site_profile": {}, "certificates": ["SIE"],
            "experience": [{"company": "X", "title": "Y", "start": "soon", "end": "later", "bullets": []}]}
    html = make_client(bank).get("/").get_data(as_text=True)
    assert '<ol class="timeline">' not in html
    assert "<h2>Timeline</h2>" not in html


def test_timeline_never_parses_a_date_out_of_free_text():
    assert homepage._month_year("Expected Q4 2026") is None
    assert homepage._month_year("05/2026") == (2026, 5)
    assert homepage._month_year("13/2026") is None
    assert homepage._month_year("5/2026") is None
    assert homepage._timeline({"certificates": ["Series 65 (Expected Q4 2026)"]}) == []


def test_timeline_the_503_page_has_none(make_client, monkeypatch):
    monkeypatch.setattr(homepage, "load_bank", lambda: None)
    r = main.app.test_client().get("/")
    assert r.status_code == 503 and "timeline" not in r.get_data(as_text=True)


def test_timeline_an_ongoing_role_ranks_newest_and_a_lone_date_is_not_a_one_month_event(make_client):
    bank = copy.deepcopy(BANK)
    bank["experience"].append({"company": "Now Co", "title": "Current Role", "start": "01/2025", "end": "Present", "bullets": []})
    bank["experience"].append({"company": "Half Co", "title": "Half Role", "start": "02/2024", "end": "Summer", "bullets": []})
    entries = _entries(make_client(bank).get("/").get_data(as_text=True))
    sources = [s for _, s, _ in entries]
    assert sources[0] == "experience[4]"  # the ongoing role, ahead of May 2026 - Aug 2026
    body = dict((s, b) for _, s, b in entries)
    assert "Jan 2025 \u2013 Present" in body["experience[4]"]
    assert "From Feb 2024" in body["experience[5]"]


def test_timeline_dates_are_ascii_mm_yyyy_in_a_sane_year_range():
    assert homepage._month_year("05/\u0662\u0660\u0662\u0666") is None
    assert homepage._month_year("05/0000") is None
    assert homepage._month_year(" 05/2026 ") == (2026, 5)
