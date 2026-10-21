"""The file behind the homepage "Download my résumé" button: one designed page, confirmed facts."""
import io
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

pypdf = pytest.importorskip("pypdf")

import homepage  # noqa: E402
import main  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TYP = ROOT / "resume" / "kevin-miller-resume.typ"
ROUTE = "/resume/kevin-miller-resume.pdf"

# The engine's negation gate (job-outreach-engine pipeline_utils.py:507).
NEGATIONS = re.compile(
    r"\b(?:not|no|never|nobody|nothing|none|nor|neither|without|cannot|instead|rather|only|least|"
    r"gaps?|limit(?:s|ed|ation)?|fail\w*|pretend\w*|overstat\w*|scratch|unglamorous|tedious|dull|"
    r"annoy\w*|impatien\w*|liability|warning|mistakes?|wrong|trouble|merely|honest(?:ly)?|admit\w*|"
    r"closest)\b|\b\w+n['’]t\b",
    re.IGNORECASE,
)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("’", "'")).strip()


@pytest.fixture(scope="module")
def response():
    return main.app.test_client().get(ROUTE)


@pytest.fixture(scope="module")
def reader(response):
    return pypdf.PdfReader(io.BytesIO(response.data))


@pytest.fixture(scope="module")
def text(reader):
    return reader.pages[0].extract_text()


def test_serves_one_us_letter_pdf_page(response, reader):
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF-")
    assert len(reader.pages) == 1
    box = reader.pages[0].mediabox
    assert (round(float(box.width)), round(float(box.height))) == (612, 792)


def test_signal_line_carries_the_confirmed_title_and_dates(text):
    flat = _norm(text)
    assert "Wealth Operations Specialist Intern" in flat
    assert "05/2026" in flat and "08/2026" in flat
    assert "06/2026" not in flat and "09/2026" not in flat


def test_headline_figures_present(text):
    flat = _norm(text)
    assert "60 to 20 minutes" in flat
    assert "10 critical SLA breaches" in flat


# Banked proper names and facts that contain a gate word; they are not statements about Kevin.
GATE_EXEMPT = ("Schwab Limited Power of Attorney", "host their own websites at no cost")


def test_no_negations_about_himself(text):
    flat = _norm(text)
    for phrase in GATE_EXEMPT:
        assert phrase in flat
        flat = flat.replace(phrase, "")
    assert NEGATIONS.findall(flat) == []


def test_name_first_then_headings_in_order(text):
    assert text.lstrip().startswith("Kevin Miller")
    positions = [text.upper().find(h) for h in
                 ("SUMMARY", "PROFESSIONAL EXPERIENCE", "TECHNICAL PROJECTS", "EDUCATION & CREDENTIALS",
                  "SKILLS & SYSTEMS")]
    assert all(p >= 0 for p in positions)
    assert positions == sorted(positions)


def test_metadata_names_kevin_not_a_posting(reader):
    title = reader.metadata.title or ""
    assert "Kevin Miller" in title
    assert "Open Dealer Exchange" not in title


def _typ_bullets() -> list[str]:
    """List items in the Typst source: one `- ` line each, with Typst escapes undone."""
    lines = TYP.read_text(encoding="utf-8").splitlines()
    unescape = re.compile(r"[\\](.)")
    return [_norm(unescape.sub(r"\1", l[2:]).replace("--", chr(0x2013))) for l in lines if l.startswith("- ")]


def _strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for v in node.values():
            yield from _strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from _strings(v)


def test_every_bullet_is_word_for_word_in_the_engine_banks():
    source = homepage.bank_source()
    if source.startswith(("http://", "https://")) or not Path(source).exists():
        pytest.skip("evidence bank not readable locally")
    bullets_path = Path(source).with_name("resume_bullets_bank.json")
    try:
        bank = json.loads(Path(source).read_text(encoding="utf-8"))
        pool = json.loads(bullets_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pytest.skip("engine banks not readable locally")
    banked = {_norm(t) for sect in ("experience", "projects") for e in bank[sect] for t in e["bullets"]}
    banked |= {_norm(t) for t in _strings(pool)}
    bullets = _typ_bullets()
    assert len(bullets) >= 10
    assert [b for b in bullets if b not in banked] == []


def test_typst_source_exists_and_rebuilds_the_committed_text(tmp_path, text):
    assert TYP.exists()
    if not shutil.which("typst"):
        pytest.skip("typst not on PATH")
    out = tmp_path / "rebuilt.pdf"
    subprocess.run(["typst", "compile", str(TYP), str(out)], check=True, cwd=ROOT)
    rebuilt = pypdf.PdfReader(str(out)).pages[0].extract_text()
    assert _norm(rebuilt) == _norm(text)
