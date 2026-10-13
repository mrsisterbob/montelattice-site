"""The homepage and the product pages draw one top bar, from one partial and one stylesheet.
The layout test runs in real headless Chrome (the Flask test client cannot see layout).
Run: python -m pytest tests -q
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


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setattr(homepage, "load_bank", lambda: BANK)
    monkeypatch.setattr(jobstats, "fetch", lambda *a, **k: None)
    return main.app.test_client()


def _topbar(page):
    m = re.search(r'<header class="topbar">.*?</header>', page, re.S)
    assert m, "no shared topbar"
    return re.sub(r"\s+", " ", m.group(0).replace('class="active"', 'class=""'))


def test_homepage_and_product_pages_render_the_same_topbar(client):
    home = client.get("/").get_data(as_text=True)
    for path in ("/job-engine", "/docfiler", "/budget"):
        assert _topbar(home) == _topbar(client.get(path).get_data(as_text=True)), path
    assert 'class="sitenav"' not in home and 'class="navlinks"' not in home


def test_the_topbar_lives_in_one_partial_included_by_both_templates():
    partial = (ROOT / "templates" / "_topbar.html").read_text(encoding="utf-8")
    assert '<header class="topbar">' in partial and 'id="theme-toggle"' in partial
    for name in ("base.html", "profile.html"):
        src = (ROOT / "templates" / name).read_text(encoding="utf-8")
        assert '{% include "_topbar.html" %}' in src, name
        assert '<header class="topbar">' not in src, name  # no second copy


def test_homepage_links_the_stylesheet_that_styles_the_icon_nav(client):
    home = client.get("/").get_data(as_text=True)
    sheets = re.findall(r'href="(/static/css/[^"]+)"', home)
    assert any("topbar.css" in s for s in sheets), sheets
    styled = [s for s in sheets if ".icon-nav" in client.get(s).get_data(as_text=True)]
    assert styled, sheets
    # and the old text-nav rules are gone from the homepage sheet
    profile_css = client.get("/static/css/profile.css").get_data(as_text=True)
    assert ".sitenav" not in profile_css and ".navlinks" not in profile_css and ".theme-toggle" not in profile_css


def test_the_product_pages_still_link_the_same_stylesheet(client):
    page = client.get("/job-engine").get_data(as_text=True)
    assert "css/topbar.css" in page


def test_homepage_toggle_still_has_its_handler(client):
    """The homepage does not load site.js; its inline handler finds #theme-toggle."""
    home = client.get("/").get_data(as_text=True)
    assert 'id="theme-toggle"' in home
    assert 'document.getElementById("theme-toggle")' in home
    assert "site.js" not in home


PROBE = r"""<script>
window.addEventListener("load", function () {
  function box(el) { var r = el.getBoundingClientRect(); return {l: r.left, t: r.top, r: r.right, b: r.bottom}; }
  var nav = document.querySelector(".icon-nav"), links = [].slice.call(nav.querySelectorAll("a"));
  var tog = document.getElementById("theme-toggle"), nb = box(nav), tb = box(tog);
  var out = {
    clientWidth: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth,
    links: links.map(function (a) { var r = box(a); return {l: Math.round(r.l), t: Math.round(r.t)}; }),
    nav: nb, toggle: tb, toggleCentre: (tb.t + tb.b) / 2,
    brand: box(document.querySelector(".topbar__brand"))
  };
  var pre = document.createElement("pre");
  pre.id = "OUT";
  pre.textContent = JSON.stringify(out);
  document.body.appendChild(pre);
});
</script>
"""


def _measure(path, width, monkeypatch, tmp_path):
    browser = next((p for p in BROWSERS if Path(p).is_file()), None) or shutil.which("chrome") or shutil.which("msedge")
    if not browser:
        pytest.skip("no Chrome or Edge found to measure layout")
    page = main.app.test_client().get(path).get_data(as_text=True)
    page = page.replace('"/static/', '"' + (ROOT / "static").as_uri() + "/")
    page = page.replace("</body>", PROBE + "</body>")
    (tmp_path / "page.html").write_text(page, encoding="utf-8")
    (tmp_path / "wrapper.html").write_text(
        '<!doctype html><html><body style="margin:0"><iframe id="f" src="page.html" scrolling="no" '
        f'style="width:{width}px;height:800px;border:0"></iframe>'
        '<pre id="RESULT"></pre><script>'
        'window.addEventListener("load",function(){var f=document.getElementById("f");'
        'var go=function(){try{var o=f.contentDocument.getElementById("OUT");'
        'if(o){document.getElementById("RESULT").textContent=o.textContent;return;}}catch(e){}'
        'setTimeout(go,100);};go();});</script></body></html>', encoding="utf-8")
    result = subprocess.run(
        [browser, "--headless=new", "--disable-gpu", "--no-first-run", "--window-size=1200,900",
         f"--user-data-dir={tmp_path / 'profile'}", "--allow-file-access-from-files",
         "--virtual-time-budget=8000", "--dump-dom", (tmp_path / "wrapper.html").as_uri()],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
    found = re.search(r'<pre id="RESULT">(.*?)</pre>', result.stdout, re.S)
    assert found and found.group(1), f"probe reported nothing: {result.stdout[-1500:]} {result.stderr[-800:]}"
    return json.loads(htmllib.unescape(found.group(1)))


@pytest.mark.parametrize("path", ["/", "/job-engine"])
def test_homepage_nav_lays_out_like_the_product_pages_at_375px(path, monkeypatch, tmp_path):
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setattr(homepage, "load_bank", lambda: BANK)
    monkeypatch.setattr(jobstats, "fetch", lambda *a, **k: None)
    out = _measure(path, 375, monkeypatch, tmp_path)
    n = len(out["links"])
    assert n >= 4, out
    lefts = sorted({l["l"] for l in out["links"]})
    tops = sorted({l["t"] for l in out["links"]})
    assert len(lefts) == 2, ("icon nav is not two columns", out["links"])
    assert len(tops) == (n + 1) // 2, ("icon nav rows", out["links"])
    nav = out["nav"]
    assert nav["t"] <= out["toggleCentre"] <= nav["b"], ("toggle is not beside the nav", out)
    assert out["scrollWidth"] <= out["clientWidth"], out
