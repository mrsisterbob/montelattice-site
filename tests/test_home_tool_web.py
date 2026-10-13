"""The homepage shows the same tool web as /lattice, drawn by the same macro, settled by one shared
script and styled by one shared sheet. Layout is measured in real headless Chrome.
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
import tools  # noqa: E402

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


def _home(client):
    return client.get("/").get_data(as_text=True)


def test_homepage_draws_one_tool_web_from_tools_py(client):
    html = _home(client)
    assert html.count('<svg class="tool-grid"') == 1
    names = [htmllib.unescape(n) for n in re.findall(r'<g class="tool" data-tool="([^"]*)"', html)]
    assert sorted(names) == sorted(t.name for t in tools.TOOLS)
    assert "M6 24V9h3l7 9 7-9h3v15h-3.2V14.2L16 22.4 9.2 14.2V24Z" in html  # the M mark


def test_the_web_sits_below_the_paths_and_above_the_credentials(monkeypatch):
    bank = dict(BANK, education=[{"degree": "Economics, B.A.", "school": "Test College", "end": "05/2025"}])
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setattr(homepage, "load_bank", lambda: bank)
    monkeypatch.setattr(jobstats, "fetch", lambda *a, **k: None)
    html = main.app.test_client().get("/").get_data(as_text=True)
    grid = html.index('<svg class="tool-grid"')
    assert html.index('class="paths"') < grid < html.index("Credentials and research")


def test_the_web_wrapper_holds_no_text_outside_the_svg(client):
    html = _home(client)
    start = html.index('<div class="tool-grid-wrap">')
    wrapper = html[start:html.index("</svg>", start) + len("</svg>")]
    outside = re.sub(r"<svg.*?</svg>", "", wrapper, flags=re.S)
    assert re.sub(r"<[^>]+>", "", outside).strip() == ""


def test_home_and_lattice_share_one_stylesheet_and_one_script_and_home_has_no_site_js(client):
    home, lattice = _home(client), client.get("/lattice").get_data(as_text=True)
    for page in (home, lattice):
        assert "css/toolweb.css" in page and "js/toolweb.js" in page
    assert "site.js" not in home
    assert "site.js" not in "".join(re.findall(r'src="([^"]+)"', home))


def test_the_tool_grid_svg_is_written_once_across_the_templates():
    count = sum(p.read_text(encoding="utf-8").count('class="tool-grid"') for p in (ROOT / "templates").glob("*.html"))
    assert count == 1


def test_the_503_page_renders_no_web(monkeypatch):
    monkeypatch.setattr(homepage, "load_bank", lambda: None)
    page = main.app.test_client().get("/").get_data(as_text=True)
    assert "tool-grid" not in page.replace("toolweb", "")


PROBE = r"""<script>
window.addEventListener("load", function () {
  setTimeout(function () {
    var svg = document.querySelector("svg.tool-grid"), paths = document.querySelector(".paths");
    var sr = svg.getBoundingClientRect(), pr = paths.getBoundingClientRect();
    var sizes = [].slice.call(svg.querySelectorAll(".tool__name")).map(function (t) {
      return parseFloat(getComputedStyle(t).fontSize) * sr.width / 560;
    });
    var btn = document.getElementById("theme-toggle");
    btn.click();
    var out = {
      clientWidth: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth,
      gridTop: sr.top, gridRight: sr.right, pathsBottom: pr.bottom,
      minName: Math.min.apply(null, sizes), cls: svg.getAttribute("class"),
      theme: document.documentElement.getAttribute("data-theme")
    };
    var pre = document.createElement("pre");
    pre.id = "OUT";
    pre.textContent = JSON.stringify(out);
    document.body.appendChild(pre);
  }, 6800);
});
</script>
"""


def _measure(width, tmp_path):
    browser = next((p for p in BROWSERS if Path(p).is_file()), None) or shutil.which("chrome") or shutil.which("msedge")
    if not browser:
        pytest.skip("no Chrome or Edge found to measure layout")
    page = main.app.test_client().get("/").get_data(as_text=True)
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
         "--virtual-time-budget=12000", "--dump-dom", (tmp_path / "wrapper.html").as_uri()],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    found = re.search(r'<pre id="RESULT">(.*?)</pre>', result.stdout, re.S)
    assert found and found.group(1), f"probe reported nothing: {result.stdout[-1500:]} {result.stderr[-800:]}"
    return json.loads(htmllib.unescape(found.group(1)))


@pytest.mark.parametrize("width", [375, 1280])
def test_the_web_lays_out_below_the_paths_and_inside_the_viewport(width, monkeypatch, tmp_path):
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setattr(homepage, "load_bank", lambda: BANK)
    monkeypatch.setattr(jobstats, "fetch", lambda *a, **k: None)
    out = _measure(width, tmp_path)
    assert out["gridTop"] >= out["pathsBottom"], out
    assert out["gridRight"] <= out["clientWidth"], out
    assert out["scrollWidth"] <= out["clientWidth"], out
    assert out["minName"] >= 8, ("tool names render below 8px", out)
    assert "is-settling" in out["cls"], ("the settle never ran", out)
    # Served dark since 2026-10-13, so one click leaves light; a second handler would cancel it.
    assert out["theme"] == "light", ("one click must flip to light; a second handler would cancel it", out)
