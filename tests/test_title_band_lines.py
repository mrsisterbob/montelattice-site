"""The teal title band on every product page is plain teal: no constellation layer behind the page
name (2026-10-19; the web behind the tool grid and the contact block keep theirs). Title >= 4.5:1 on
teal; the top bar and footer stay plain. CSS shape and contrast are checked from the served sheets;
the band's computed ::before and heights are MEASURED in real headless Chrome. Run: python -m pytest tests -q
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

def test_title_band_has_no_constellation_layer(client):
    css = _strip(_rapture(client))
    assert ".title-band::before" not in css and ".title-band::after" not in css
    band = _rule(css, ".title-band")
    assert "isolation" not in band and "constellation" not in band
    assert ".title-band__inner" in css


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
def test_the_title_is_4_5_to_1_on_plain_teal(client, mode):
    """The h1 is `color: var(--on-teal)` on the --teal band, nothing between them."""
    tokens = client.get("/static/css/tokens.css").get_data(as_text=True)
    block = (re.search(r':root,\s*:root\[data-theme="light"\] \{(.*?)^\}', tokens, re.S | re.M)
             if mode == "light" else re.search(r':root\[data-theme="dark"\] \{(.*?)\}', tokens, re.S)).group(1)
    p = dict(re.findall(r"(--[\w-]+):\s*(#[0-9A-Fa-f]{6})\b", block))
    teal, on_teal = _rgb(p["--teal"]), _rgb(p["--on-teal"])
    assert "color: var(--on-teal)" in _rule(_rapture(client), ".title-band h1")
    assert _ratio(on_teal, teal) >= 4.5, (mode, round(_ratio(on_teal, teal), 2))


# --- measured in Chrome ---------------------------------------------------------------------------

PROBE = r"""<script>
window.addEventListener("load", function () {
  var el = document.querySelector(".title-band");
  var out = {clientWidth: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth};
  var cs = getComputedStyle(el, "::before");
  out.content = cs.content;
  out.animName = cs.animationName;
  out.count = document.getAnimations().filter(function (a) {
    return a.effect && a.effect.target === el;
  }).length;
  out.height = el.getBoundingClientRect().height;
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


@pytest.mark.parametrize("width", [1280, 375])
@pytest.mark.parametrize("path", PAGES)
def test_title_band_has_no_pseudo_layer_in_chrome(path, width, tmp_path, monkeypatch, client):
    """Cheaper honest check than the old before/after height probe: the band's computed ::before
    generates nothing (content none), nothing animates on the band, and the page does not scroll sideways."""
    out = _measure(path, width, tmp_path, monkeypatch)
    assert out["content"] in ("none", "normal"), out
    assert out["animName"] in ("none", ""), out
    assert out["count"] == 0, out
    assert out["height"] > 0, out
    assert out["scrollWidth"] <= out["clientWidth"], out


def test_no_sideways_scroll_at_320(tmp_path, monkeypatch):
    out = _measure("/job-engine", 320, tmp_path, monkeypatch)
    assert out["scrollWidth"] <= out["clientWidth"], out
