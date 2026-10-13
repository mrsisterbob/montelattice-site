"""A first-time visitor sees dark on every page, with no light flash and with JavaScript off; a
stored ml-theme=light still wins; the toggle works both ways and persists; charts pick up dark on a
fresh load. 2026-10-13: Kevin chose dark as the default. The browser tests run in real headless
Chrome with a fresh --user-data-dir per run, so storage starts empty. Run: python -m pytest tests -q
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
from tests.test_job_dashboard import FULL  # noqa: E402

BANK = {"identity": {"name": "K"}, "site_profile": {"resume_note": "Available on request."}}
BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]
PAGES = ["/", "/lattice", "/job-engine", "/docfiler", "/budget", "/code", "/console/login"]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setattr(homepage, "load_bank", lambda: BANK)
    monkeypatch.setattr(jobstats, "fetch", lambda *a, **k: None)
    return main.app.test_client()


def _dark_tokens(client):
    css = client.get("/static/css/tokens.css").get_data(as_text=True)
    block = re.search(r':root\[data-theme="dark"\] \{(.*?)\}', css, re.S).group(1)
    return dict(re.findall(r"(--[\w-]+):\s*(#[0-9A-Fa-f]{6})\b", block))


@pytest.mark.parametrize("path", PAGES)
def test_every_page_is_served_with_the_dark_theme_on_html(client, path):
    html = client.get(path).get_data(as_text=True)
    assert re.search(r'<html\b[^>]*\bdata-theme="dark"', html), path


def test_crypto_page_is_served_dark_when_public(client, monkeypatch):
    monkeypatch.setenv("PUBLIC_CRYPTO", "true")
    assert re.search(r'<html\b[^>]*\bdata-theme="dark"', client.get("/crypto").get_data(as_text=True))


@pytest.mark.parametrize("path", ["/", "/job-engine", "/console/login"])
def test_head_script_stays_synchronous_above_tokens_and_takes_light_or_dark(client, path):
    html = client.get(path).get_data(as_text=True)
    script = html.index('localStorage.getItem("ml-theme")')
    assert script < html.index("css/tokens.css")
    assert 't === "dark" || t === "light"' in html
    before = html[:script]
    assert before.rstrip().endswith("<script>") or "<script>" in before[-120:]
    assert " defer" not in html[html.rindex("<script", 0, script):script]


# --- measured in Chrome --------------------------------------------------------------------------

PROBE = r"""<script>
window.addEventListener("load", function () {
  var root = document.documentElement;
  function snap() {
    return {theme: root.getAttribute("data-theme"), paper: getComputedStyle(root).getPropertyValue("--paper").trim(),
            body: getComputedStyle(document.body).backgroundColor, stored: (function () {
              try { return localStorage.getItem("ml-theme"); } catch (e) { return "unreadable"; } })()};
  }
  var out = {load: snap()}, btn = document.getElementById("theme-toggle");
  if (btn) {
    btn.click();
    out.first = snap();
    btn.click();
    out.second = snap();
  }
  var c = window.Chart && document.getElementById("chart-volume") && Chart.getChart("chart-volume");
  if (c) out.legend = c.options.plugins.legend.labels.color;
  out.ink = getComputedStyle(root).getPropertyValue("--ink").trim();
  var pre = document.createElement("pre");
  pre.id = "OUT";
  pre.textContent = JSON.stringify(out);
  document.body.appendChild(pre);
});
</script>
"""


def _run(path, tmp_path, monkeypatch, stored=None, feed=None):
    browser = next((p for p in BROWSERS if Path(p).is_file()), None) or shutil.which("chrome") or shutil.which("msedge")
    if not browser:
        pytest.skip("no Chrome or Edge found to measure the theme")
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setattr(homepage, "load_bank", lambda: BANK)
    monkeypatch.setattr(jobstats, "fetch", lambda *a, **k: feed)
    page = main.app.test_client().get(path).get_data(as_text=True)
    page = page.replace('"/static/', '"' + (ROOT / "static").as_uri() + "/")
    if stored:  # storage written before the page's own head script runs, as a returning visitor has
        page = page.replace("<head>", '<head><script>try{localStorage.setItem("ml-theme","%s")}catch(e){}</script>' % stored, 1)
    page = page.replace("</body>", PROBE + "</body>")
    (tmp_path / "page.html").write_text(page, encoding="utf-8")
    result = subprocess.run(
        [browser, "--headless=new", "--disable-gpu", "--no-first-run", "--window-size=1200,900",
         f"--user-data-dir={tmp_path / 'profile'}", "--allow-file-access-from-files",
         "--virtual-time-budget=8000", "--dump-dom", (tmp_path / "page.html").as_uri()],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
    found = re.search(r'<pre id="OUT">(.*?)</pre>', result.stdout, re.S)
    assert found and found.group(1), f"probe reported nothing: {result.stdout[-1500:]} {result.stderr[-800:]}"
    return json.loads(htmllib.unescape(found.group(1)))


@pytest.mark.parametrize("path", ["/", "/job-engine"])
def test_fresh_visitor_gets_dark_and_the_dark_tokens(path, tmp_path, monkeypatch, client):
    out = _run(path, tmp_path, monkeypatch)
    assert out["load"]["theme"] == "dark", out
    assert out["load"]["paper"].upper() == _dark_tokens(client)["--paper"].upper(), out
    assert out["load"]["stored"] is None, out  # nothing is written until the visitor chooses


@pytest.mark.parametrize("path", ["/", "/job-engine"])
def test_a_stored_light_choice_still_wins(path, tmp_path, monkeypatch):
    out = _run(path, tmp_path, monkeypatch, stored="light")
    assert out["load"]["theme"] == "light", out


@pytest.mark.parametrize("path", ["/", "/job-engine"])
def test_the_toggle_goes_light_then_dark_and_persists_each_choice(path, tmp_path, monkeypatch):
    out = _run(path, tmp_path, monkeypatch)
    assert out["load"]["theme"] == "dark"
    assert out["first"]["theme"] == "light" and out["first"]["stored"] == "light", out
    assert out["second"]["theme"] == "dark" and out["second"]["stored"] == "dark", out


def test_the_page_body_is_dark_before_any_script_runs(client):
    """JS off: nothing here depends on a script. The attribute is in the served HTML and tokens.css
    keys the dark palette on it, so the computed ground is the dark --paper."""
    html = client.get("/").get_data(as_text=True)
    assert re.search(r'<html\b[^>]*\bdata-theme="dark"', html)
    css = client.get("/static/css/tokens.css").get_data(as_text=True)
    assert re.search(r'html, body \{ background: var\(--paper\)', css)
    assert ":root[data-theme=\"dark\"]" in css and _dark_tokens(client)["--paper"]


def test_charts_open_in_the_dark_ink_on_a_fresh_load(tmp_path, monkeypatch, client):
    out = _run("/job-engine", tmp_path, monkeypatch, feed=dict(FULL))
    assert out["load"]["theme"] == "dark"
    assert out["legend"].upper() == _dark_tokens(client)["--ink"].upper(), out
