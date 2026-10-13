"""The teal title band on every product page carries the masthead's drifting constellation behind the
page name (2026-10-13). Same svg, same keyframes, moving from the first second, title >= 4.5:1; the
top bar and footer stay plain. CSS shape and contrast are checked from the served sheets; motion and
heights are MEASURED in real headless Chrome. Run: python -m pytest tests -q
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

BANK = {"identity": {"name": "K"}, "site_profile": {"resume_note": "Available on request."}}
BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]
ART_W, ART_H = 800.0, 400.0
MIN_FIRST_SECOND_PX = 4.0
NO_RAMP = 0.75
PAGES = ["/job-engine", "/docfiler", "/budget", "/code", "/crypto"]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setattr(homepage, "load_bank", lambda: BANK)
    monkeypatch.setattr(jobstats, "fetch", lambda *a, **k: None)
    return main.app.test_client()


def _rapture(client):
    return client.get("/static/css/rapture.css").get_data(as_text=True)


def _strip(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _rule(css, selector):
    bodies = [m.group(2) for m in re.finditer(r"(?:^|\n)([^\s{}@][^{}]*?)\s*\{([^}]*)\}", _strip(css))
              if selector in [x.strip() for x in m.group(1).split(",")]]
    assert bodies, selector
    return "\n".join(bodies)


# --- CSS shape ------------------------------------------------------------------------------------

def test_title_band_layer_is_a_masked_token_behind_the_text(client):
    css = _rapture(client)
    body = _rule(css, ".title-band::before")
    assert "constellation.svg" in body and "constellation-drift" in body
    assert re.search(r"mask:[^;]*/\s*cover", body), "the motion model below assumes `cover` sizing"
    assert "pointer-events: none" in body and re.search(r"z-index:\s*-1", body)
    assert "background-color: var(--on-teal)" in body
    assert "-webkit-mask:" in body and re.search(r"(?<!-)mask:", body)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", body)
    assert 0.08 <= float(re.search(r"opacity:\s*([\d.]+)", body).group(1)) <= 0.14
    band = _rule(css, ".title-band")
    assert "isolation: isolate" in band and "position: relative" in band
    seconds = [float(x) for x in re.findall(r"constellation-drift\s+([\d.]+)s", body)]
    assert seconds and min(seconds) >= 12, seconds
    block = re.search(r"@media \(prefers-reduced-motion: reduce\) \{\s*\.title-band::before\s*\{([^}]*)\}", _strip(css))
    assert block and "animation: none" in block.group(1)


def test_the_keyframes_are_still_the_one_in_topbar_css():
    sheets = {p.name: p.read_text(encoding="utf-8") for p in (ROOT / "static" / "css").glob("*.css")}
    assert sum(len(re.findall(r"@keyframes constellation-drift", t)) for t in sheets.values()) == 1
    assert "@keyframes constellation-drift" in sheets["topbar.css"]


def test_the_bars_stay_plain(client):
    for name in ("topbar.css", "rapture.css", "profile.css", "toolweb.css"):
        css = _strip(client.get(f"/static/css/{name}").get_data(as_text=True))
        assert ".topbar::before" not in css and ".site-footer::before" not in css, name


@pytest.mark.parametrize("path", PAGES)
def test_every_product_page_has_a_title_band(client, monkeypatch, path):
    monkeypatch.setenv("PUBLIC_CRYPTO", "true")
    assert 'class="title-band"' in client.get(path).get_data(as_text=True), path


# --- contrast -------------------------------------------------------------------------------------

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


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_the_title_keeps_4_5_to_1_with_a_line_pixel_under_it(client, mode):
    """Worst case: an on-teal line pixel at the layer's opacity fully under a glyph of the h1
    (which is `color: var(--on-teal)`), over the --teal band."""
    tokens = client.get("/static/css/tokens.css").get_data(as_text=True)
    block = (re.search(r':root,\s*:root\[data-theme="light"\] \{(.*?)^\}', tokens, re.S | re.M)
             if mode == "light" else re.search(r':root\[data-theme="dark"\] \{(.*?)\}', tokens, re.S)).group(1)
    p = dict(re.findall(r"(--[\w-]+):\s*(#[0-9A-Fa-f]{6})\b", block))
    teal, on_teal = _rgb(p["--teal"]), _rgb(p["--on-teal"])
    opacity = float(re.search(r"opacity:\s*([\d.]+)", _rule(_rapture(client), ".title-band::before")).group(1))
    bg = [t * (1 - opacity) + o * opacity for t, o in zip(teal, on_teal)]
    assert "color: var(--on-teal)" in _rule(_rapture(client), ".title-band h1")
    assert _ratio(on_teal, bg) >= 4.5, (mode, round(_ratio(on_teal, bg), 2))


# --- measured in Chrome ---------------------------------------------------------------------------

PROBE = r"""<script>
window.addEventListener("load", function () {
  var TIMES = [0, 1000, 10000, 11000];
  var el = document.querySelector(".title-band");
  var out = {clientWidth: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth};
  var cs = getComputedStyle(el, "::before");
  out.mask = cs.maskImage || cs.webkitMaskImage || "";
  out.size = cs.maskSize || "";
  var anims = document.getAnimations().filter(function (a) {
    return a.effect && a.effect.target === el && a.effect.pseudoElement === "::before";
  });
  out.count = anims.length;
  out.w = parseFloat(cs.width); out.h = parseFloat(cs.height); out.pos = [];
  anims.forEach(function (a) { a.pause(); });
  TIMES.forEach(function (t) {
    anims.forEach(function (a) { a.currentTime = t; });
    out.pos.push(getComputedStyle(el, "::before").maskPosition);
  });
  out.heightWith = el.getBoundingClientRect().height;
  var style = document.createElement("style");
  style.textContent = ".title-band::before { display: none }";
  document.head.appendChild(style);
  out.heightWithout = el.getBoundingClientRect().height;
  var pre = document.createElement("pre");
  pre.id = "OUT";
  pre.textContent = JSON.stringify(out);
  document.body.appendChild(pre);
});
</script>
"""


def _measure(path, width, tmp_path, monkeypatch):
    browser = next((p for p in BROWSERS if Path(p).is_file()), None) or shutil.which("chrome") or shutil.which("msedge")
    if not browser:
        pytest.skip("no Chrome or Edge found to measure layout")
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setenv("PUBLIC_CRYPTO", "true")
    monkeypatch.setattr(homepage, "load_bank", lambda: BANK)
    monkeypatch.setattr(jobstats, "fetch", lambda *a, **k: None)
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
         "--virtual-time-budget=6000", "--dump-dom", (tmp_path / "wrapper.html").as_uri()],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    found = re.search(r'<pre id="RESULT">(.*?)</pre>', result.stdout, re.S)
    assert found and found.group(1), f"probe reported nothing: {result.stdout[-1500:]} {result.stderr[-800:]}"
    return json.loads(htmllib.unescape(found.group(1)))


def _offsets(rec):
    """Pixel offset of the art's top-left at each probed time. The band uses `cover` (asserted by
    test_title_band_layer_is_a_masked_token_behind_the_text), so the scale follows the band's box."""
    scale = max(rec["w"] / ART_W, rec["h"] / ART_H)
    art_w, art_h = ART_W * scale, ART_H * scale
    ox, oy = max(0.0, art_w - rec["w"]), max(0.0, art_h - rec["h"])
    points = []
    for pos in rec["pos"]:
        px, py = (float(v.rstrip("%")) for v in pos.split())
        points.append((px / 100.0 * ox, py / 100.0 * oy))
    return points


@pytest.mark.parametrize("width", [1280, 375])
@pytest.mark.parametrize("path", PAGES)
def test_title_band_lines_drift_from_the_first_second_and_change_nothing_else(path, width, tmp_path, monkeypatch, client):
    out = _measure(path, width, tmp_path, monkeypatch)
    assert "constellation.svg" in out["mask"], out
    assert out["count"] == 1, out
    p = _offsets(out)
    first = math.hypot(p[1][0] - p[0][0], p[1][1] - p[0][1])
    later = math.hypot(p[3][0] - p[2][0], p[3][1] - p[2][1])
    assert first >= MIN_FIRST_SECOND_PX, (path, width, "px in the first second", round(first, 2), out)
    assert first >= NO_RAMP * later, (path, width, "ramp", round(first, 2), round(later, 2))
    assert out["heightWith"] == out["heightWithout"], ("the layer changed the band's height", out)
    assert out["scrollWidth"] <= out["clientWidth"], out


def test_no_sideways_scroll_at_320(tmp_path, monkeypatch):
    out = _measure("/job-engine", 320, tmp_path, monkeypatch)
    assert out["scrollWidth"] <= out["clientWidth"], out
