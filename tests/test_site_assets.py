"""Static assets the pages link to: the résumé link must never 404, and no unredacted (-RAW)
screenshot may be referenced anywhere. Run: python -m pytest tests -q
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


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setattr(homepage, "load_bank", lambda: BANK)
    return main.app.test_client()


def test_resume_absent_shows_the_note_and_no_link(client, monkeypatch, tmp_path):
    monkeypatch.setattr(main.app, "static_folder", str(tmp_path))
    html = client.get("/").get_data(as_text=True)
    assert "Available on request, tailored to the role." in html
    assert main.RESUME_PDF not in html


def test_resume_present_links_to_a_file_that_is_served(client, monkeypatch, tmp_path):
    (tmp_path / main.RESUME_PDF).write_bytes(b"%PDF-1.7 test")
    monkeypatch.setattr(main.app, "static_folder", str(tmp_path))
    html = client.get("/").get_data(as_text=True)
    href = re.search(r'href="([^"]*kevin-miller-resume\.pdf)"', html).group(1)
    assert "Available on request" not in html
    r = client.get(href)
    assert r.status_code == 200 and r.data == b"%PDF-1.7 test"


def test_headshot_referenced_by_the_profile_exists(client):
    html = client.get("/").get_data(as_text=True)
    src = re.search(r'<img class="portrait" src="/static/([^"]+)"', html).group(1)
    assert (ROOT / "static" / src).is_file()


def test_no_raw_screenshot_is_referenced_anywhere():
    for path in list((ROOT / "templates").rglob("*.html")) + list((ROOT / "static").rglob("*.css")) \
            + list((ROOT / "static").rglob("*.js")) + list(ROOT.glob("*.py")):
        assert "RAW" not in path.read_text(encoding="utf-8"), path


def test_job_engine_screenshots_exist_and_are_redacted_copies():
    src = (ROOT / "templates" / "job_engine.html").read_text(encoding="utf-8")
    shots = set(re.findall(r"img/(sys-[\w-]+\.webp)", src))
    assert shots == {"sys-telegram-card.webp", "sys-telegram-draft.webp", "sys-sheets-crm.webp"}
    for name in shots:
        assert (ROOT / "static" / "img" / name).is_file()
