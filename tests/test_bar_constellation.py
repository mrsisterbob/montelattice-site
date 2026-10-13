"""The top bar and the site footer carry the same drifting constellation as the masthead: one
keyframes, one constellation.svg, behind the content, moving from the first second, and every bar
text keeps 4.5:1 over it. Motion, heights and hit-testing are MEASURED in headless Chrome; contrast
is recomputed from tokens.css and the opacities in the CSS. Run: python -m pytest tests -q
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
PAGES = ["/", "/lattice", "/job-engine", "/docfiler", "/budget", "/code"]
MIN_FIRST_SECOND_PX = 4.0
NO_RAMP = 0.75


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setattr(homepage, "load_bank", lambda: BANK)
    monkeypatch.setattr(jobstats, "fetch", lambda *a, **k: None)
    return main.app.test_client()


def _css(client, name):
    return client.get(f"/static/css/{name}").get_data(as_text=True)


def _strip(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _rule(css, selector):
    for m in re.finditer(r"(?:^|\n)([^\s{}@][^{}]*?)\s*\{([^}]*)\}", _strip(css)):
        if selector in [x.strip() for x in m.group(1).split(",")]:
            yield m.group(2)


# --- CSS shape -----------------------------------------------------------------------------------

@pytest.mark.parametrize("selector", [".topbar::before", ".site-footer::before"])
def test_each_bar_layer_is_a_masked_token_behind_the_content(client, selector):
    css = _css(client, "topbar.css")
    body = "\n".join(_rule(css, selector))
    assert "constellation.svg" in body
    assert "pointer-events: none" in body and re.search(r"z-index:\s*-1", body)
    assert "background-color: var(--on-teal)" in body
    assert "-webkit-mask:" in body and re.search(r"(?<!-)mask:", body)
    assert "constellation-drift" in body
    seconds = [float(x) for x in re.findall(r"constellation-drift\s+([\d.]+)s", body)]
    assert seconds and min(seconds) >= 12, seconds  # slow enough to read as drift, not scroll
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", body)
    block = re.search(r"@media \(prefers-reduced-motion: reduce\) \{\s*" + re.escape(selector)
                      + r"\s*\{([^}]*)\}", _strip(css))
    assert block and "animation: none" in block.group(1), selector


def test_one_keyframes_for_the_whole_site_and_it_is_in_topbar_css(client):
    sheets = {p.name: p.read_text(encoding="utf-8") for p in (ROOT / "static" / "css").glob("*.css")}
    total = sum(len(re.findall(r"@keyframes constellation-drift", t)) for t in sheets.values())
    assert total == 1
    assert "@keyframes constellation-drift" in sheets["topbar.css"]


@pytest.mark.parametrize("path", PAGES)
def test_every_page_has_the_top_bar_and_every_page_but_home_has_the_footer(client, path):
    html = client.get(path).get_data(as_text=True)
    assert '<header class="topbar">' in html
    assert ('<footer class="site-footer">' in html) is (path != "/")


def test_crypto_page_has_both_bars_when_public(client, monkeypatch):
    monkeypatch.setenv("PUBLIC_CRYPTO", "true")
    html = client.get("/crypto").get_data(as_text=True)
    assert '<header class="topbar">' in html and '<footer class="site-footer">' in html


# --- contrast ------------------------------------------------------------------------------------

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


def _mix_pct(client, sheet, selector, prop="color"):
    """The percentage in `prop: color-mix(in srgb, var(--on-teal) N%, transparent)` of the rule."""
    for body in _rule(_css(client, sheet), selector):
        m = re.search(prop + r":\s*color-mix\(in srgb, var\(--on-teal\) (\d+)%", body)
        if m:
            return int(m.group(1)) / 100.0
    raise AssertionError((sheet, selector, "no on-teal color-mix"))


def _opacity(client, selector):
    body = "\n".join(_rule(_css(client, "topbar.css"), selector))
    return float(re.search(r"opacity:\s*([\d.]+)", body).group(1))


@pytest.fixture(scope="module")
def palettes():
    tokens = main.app.test_client().get("/static/css/tokens.css").get_data(as_text=True)
    light = re.search(r':root,\s*:root\[data-theme="light"\] \{(.*?)^\}', tokens, re.S | re.M).group(1)
    dark = re.search(r':root\[data-theme="dark"\] \{(.*?)\}', tokens, re.S).group(1)
    grab = lambda block: dict(re.findall(r"(--[\w-]+):\s*(#[0-9A-Fa-f]{6})\b", block))
    return {"light": grab(light), "dark": grab(dark)}


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_bar_text_keeps_4_5_to_1_over_the_constellation(client, palettes, mode):
    """Worst case: a line pixel fully under the glyph, i.e. on-teal at the layer's opacity over
    teal, with the text's own alpha composited over that."""
    p = palettes[mode]
    teal, on_teal, brass = _rgb(p["--teal"]), _rgb(p["--on-teal"]), _rgb(p["--brass"])
    top_bg = _mix(on_teal, teal, _opacity(client, ".topbar::before"))
    foot_bg = _mix(on_teal, teal, _opacity(client, ".site-footer::before"))
    cases = {
        "brand": (on_teal, 1.0, top_bg),
        "nav labels": (on_teal, _mix_pct(client, "topbar.css", ".icon-nav a"), top_bg),
        "theme toggle": (on_teal, _mix_pct(client, "topbar.css", ".theme-toggle"), top_bg),
        "active link": (brass, 1.0, top_bg),
        "footer text": (on_teal, _mix_pct(client, "rapture.css", ".site-footer"), foot_bg),
        "footer links": (on_teal, _mix_pct(client, "rapture.css", ".site-footer__link"), foot_bg),
        "footer privacy": (on_teal, _mix_pct(client, "rapture.css", ".site-footer__privacy"), foot_bg),
    }
    for name, (fg, alpha, bg) in cases.items():
        ratio = _ratio(_mix(fg, bg, alpha), bg)
        assert ratio >= 4.5, (mode, name, round(ratio, 2))


# --- measured in Chrome --------------------------------------------------------------------------

PROBE = r"""<script>
window.addEventListener("load", function () {
  var TIMES = [0, 1000, 10000, 11000];
  function heights() {
    var o = {};
    [".topbar", ".site-footer", ".masthead"].forEach(function (s) {
      var el = document.querySelector(s);
      if (el) o[s] = el.getBoundingClientRect().height;
    });
    return o;
  }
  var out = {clientWidth: document.documentElement.clientWidth,
             scrollWidth: document.documentElement.scrollWidth, layers: {}, hits: []};
  [".topbar", ".site-footer", ".masthead"].forEach(function (sel) {
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
    out.layers[sel] = rec;
  });
  var targets = [].slice.call(document.querySelectorAll("#theme-toggle, .icon-nav a, .site-footer__link"));
  targets.forEach(function (el) {
    el.scrollIntoView({block: "center"});   // elementFromPoint is null for points off screen
    var r = el.getBoundingClientRect();
    var hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
    out.hits.push({what: el.className || el.id, ok: !!hit && (hit === el || el.contains(hit))});
  });
  out.withLayer = heights();
  var style = document.createElement("style");
  style.textContent = ".topbar::before, .site-footer::before { display: none }";
  document.head.appendChild(style);
  out.withoutLayer = heights();
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


def _art_width(sel, rec):
    """Rendered width of the constellation art in a band: the bars size it by width
    (`max(100%, 800px)`), the masthead by `cover` over the 800x400 art."""
    if sel == ".masthead":
        return 800.0 * max(rec["w"] / 800.0, rec["h"] / 400.0)
    return max(rec["w"], 800.0)


def _offsets(sel, rec):
    art_w = _art_width(sel, rec)
    art_h = art_w / 2.0
    ox, oy = max(0.0, art_w - rec["w"]), max(0.0, art_h - rec["h"])
    pts = []
    for pos in rec["pos"]:
        px, py = (float(v.rstrip("%")) for v in pos.split())
        pts.append((px / 100.0 * ox, py / 100.0 * oy))
    return pts


def _travel(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


@pytest.mark.parametrize("width", [320, 375, 1280])
def test_bars_drift_from_the_first_second_and_change_nothing_else(width, tmp_path, monkeypatch):
    out = _measure("/job-engine", width, tmp_path, monkeypatch)
    for sel in (".topbar", ".site-footer"):
        rec = out["layers"][sel]
        assert rec["count"] == 1, (sel, rec)
        p = _offsets(sel, rec)
        first, later = _travel(p[0], p[1]), _travel(p[2], p[3])
        assert first >= MIN_FIRST_SECOND_PX, (sel, width, "px in the first second", round(first, 2), rec)
        assert first >= NO_RAMP * later, (sel, width, "ramp", round(first, 2), round(later, 2))
    assert out["withLayer"] == out["withoutLayer"], ("the layer changed a bar's height", out)
    assert all(h["ok"] for h in out["hits"]) and out["hits"], out["hits"]
    assert out["scrollWidth"] <= out["clientWidth"], out


@pytest.mark.parametrize("width", [375, 1280])
def test_homepage_top_bar_drifts_and_keeps_the_mastheads_scale(width, tmp_path, monkeypatch):
    out = _measure("/", width, tmp_path, monkeypatch)
    assert ".site-footer" not in out["layers"]
    rec = out["layers"][".topbar"]
    assert rec["count"] == 1, rec
    p = _offsets(".topbar", rec)
    assert _travel(p[0], p[1]) >= MIN_FIRST_SECOND_PX, (width, rec)
    ratio = _art_width(".topbar", rec) / _art_width(".masthead", out["layers"][".masthead"])
    assert 0.5 <= ratio <= 2.0, ("the bar's lines are not at the masthead's scale", round(ratio, 2))
    assert all(h["ok"] for h in out["hits"]) and out["hits"], out["hits"]
    assert out["scrollWidth"] <= out["clientWidth"], out
    assert out["withLayer"] == out["withoutLayer"], out
