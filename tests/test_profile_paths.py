"""The homepage offers two clear paths right under the masthead and a closing "You might want
to:" row. Run: python -m pytest tests -q
"""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import homepage  # noqa: E402
import main  # noqa: E402

LINKEDIN = "https://www.linkedin.com/in/example-person/"
BANK = {
    "identity": {"name": "K", "linkedin_url": LINKEDIN},
    "site_profile": {"resume_note": "Available on request, tailored to the role."},
}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setattr(homepage, "load_bank", lambda: BANK)
    return main.app.test_client()


def _path(html, title):
    m = re.search(r'<h2 class="path__title">' + re.escape(title) + r"</h2>(.*?)</div>", html, re.S)
    assert m, title
    return m.group(1)


def test_paths_hiring_links_the_resume_pdf_and_the_banks_linkedin(client):
    html = client.get("/").get_data(as_text=True)
    hiring = _path(html, "Hiring?")
    assert main.RESUME_PDF in hiring
    assert f'href="{LINKEDIN}"' in hiring


def test_paths_building_links_to_the_docfiler_form(client):
    html = client.get("/").get_data(as_text=True)
    assert 'href="/docfiler#contact-form"' in _path(html, "Building something?")
    assert 'id="contact-form"' in (ROOT / "templates" / "docfiler.html").read_text(encoding="utf-8")


def test_paths_sit_right_after_the_masthead_before_the_figures(client):
    html = client.get("/").get_data(as_text=True)
    assert html.index("</header>") < html.index('<div class="paths">') < html.index('<div class="wrap">')


def test_paths_closing_row_comes_after_the_timeline_and_before_get_in_touch(client):
    html = client.get("/").get_data(as_text=True)
    row = html[html.index('<p class="next-steps">'):]
    row = row[:row.index("</p>")]
    assert "You might want to:" in row
    assert 'href="/lattice"' in row and f'href="{LINKEDIN}"' in row and main.RESUME_PDF in row
    assert html.index('<p class="next-steps">') < html.index("Get in touch")


def test_paths_without_the_resume_file_show_the_note_not_a_dead_link(client, monkeypatch, tmp_path):
    monkeypatch.setattr(main.app, "static_folder", str(tmp_path))
    html = client.get("/").get_data(as_text=True)
    assert main.RESUME_PDF not in html
    assert BANK["site_profile"]["resume_note"] in _path(html, "Hiring?")
    row = html[html.index('<p class="next-steps">'):]
    assert "R&eacute;sum&eacute;" not in row[:row.index("</p>")]


def test_paths_hide_linkedin_when_the_bank_has_none(client, monkeypatch):
    bank = {"identity": {"name": "K"}, "site_profile": {}}
    monkeypatch.setattr(homepage, "load_bank", lambda: bank)
    html = client.get("/").get_data(as_text=True)
    assert "linkedin" not in _path(html, "Hiring?").lower()
    row = html[html.index('<p class="next-steps">'):]
    assert "LinkedIn" not in row[:row.index("</p>")]


def test_paths_are_absent_from_the_503_page(monkeypatch):
    monkeypatch.setattr(homepage, "load_bank", lambda: None)
    html = main.app.test_client().get("/").get_data(as_text=True)
    assert "Hiring?" not in html and "You might want to:" not in html


def test_paths_css_uses_tokens_only(client):
    css = client.get("/static/css/profile.css").get_data(as_text=True)
    block = css[css.index("/* ---- two paths"):css.index("/* ---- timeline")]
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", block)


def test_paths_closing_row_is_after_the_timeline_when_there_is_one(client, monkeypatch):
    bank = dict(BANK, experience=[{"company": "Acme", "title": "Analyst", "start": "05/2025", "end": "08/2025", "bullets": []}])
    monkeypatch.setattr(homepage, "load_bank", lambda: bank)
    html = client.get("/").get_data(as_text=True)
    assert html.index('<ol class="timeline">') < html.index('<p class="next-steps">') < html.index("Get in touch")


def test_paths_hiring_never_renders_a_card_with_nothing_to_click(client, monkeypatch, tmp_path):
    monkeypatch.setattr(main.app, "static_folder", str(tmp_path))
    bank = {"identity": {"name": "K", "site_email": "k@example.com"}, "site_profile": {}}
    monkeypatch.setattr(homepage, "load_bank", lambda: bank)
    hiring = _path(client.get("/").get_data(as_text=True), "Hiring?")
    assert 'href="mailto:k@example.com"' in hiring
