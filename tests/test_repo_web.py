"""/code opens with a second web, drawn by the same macro as the tool web: the M mark in the middle,
one tile per public repo around it, each repo's stack under its name. Layout is measured in real
headless Chrome. Run: python -m pytest tests -q
"""
import html as htmllib
import itertools
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
M_PATH = "M6 24V9h3l7 9 7-9h3v15h-3.2V14.2L16 22.4 9.2 14.2V24Z"
BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setattr(homepage, "load_bank", lambda: BANK)
    monkeypatch.setattr(jobstats, "fetch", lambda *a, **k: None)
    return main.app.test_client()


def _code(client, monkeypatch, crypto):
    monkeypatch.setenv("PUBLIC_CRYPTO", "true" if crypto else "false")
    r = client.get("/code")
    assert r.status_code == 200
    return r.get_data(as_text=True)


def test_code_has_one_repo_web_with_the_m_above_the_repo_list(client, monkeypatch):
    html = _code(client, monkeypatch, False)
    assert html.count('<svg class="tool-grid"') == 1
    assert html.index('<svg class="tool-grid"') < html.index('class="repo-list"')
    assert M_PATH in html


@pytest.mark.parametrize("crypto,count", [(False, 4), (True, 5)])
def test_tiles_are_the_public_repos_in_order(client, monkeypatch, crypto, count):
    html = _code(client, monkeypatch, crypto)
    names = [htmllib.unescape(n) for n in re.findall(r'<g class="tool" data-tool="([^"]*)"', html)]
    monkeypatch.setenv("PUBLIC_CRYPTO", "true" if crypto else "false")
    assert names == [r["name"] for r in main._public_repos()]
    assert len(names) == count
    assert ("crypto-trading-engine" in names) is crypto


def test_each_tile_carries_that_repos_stack_as_text(client, monkeypatch):
    html = _code(client, monkeypatch, True)
    for repo in main._public_repos():
        m = re.search(r'<g class="tool" data-tool="' + re.escape(repo["name"]) + r'".*?</g>\s*</g>', html, re.S)
        assert m, repo["name"]
        for item in repo["stack"].split(" \u00b7 "):
            assert f">{htmllib.escape(item, quote=False)}</text>" in m.group(0), (repo["name"], item)
    label = re.search(r'<svg class="tool-grid"[^>]*aria-label="([^"]*)"', html, re.S).group(1)
    for repo in main._public_repos():
        assert htmllib.escape(repo["name"]) in label
        for item in repo["stack"].split(" \u00b7 "):
            assert htmllib.escape(item, quote=False) in label, (repo["name"], item)


def test_the_macro_is_still_the_only_place_the_grid_is_written(client):
    count = sum(p.read_text(encoding="utf-8").count('class="tool-grid"') for p in (ROOT / "templates").glob("*.html"))
    assert count == 1


def test_toolweb_css_uses_tokens_only(client):
    css = client.get("/static/css/toolweb.css").get_data(as_text=True)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css)


def test_lattice_keeps_its_one_tool_web_and_the_default_markup(client, monkeypatch):
    html = client.get("/lattice").get_data(as_text=True)
    assert html.count('<svg class="tool-grid"') == 1 and 'data-web="' not in html
    assert 'viewBox="0 0 560 300"' in html and "tool__sub" not in html


PROBE = r"""<script>
window.addEventListener("load", function () {
  var svg = document.querySelector("svg.tool-grid");
  function snapshot() {
    var sb = svg.getBoundingClientRect();
    var texts = [].slice.call(svg.querySelectorAll("text:not(.tool__monogram)")).map(function (t) {
      var r = t.getBoundingClientRect();
      return {s: t.textContent, l: r.left, t: r.top, r: r.right, b: r.bottom,
              px: parseFloat(getComputedStyle(t).fontSize) * sb.width / 560};
    });
    return {box: {l: sb.left, t: sb.top, r: sb.right, b: sb.bottom}, texts: texts};
  }
  var out = {clientWidth: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth};
  svg.setAttribute("class", "tool-grid is-scattered");   // the start of the settle: marks offset, opacity 0
  out.scattered = snapshot();
  svg.setAttribute("class", "tool-grid");                // the settled grid
  out.settled = snapshot();
  var pre = document.createElement("pre");
  pre.id = "OUT";
  pre.textContent = JSON.stringify(out);
  document.body.appendChild(pre);
});
</script>
"""


def _measure(width, crypto, tmp_path, monkeypatch):
    browser = next((p for p in BROWSERS if Path(p).is_file()), None) or shutil.which("chrome") or shutil.which("msedge")
    if not browser:
        pytest.skip("no Chrome or Edge found to measure layout")
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setattr(homepage, "load_bank", lambda: BANK)
    monkeypatch.setattr(jobstats, "fetch", lambda *a, **k: None)
    monkeypatch.setenv("PUBLIC_CRYPTO", "true" if crypto else "false")
    page = main.app.test_client().get("/code").get_data(as_text=True)
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
         "--virtual-time-budget=4000", "--dump-dom", (tmp_path / "wrapper.html").as_uri()],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
    found = re.search(r'<pre id="RESULT">(.*?)</pre>', result.stdout, re.S)
    assert found and found.group(1), f"probe reported nothing: {result.stdout[-1500:]} {result.stderr[-800:]}"
    return json.loads(htmllib.unescape(found.group(1)))


def _overlap(a, b):
    w = min(a["r"], b["r"]) - max(a["l"], b["l"])
    h = min(a["b"], b["b"]) - max(a["t"], b["t"])
    return max(0.0, w) * max(0.0, h)


@pytest.mark.parametrize("width", [375, 1280])
@pytest.mark.parametrize("crypto", [False, True])
def test_repo_web_text_is_legible_inside_the_svg_and_never_overlaps(width, crypto, tmp_path, monkeypatch):
    out = _measure(width, crypto, tmp_path, monkeypatch)
    expected = len(main._public_repos())  # PUBLIC_CRYPTO is still set by _measure
    assert out["scrollWidth"] <= out["clientWidth"], out
    for state in ("settled", "scattered"):
        snap = out[state]
        box, texts = snap["box"], snap["texts"]
        assert len(texts) >= expected * 2, (state, len(texts))
        for t in texts:
            assert t["l"] >= box["l"] - 0.5 and t["r"] <= box["r"] + 0.5, (state, "outside the svg", t, box)
            assert t["t"] >= box["t"] - 0.5 and t["b"] <= box["b"] + 0.5, (state, "outside the svg", t, box)
            assert t["px"] >= 8, (state, "text under 8px", t)
        if state == "settled":
            for a, b in itertools.combinations(texts, 2):
                assert _overlap(a, b) == 0, ("overlap", a, b)
