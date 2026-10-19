"""The cover renders 10% larger on wide screens (CSS zoom), and nothing else changes."""
import re
from pathlib import Path

import sys

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
    monkeypatch.setattr(main.jobstats, "fetch", lambda: None)
    return main.app.test_client()


STATIC = Path(__file__).resolve().parent.parent / "static" / "css"


def _css(name):
    return (STATIC / name).read_text(encoding="utf-8")


def _media_blocks(css):
    """Yield (query, body) for each top-level @media block."""
    for m in re.finditer(r"@media\s*([^{]+)\{", css):
        depth, i = 1, m.end()
        while depth and i < len(css):
            depth += {"{": 1, "}": -1}.get(css[i], 0)
            i += 1
        yield m.group(1).strip(), css[m.end():i - 1]


def test_wide_media_block_zooms_the_four_cover_sections():
    blocks = [(q, b) for q, b in _media_blocks(_css("profile.css"))
              if (t := re.search(r"min-width:\s*(\d+)px", q)) and int(t.group(1)) >= 900]
    assert blocks, "no min-width >= 900px block in profile.css"
    body = blocks[0][1]
    m = re.search(r"([^{}]+)\{[^}]*zoom:\s*1\.1\s*;", body)
    assert m, "the wide block does not set zoom: 1.1"
    selectors = {s.strip() for s in m.group(1).split(",")}
    assert {".masthead", ".paths", ".wrap", ".contact"} <= selectors


def test_zoom_appears_only_inside_the_wide_block():
    css = _css("profile.css")
    wide = [b for q, b in _media_blocks(css)
            if (t := re.search(r"min-width:\s*(\d+)px", q)) and int(t.group(1)) >= 900]
    assert len(re.findall(r"\bzoom\s*:", css)) == sum(len(re.findall(r"\bzoom\s*:", b)) for b in wide) >= 1
    for q, b in _media_blocks(css):
        if "max-width" in q:
            assert "zoom" not in b, q


@pytest.mark.parametrize("sheet", ["rapture.css", "topbar.css", "toolweb.css", "tokens.css"])
def test_no_zoom_in_shared_or_product_sheets(sheet):
    assert not re.search(r"\bzoom\s*:", _css(sheet))


def test_cover_still_links_profile_css_and_markup_has_no_zoom(client):
    html = client.get("/").get_data(as_text=True)
    assert "css/profile.css" in html
    inline = re.findall(r'style\s*=\s*"[^"]*"', html) + re.findall(r"<style[^>]*>.*?</style>", html, re.S)
    assert not any(re.search(r"zoom\s*:", x) for x in inline)
