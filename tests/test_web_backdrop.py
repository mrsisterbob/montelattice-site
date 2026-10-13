"""One drifting-constellation backdrop sits behind the WHOLE tool web, on /lattice and on `/`: from
above the web to at least 16px below its last row of labels, without a horizontal scroll, without
swallowing clicks, and with every tile name still at 4.5:1. Layout is measured in real headless
Chrome; contrast is recomputed from tokens.css. Run: python -m pytest tests -q
"""
import html as htmllib
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
import jobstats  # noqa: E402
import main  # noqa: E402

BANK = {"identity": {"name": "K"}, "site_profile": {"resume_note": "Available on request."}}
BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]
LAYER_OPACITY = 0.2


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setattr(homepage, "load_bank", lambda: BANK)
    monkeypatch.setattr(jobstats, "fetch", lambda *a, **k: None)
    return main.app.test_client()


PROBE = r"""<script>
window.addEventListener("load", function () {
  setTimeout(function () {
    var grid = document.querySelector("svg.tool-grid");
    grid.setAttribute("class", "tool-grid");   // the settled grid, whatever the animation is doing
    grid.scrollIntoView({block: "center"});    // elementFromPoint is null for points off screen
    var gr = grid.getBoundingClientRect(), layers = [];
    for (var el = grid.parentElement; el; el = el.parentElement) {
      var cs = getComputedStyle(el, "::before");
      if (cs.content !== "none" && /constellation\.svg/.test(cs.maskImage || cs.webkitMaskImage || "")) {
        var r = el.getBoundingClientRect();
        layers.push({cls: el.className, l: r.left, t: r.top, r: r.right, b: r.bottom,
                     w: r.width, h: r.height, opacity: parseFloat(cs.opacity), mask: cs.maskSize});
      }
    }
    var names = [].slice.call(grid.querySelectorAll(".tool__name")).map(function (n) {
      return n.getBoundingClientRect().bottom;
    });
    var hits = [].slice.call(grid.querySelectorAll(".tool__tile")).map(function (t) {
      var r = t.getBoundingClientRect(), hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
      return !!hit && hit.closest(".tool") === t.closest(".tool");
    });
    var out = {clientWidth: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth,
               grid: {l: gr.left, t: gr.top, r: gr.right, b: gr.bottom}, layers: layers,
               lastLabelBottom: Math.max.apply(null, names), hits: hits};
    var pre = document.createElement("pre");
    pre.id = "OUT";
    pre.textContent = JSON.stringify(out);
    document.body.appendChild(pre);
  }, 300);
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
        f'style="width:{width}px;height:1400px;border:0"></iframe>'
        '<pre id="RESULT"></pre><script>'
        'window.addEventListener("load",function(){var f=document.getElementById("f");'
        'var go=function(){try{var o=f.contentDocument.getElementById("OUT");'
        'if(o){document.getElementById("RESULT").textContent=o.textContent;return;}}catch(e){}'
        'setTimeout(go,100);};go();});</script></body></html>', encoding="utf-8")
    result = subprocess.run(
        [browser, "--headless=new", "--disable-gpu", "--no-first-run", "--window-size=1300,900",
         f"--user-data-dir={tmp_path / 'profile'}", "--allow-file-access-from-files",
         "--virtual-time-budget=9000", "--dump-dom", (tmp_path / "wrapper.html").as_uri()],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    found = re.search(r'<pre id="RESULT">(.*?)</pre>', result.stdout, re.S)
    assert found and found.group(1), f"probe reported nothing: {result.stdout[-1500:]} {result.stderr[-800:]}"
    return json.loads(htmllib.unescape(found.group(1)))


def _art_height_fraction(client):
    css = client.get("/static/css/toolweb.css").get_data(as_text=True)
    m = re.search(r"\.web-backdrop::before\s*\{[^}]*?\bmask:[^;]*/\s*auto\s+(\d+)%", css)
    assert m, "the backdrop's mask is not sized `auto N%`"
    return int(m.group(1)) / 100.0


@pytest.mark.parametrize("width", [1280, 768, 375, 320])
@pytest.mark.parametrize("path", ["/lattice", "/"])
def test_the_backdrop_runs_from_above_the_web_to_past_its_last_label(path, width, tmp_path, monkeypatch, client):
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setattr(homepage, "load_bank", lambda: BANK)
    monkeypatch.setattr(jobstats, "fetch", lambda *a, **k: None)
    out = _measure(path, width, tmp_path)
    assert len(out["layers"]) == 1, ("exactly one constellation layer behind the web", out["layers"])
    layer, grid = out["layers"][0], out["grid"]
    assert "web-backdrop" in layer["cls"], layer
    assert layer["t"] <= grid["t"] + 0.5, ("starts below the top of the web", layer, grid)
    assert layer["b"] >= out["lastLabelBottom"] + 16, ("ends within 16px of the last label", layer, out["lastLabelBottom"])
    assert layer["l"] <= grid["l"] + 0.5 and min(layer["r"], out["clientWidth"]) >= grid["r"] - 0.5, (layer, grid)
    assert out["scrollWidth"] <= out["clientWidth"], out
    assert out["hits"] and all(out["hits"]), ("the layer swallows clicks on a tile", out["hits"])
    assert layer["opacity"] == LAYER_OPACITY, layer
    # the art is sized by height (see toolweb.css), so it covers the box only while the box is at
    # most 2 x (that fraction) as wide as it is tall
    assert layer["w"] <= 2 * _art_height_fraction(client) * layer["h"], ("the art would not cover the box", layer)


# --- contrast of the tile names over the backdrop ------------------------------------------------

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
def test_tile_names_keep_4_5_to_1_with_a_line_pixel_under_them(client, mode):
    """Worst case: a line pixel (--brass-warm at the layer's opacity) fully under the glyph. The
    names are `.tool__name { fill: var(--muted) }` on the page ground (--paper)."""
    tokens = client.get("/static/css/tokens.css").get_data(as_text=True)
    block = (re.search(r':root,\s*:root\[data-theme="light"\] \{(.*?)^\}', tokens, re.S | re.M)
             if mode == "light" else re.search(r':root\[data-theme="dark"\] \{(.*?)\}', tokens, re.S)).group(1)
    p = dict(re.findall(r"(--[\w-]+):\s*(#[0-9A-Fa-f]{6})\b", block))
    # --brass-warm is only in the light block's own definitions and the dark block's
    paper, muted, line = _rgb(p["--paper"]), _rgb(p["--muted"]), _rgb(p["--brass-warm"])
    bg = [l * LAYER_OPACITY + b * (1 - LAYER_OPACITY) for l, b in zip(line, paper)]
    assert _ratio(muted, bg) >= 4.5, (mode, round(_ratio(muted, bg), 2))
    css = client.get("/static/css/toolweb.css").get_data(as_text=True)
    assert "fill: var(--muted)" in re.search(r"\.tool__name\s*\{([^}]*)\}", css).group(1)
    assert float(re.search(r"\.web-backdrop::before\s*\{[^}]*opacity:\s*([\d.]+)", css).group(1)) == LAYER_OPACITY


def test_the_class_is_on_lattice_and_home_and_not_on_code(client, monkeypatch):
    assert 'class="intro__hero web-backdrop"' in client.get("/lattice").get_data(as_text=True)
    assert 'class="web-backdrop"' in client.get("/").get_data(as_text=True)
    assert "web-backdrop" not in client.get("/code").get_data(as_text=True)
