"""The constellation drifts at cruising speed from the first frame (no ease-in ramp), on the
the contact band and the tool-web backdrop (/lattice and /), and the contact band's text keeps its contrast
over it. Motion and contrast are MEASURED: Chrome pauses each ::before animation at fixed times and
reads the computed mask-position; contrast is recomputed from tokens.css.
Run: python -m pytest tests -q
"""
import html as htmllib
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import homepage  # noqa: E402
import jobstats  # noqa: E402
import main  # noqa: E402

# A bank with every contact line, so the band is as tall as the live one (~228px at 375px); the
# art's overflow, and so how far it can travel, depends on that height.
BANK = {"identity": {"name": "K", "email": "k@example.com", "github": "github.com/example",
                     "linkedin_url": "https://www.linkedin.com/in/example"},
        "site_profile": {"resume_note": "Available on request, tailored to the role.",
                         "footnote": "Everything on this page is drawn from a banked record of my own work and "
                                     "is checked before it ships."}}
BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]
ART_W, ART_H = 800.0, 400.0  # static/img/constellation.svg's viewBox, scaled by `cover`
MIN_FIRST_SECOND_PX = 4.0   # a floor, not a target: measured 5.6-41px in the first second
NO_RAMP = 0.75              # first-second travel must be >= 75% of the 10-11s travel

PROBE = r"""<script>
window.addEventListener("load", function () {
  var TIMES = [0, 1000, 10000, 11000], out = {clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth, bands: {}};
  [".contact", ".web-backdrop"].forEach(function (sel) {
    var el = document.querySelector(sel);
    if (!el) return;
    var anims = document.getAnimations().filter(function (a) {
      return a.effect && a.effect.target === el && a.effect.pseudoElement === "::before";
    });
    var cs = getComputedStyle(el, "::before");
    var rec = {count: anims.length, w: parseFloat(cs.width), h: parseFloat(cs.height), pos: []};
    anims.forEach(function (a) { a.pause(); });
    TIMES.forEach(function (t) {
      anims.forEach(function (a) { a.currentTime = t; });
      rec.pos.push(getComputedStyle(el, "::before").maskPosition);
    });
    out.bands[sel] = rec;
  });
  var pre = document.createElement("pre");
  pre.id = "OUT";
  pre.textContent = JSON.stringify(out);
  document.body.appendChild(pre);
});
</script>
"""


def _measure(path, width, tmp_path):
    browser = next((p for p in BROWSERS if Path(p).is_file()), None) or shutil.which("chrome") or shutil.which("msedge")
    if not browser:
        pytest.skip("no Chrome or Edge found to measure layout")
    page = main.app.test_client().get(path).get_data(as_text=True)
    page = page.replace('"/static/', '"' + (ROOT / "static").as_uri() + "/")
    page = page.replace("</body>", PROBE + "</body>")
    (tmp_path / "page.html").write_text(page, encoding="utf-8")
    (tmp_path / "wrapper.html").write_text(
        '<!doctype html><html><body style="margin:0"><iframe id="f" src="page.html" scrolling="no" '
        f'style="width:{width}px;height:900px;border:0"></iframe>'
        '<pre id="RESULT"></pre><script>'
        'window.addEventListener("load",function(){var f=document.getElementById("f");'
        'var go=function(){try{var o=f.contentDocument.getElementById("OUT");'
        'if(o){document.getElementById("RESULT").textContent=o.textContent;return;}}catch(e){}'
        'setTimeout(go,100);};go();});</script></body></html>', encoding="utf-8")
    result = subprocess.run(
        [browser, "--headless=new", "--disable-gpu", "--no-first-run", "--window-size=1300,900",
         f"--user-data-dir={tmp_path / 'profile'}", "--allow-file-access-from-files",
         "--virtual-time-budget=4000", "--dump-dom", (tmp_path / "wrapper.html").as_uri()],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
    found = re.search(r'<pre id="RESULT">(.*?)</pre>', result.stdout, re.S)
    assert found and found.group(1), f"probe reported nothing: {result.stdout[-1500:]} {result.stderr[-800:]}"
    return json.loads(htmllib.unescape(found.group(1)))


BACKDROP_ART_HEIGHT = 1.2  # .web-backdrop::before sizes the art `auto 120%`: a fraction of the box height


def _offsets(rec, band=None):
    """Pixel offset of the art's top-left corner at each probed time (mask-position % of overflow).
    Bands use `cover`; the tool-web backdrop sizes the art by height (see toolweb.css)."""
    if band == ".web-backdrop":
        scale = BACKDROP_ART_HEIGHT * rec["h"] / ART_H
    else:
        scale = max(rec["w"] / ART_W, rec["h"] / ART_H)
    ox, oy = max(0.0, ART_W * scale - rec["w"]), max(0.0, ART_H * scale - rec["h"])
    points = []
    for pos in rec["pos"]:
        px, py = (float(v.rstrip("%")) for v in pos.split())
        points.append((px / 100.0 * ox, py / 100.0 * oy))
    return points


def _travel(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


CASES = [("/", ".contact"), ("/lattice", ".web-backdrop"), ("/", ".web-backdrop")]


@pytest.mark.parametrize("width", [375, 1280])
@pytest.mark.parametrize("path,band", CASES)
def test_constellation_moves_from_the_first_second_without_a_ramp(path, band, width, monkeypatch, tmp_path):
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setattr(homepage, "load_bank", lambda: BANK)
    monkeypatch.setattr(jobstats, "fetch", lambda *a, **k: None)
    out = _measure(path, width, tmp_path)
    rec = out["bands"].get(band)
    assert rec and rec["count"] == 1, (band, out)
    p = _offsets(rec, band)
    first, later = _travel(p[0], p[1]), _travel(p[2], p[3])
    assert first >= MIN_FIRST_SECOND_PX, (band, width, "px in the first second", round(first, 2), rec)
    assert first >= NO_RAMP * later, (band, width, "ramp", round(first, 2), round(later, 2), rec)
    if path == "/":
        assert out["scrollWidth"] <= out["clientWidth"], out


# --- contrast of the contact band's text over its constellation ----------------------------------

def _lin(c):
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def _lum(c):
    r, g, b = (_lin(v) for v in c)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _ratio(a, b):
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _mix(fg, bg, alpha):
    return [f * alpha + b * (1 - alpha) for f, b in zip(fg, bg)]


@pytest.fixture(scope="module")
def palettes():
    c = main.app.test_client()
    tokens = c.get("/static/css/tokens.css").get_data(as_text=True)
    light = re.search(r':root,\s*:root\[data-theme="light"\] \{(.*?)^\}', tokens, re.S | re.M).group(1)
    dark = re.search(r':root\[data-theme="dark"\] \{(.*?)\}', tokens, re.S).group(1)
    grab = lambda block: dict(re.findall(r"(--[\w-]+):\s*(#[0-9A-Fa-f]{6})\b", block))
    profile = c.get("/static/css/profile.css").get_data(as_text=True)
    profile = re.sub(r"/\*.*?\*/", "", profile, flags=re.S)
    layer = float(re.search(r"\.contact::before\s*\{[^}]*opacity:\s*([\d.]+)", profile).group(1))
    resume = float(re.search(r"\.line-v\.resume-note\s*\{\s*opacity:\s*([\d.]+)", profile).group(1))
    footnote = float(re.search(r"\.footnote\s*\{[^}]*opacity:\s*([\d.]+)", profile).group(1))
    return {"light": grab(light), "dark": grab(dark), "layer": layer, "resume": resume, "footnote": footnote}


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_contact_band_text_keeps_4_5_to_1_over_the_constellation(palettes, mode):
    """Worst case: a line pixel fully under the glyph, i.e. on-teal at the layer's opacity over teal.
    The text's own opacity (resume note, footnote) then blends it toward that background."""
    p = palettes[mode]
    teal, on_teal, brass = _rgb(p["--teal"]), _rgb(p["--on-teal"]), _rgb(p["--brass"])
    bg = _mix(on_teal, teal, palettes["layer"])
    texts = {"on-teal text": (on_teal, 1.0), "label (brass)": (brass, 1.0),
             "resume note": (on_teal, palettes["resume"]), "footnote": (on_teal, palettes["footnote"])}
    for name, (fg, opacity) in texts.items():
        ratio = _ratio(_mix(fg, bg, opacity), bg)
        assert ratio >= 4.5, (mode, name, round(ratio, 2), "layer", palettes["layer"])
