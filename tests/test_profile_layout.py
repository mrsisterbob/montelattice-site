"""Layout of the homepage's "Get in touch" block, measured in a real browser. The Flask test
client cannot see layout, so "/" is rendered here, written to disk with its stylesheets pointed
at static/, and loaded in headless Chrome/Edge inside an iframe of the target width.
Run: python -m pytest tests/test_profile_layout.py -q
"""
import html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import homepage  # noqa: E402
import main  # noqa: E402

# The real long values: whether a line wraps depends on its own length, so short stubs hide it.
BANK = {
    "identity": {
        "name": "K",
        "site_email": "kevin.miller@montelattice.com",
        "phone": "248-709-6326",
        "github": "github.com/mrsisterbob",
        "linkedin_url": "https://www.linkedin.com/in/kevin-miller-7386a6252/",
    },
    "site_profile": {"resume_note": "Available on request, tailored to the role."},
}

BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

# Runs inside the iframe once fonts have loaded; reports into the parent so --dump-dom sees it.
PROBE = r"""<script>
function measure() {
  var de = document.documentElement, out = {clientWidth: de.clientWidth, scrollWidth: de.scrollWidth,
    lines: [], maxRight: 0};
  document.querySelectorAll(".contact .line").forEach(function (line) {
    var k = line.querySelector(".line-k").getBoundingClientRect();
    var v = line.querySelector(".line-v").getBoundingClientRect();
    out.lines.push({k: line.querySelector(".line-k").textContent, kLeft: k.left, kRight: k.right,
      vLeft: v.left, vRight: v.right});
  });
  document.querySelectorAll(".contact *").forEach(function (el) {
    out.maxRight = Math.max(out.maxRight, el.getBoundingClientRect().right);
  });
  parent.document.getElementById("OUT").textContent = JSON.stringify(out);
}
window.addEventListener("load", function () {
  (document.fonts ? document.fonts.ready : Promise.resolve()).then(measure, measure);
});
</script>
"""


def _browser():
    for path in BROWSERS:
        if Path(path).is_file():
            return path
    return shutil.which("chrome") or shutil.which("msedge")


def measure_contact(width, monkeypatch, tmp_path):
    browser = _browser()
    if not browser:
        pytest.skip("no Chrome or Edge found to measure layout")
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setattr(homepage, "load_bank", lambda: BANK)
    page = main.app.test_client().get("/").get_data(as_text=True)
    page = page.replace('"/static/', '"' + (ROOT / "static").as_uri() + "/")
    page = page.replace("</body>", PROBE + "</body>")
    (tmp_path / "page.html").write_text(page, encoding="utf-8")
    (tmp_path / "wrapper.html").write_text(
        '<!doctype html><html><body style="margin:0"><pre id="OUT"></pre>'
        f'<iframe src="page.html" scrolling="no" style="width:{width}px;height:800px;border:0"></iframe>'
        "</body></html>", encoding="utf-8")
    result = subprocess.run(
        [browser, "--headless=new", "--disable-gpu", "--no-first-run", "--window-size=1200,900",
         f"--user-data-dir={tmp_path / 'profile'}", "--allow-file-access-from-files",
         "--virtual-time-budget=8000", "--dump-dom", (tmp_path / "wrapper.html").as_uri()],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
    found = re.search(r'<pre id="OUT">(.*?)</pre>', result.stdout, re.S)
    assert found and found.group(1), f"probe reported nothing:\n{result.stdout[-2000:]}\n{result.stderr[-2000:]}"
    out = json.loads(html.unescape(found.group(1)))
    assert [line["k"] for line in out["lines"]] == ["Email", "Phone", "Résumé", "Code", "LinkedIn"]
    return out


def assert_values_share_a_left_edge(out):
    lefts = [line["vLeft"] for line in out["lines"]]
    assert max(lefts) - min(lefts) <= 1, out["lines"]


def test_contact_lines_align_and_fit_at_375px(monkeypatch, tmp_path):
    out = measure_contact(375, monkeypatch, tmp_path)
    assert_values_share_a_left_edge(out)
    assert out["maxRight"] <= out["clientWidth"], out
    assert out["scrollWidth"] <= out["clientWidth"], out


def test_contact_lines_sit_beside_their_labels_at_1100px(monkeypatch, tmp_path):
    out = measure_contact(1100, monkeypatch, tmp_path)
    assert_values_share_a_left_edge(out)
    for line in out["lines"]:
        assert line["vLeft"] > line["kRight"], line


# ---- image boxes ----------------------------------------------------------------------------

IMAGE_PROBE = r"""<script>
window.addEventListener("load", function () {
  var out = {portrait: null, offhours: []};
  var p = document.querySelector(".portrait");
  if (p) { var r = p.getBoundingClientRect(); out.portrait = {w: r.width, h: r.height,
    rem: parseFloat(getComputedStyle(document.documentElement).fontSize)}; }
  document.querySelectorAll(".offhours img").forEach(function (img) {
    var r = img.getBoundingClientRect(); out.offhours.push({w: r.width, h: r.height});
  });
  parent.document.getElementById("OUT").textContent = JSON.stringify(out);
});
</script>
"""

IMAGE_BANK = {
    "identity": {"name": "K"},
    "site_profile": {"offhours": [
        {"photo": "kevin-dog.jpg", "alt": "dog", "text": "t"},
        {"photo": "kevin-beach.jpg", "alt": "beach", "text": "t", "landscape": True},
    ]},
}


def measure_images(width, monkeypatch, tmp_path):
    browser = _browser()
    if not browser:
        pytest.skip("no Chrome or Edge found to measure layout")
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setattr(homepage, "load_bank", lambda: IMAGE_BANK)
    page = main.app.test_client().get("/").get_data(as_text=True)
    page = page.replace('"/static/', '"' + (ROOT / "static").as_uri() + "/")
    page = page.replace("</body>", IMAGE_PROBE + "</body>")
    (tmp_path / "page.html").write_text(page, encoding="utf-8")
    (tmp_path / "wrapper.html").write_text(
        '<!doctype html><html><body style="margin:0"><pre id="OUT"></pre>'
        f'<iframe src="page.html" scrolling="no" style="width:{width}px;height:800px;border:0"></iframe>'
        "</body></html>", encoding="utf-8")
    result = subprocess.run(
        [browser, "--headless=new", "--disable-gpu", "--no-first-run", "--window-size=1200,900",
         f"--user-data-dir={tmp_path / 'profile'}", "--allow-file-access-from-files",
         "--virtual-time-budget=8000", "--dump-dom", (tmp_path / "wrapper.html").as_uri()],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
    found = re.search(r'<pre id="OUT">(.*?)</pre>', result.stdout, re.S)
    assert found and found.group(1), f"probe reported nothing:\n{result.stdout[-2000:]}\n{result.stderr[-2000:]}"
    return json.loads(html.unescape(found.group(1)))


def test_image_box_portrait_is_square_and_photos_are_not_stretched(monkeypatch, tmp_path):
    # The tags carry height="900"; without height:auto in the CSS that becomes the rendered height.
    width = 1100
    out = measure_images(width, monkeypatch, tmp_path)
    box = out["portrait"]
    assert box, out
    assert abs(box["w"] - box["h"]) <= 1, box
    # From 1000px the cover is zoomed 1.1 (TASK-64), so the 9.5rem box renders 1.1x.
    zoom = 1.1 if width >= 1000 else 1
    assert box["w"] <= 9.5 * box["rem"] * zoom + 1, box
    assert len(out["offhours"]) == 2
    for img in out["offhours"]:
        assert 0 < img["h"] < 600, img


@pytest.mark.parametrize("width", [1100, 375])
def test_offhours_photos_share_one_box(width, monkeypatch, tmp_path):
    out = measure_images(width, monkeypatch, tmp_path)
    assert len(out["offhours"]) == 2, out
    a, b = out["offhours"]
    assert a["w"] > 0 and a["h"] > 0, a
    assert abs(a["w"] - b["w"]) <= 1 and abs(a["h"] - b["h"]) <= 1, (a, b)
    assert abs(a["w"] - a["h"]) <= 1, a  # the shared box is square (aspect-ratio: 1 / 1)


# ---- shared page edges ----------------------------------------------------------------------

EDGE_PROBE = r"""<script>
window.addEventListener("load", function () {
  // The figures grid draws its own 1px border, which is the visible edge: use the border box
  // there, and the content box (inside padding and border) everywhere else.
  function edges(sel) {
    var el = document.querySelector(sel);
    if (!el) { return null; }
    var r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    if (sel === ".figures") { return {left: r.left, right: r.right}; }
    return {left: r.left + parseFloat(cs.paddingLeft) + parseFloat(cs.borderLeftWidth),
            right: r.right - parseFloat(cs.paddingRight) - parseFloat(cs.borderRightWidth)};
  }
  var out = {clientWidth: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth};
  [".masthead-inner", ".paths-inner", ".figures", ".wrap > h2", ".contact-inner"].forEach(function (s) { out[s] = edges(s); });
  parent.document.getElementById("OUT").textContent = JSON.stringify(out);
});
</script>
"""

EDGE_BANK = {
    "identity": {"name": "K", "site_email": "kevin.miller@montelattice.com"},
    "site_profile": {"resume_note": "Available on request.",
                     "figures": [{"value": "4", "label": "Systems built"}, {"value": "2", "label": "Years"}]},
}


def measure_edges(width, monkeypatch, tmp_path):
    browser = _browser()
    if not browser:
        pytest.skip("no Chrome or Edge found to measure layout")
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setattr(homepage, "load_bank", lambda: EDGE_BANK)
    page = main.app.test_client().get("/").get_data(as_text=True)
    page = page.replace('"/static/', '"' + (ROOT / "static").as_uri() + "/")
    page = page.replace("</body>", EDGE_PROBE + "</body>")
    (tmp_path / "page.html").write_text(page, encoding="utf-8")
    (tmp_path / "wrapper.html").write_text(
        '<!doctype html><html><body style="margin:0"><pre id="OUT"></pre>'
        f'<iframe src="page.html" scrolling="no" style="width:{width}px;height:800px;border:0"></iframe>'
        "</body></html>", encoding="utf-8")
    result = subprocess.run(
        [browser, "--headless=new", "--disable-gpu", "--no-first-run", "--window-size=1200,900",
         f"--user-data-dir={tmp_path / 'profile'}", "--allow-file-access-from-files",
         "--virtual-time-budget=8000", "--dump-dom", (tmp_path / "wrapper.html").as_uri()],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
    found = re.search(r'<pre id="OUT">(.*?)</pre>', result.stdout, re.S)
    assert found and found.group(1), f"probe reported nothing: {result.stdout[-2000:]} {result.stderr[-2000:]}"
    return json.loads(html.unescape(found.group(1)))


@pytest.mark.parametrize("width", [1100, 640, 375])
def test_homepage_blocks_share_the_page_edges(width, monkeypatch, tmp_path):
    out = measure_edges(width, monkeypatch, tmp_path)
    selectors = [".masthead-inner", ".paths-inner", ".figures", ".wrap > h2", ".contact-inner"]
    blocks = {k: out[k] for k in selectors}
    assert all(blocks.values()), f"a block was not on the page: {blocks}"
    lefts = [v["left"] for v in blocks.values()]
    rights = [v["right"] for v in blocks.values()]
    assert max(lefts) - min(lefts) <= 1, blocks
    assert max(rights) - min(rights) <= 1, blocks
    assert out["scrollWidth"] <= out["clientWidth"], out
