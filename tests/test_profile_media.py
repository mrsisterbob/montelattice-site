"""Image slots on the public pages: a photo renders only when its file exists in static/, and every
content <img> carries loading="lazy" plus width/height equal to the file's real pixel size.
Run: python -m pytest tests -q
"""
import re
import shutil
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import homepage  # noqa: E402
import main  # noqa: E402
import media  # noqa: E402

STATIC = ROOT / "static"
BANK = {
    "identity": {"name": "K"},
    "site_profile": {
        "resume_note": "Available on request, tailored to the role.",
        "offhours": [
            {"photo": "kevin-dog.jpg", "alt": "Kevin with a dog", "text": "Dog text stays."},
            {"photo": "kevin-beach.jpg", "alt": "Kevin at a beach", "text": "Beach text stays.",
             "landscape": True},
        ],
    },
}
PAGES = ["/", "/lattice", "/job-engine", "/docfiler", "/budget", "/code", "/crypto", "/console/demo"]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setattr(homepage, "load_bank", lambda: BANK)
    return main.app.test_client()


def _static_with(tmp_path, *names):
    (tmp_path / "img").mkdir(exist_ok=True)
    for n in names:
        shutil.copy(STATIC / "img" / n, tmp_path / "img" / n)
    return str(tmp_path)


def _img_tags(html):
    return re.findall(r"<img\b[^>]*>", html)


@pytest.mark.parametrize("name,size", [
    ("kevin-suit.jpg", (900, 900)), ("kevin-dog.jpg", (900, 1189)), ("kevin-beach.jpg", (900, 638)),
    ("sys-telegram-card.webp", (970, 940)), ("sys-telegram-draft.webp", (970, 1270)),
    ("sys-sheets-crm.webp", (1920, 933)),
])
def test_media_slot_image_size_reads_the_real_header(name, size):
    assert media.image_size(str(STATIC), "img/" + name) == size


def test_media_slot_image_size_png_and_unreadable(tmp_path):
    png = (b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", 31, 17)
           + b"\x08\x06\x00\x00\x00")
    (tmp_path / "a.png").write_bytes(png)
    (tmp_path / "junk.jpg").write_bytes(b"not an image")
    (tmp_path / "cut.jpg").write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF")
    assert media.image_size(str(tmp_path), "a.png") == (31, 17)
    assert media.image_size(str(tmp_path), "junk.jpg") is None
    assert media.image_size(str(tmp_path), "cut.jpg") is None
    assert media.image_size(str(tmp_path), "missing.jpg") is None


def test_media_slot_all_present_renders_three_sized_images(client, monkeypatch, tmp_path):
    folder = _static_with(tmp_path, "kevin-suit.jpg", "kevin-dog.jpg", "kevin-beach.jpg")
    monkeypatch.setattr(main.app, "static_folder", folder)
    imgs = _img_tags(client.get("/").get_data(as_text=True))
    assert len(imgs) == 3
    sizes = [re.search(r'width="(\d+)" height="(\d+)"', t).groups() for t in imgs]
    assert sizes == [("900", "900"), ("900", "1189"), ("900", "638")]


def test_media_slot_portrait_absent_drops_it_and_the_page_still_renders(client, monkeypatch, tmp_path):
    monkeypatch.setattr(main.app, "static_folder", _static_with(tmp_path, "kevin-dog.jpg", "kevin-beach.jpg"))
    r = client.get("/")
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    assert 'class="portrait"' not in html
    assert "masthead-inner--no-portrait" in html
    assert len(_img_tags(html)) == 2


def test_media_slot_missing_offhours_photo_keeps_its_text(client, monkeypatch, tmp_path):
    monkeypatch.setattr(main.app, "static_folder", _static_with(tmp_path, "kevin-suit.jpg", "kevin-beach.jpg"))
    html = client.get("/").get_data(as_text=True)
    assert "Dog text stays." in html and "Beach text stays." in html
    assert "kevin-dog.jpg" not in html
    assert "kevin-beach.jpg" in html
    assert html.count("offhours--no-photo") == 1


@pytest.mark.parametrize("path", PAGES)
def test_image_attrs_every_img_is_lazy_and_sized(client, path):
    html = client.get(path).get_data(as_text=True)
    for tag in _img_tags(html):
        assert 'loading="lazy"' in tag, (path, tag)
        w = re.search(r'\bwidth="(\d+)"', tag)
        h = re.search(r'\bheight="(\d+)"', tag)
        assert w and h, (path, tag)
        src = re.search(r'src="/static/([^"]+)"', tag).group(1)
        assert media.image_size(str(STATIC), src) == (int(w.group(1)), int(h.group(1))), (path, tag)


def test_media_slot_null_offhours_still_renders(client, monkeypatch):
    bank = {"identity": {"name": "K"}, "site_profile": {"offhours": None}}
    monkeypatch.setattr(homepage, "load_bank", lambda: bank)
    r = client.get("/")
    assert r.status_code == 200
    assert "Off the clock" not in r.get_data(as_text=True)
