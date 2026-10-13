"""The /job-engine volume chart reads its colours from the theme tokens once at load, so a
light/dark toggle after load must re-read them. Driven in real headless Chrome with the real
Chart.js, because the defect is in what the browser does. Run: python -m pytest tests -q
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

import jobstats  # noqa: E402
import main  # noqa: E402
from tests.test_job_dashboard import FULL  # noqa: E402

BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

# Reads, in turn: the page as loaded, after one toggle click, after a second. For each it reports
# what the chart is using and what the tokens say at that moment. Waits a frame after each click
# so the MutationObserver (a microtask) and the chart update have both run. (setTimeout, not
# requestAnimationFrame: headless virtual time does not advance frames.)
PROBE = r"""<script>
window.addEventListener("load", function () { try {
  var root = document.documentElement;
  function tok(n) { return getComputedStyle(root).getPropertyValue(n).trim(); }
  function snap(label) {
    var c = Chart.getChart("chart-volume"), o = c.options;
    return {step: label, theme: root.getAttribute("data-theme"),
      legend: o.plugins.legend.labels.color, tickX: o.scales.x.ticks.color, tickY: o.scales.y.ticks.color,
      grid: o.scales.y.grid.color,
      // what the chart actually resolved and draws with, not just what the page wrote
      drawnLegend: c.legend.options.labels.color, drawnTickX: c.scales.x.options.ticks.color,
      drawnTickY: c.scales.y.options.ticks.color, drawnGrid: c.scales.y.options.grid.color, bar0: c.data.datasets[0].backgroundColor, bar1: c.data.datasets[1].backgroundColor,
      ink: tok("--ink"), muted: tok("--muted"), chartGrid: tok("--chart-grid"),
      chart1: tok("--chart-1"), chart2: tok("--chart-2")};
  }
  var out = [], btn = document.getElementById("theme-toggle");
  function next(fn) { setTimeout(fn, 100); }
  out.push(snap("load"));
  btn.click();
  next(function () {
    out.push(snap("toggled"));
    btn.click();
    next(function () {
      out.push(snap("toggled-back"));
      var pre = document.createElement("pre");
      pre.id = "OUT";
      pre.textContent = JSON.stringify(out);
      document.body.appendChild(pre);
    });
  });
} catch (e) {
  var pre = document.createElement("pre");
  pre.id = "OUT";
  pre.textContent = JSON.stringify([{error: String(e)}]);
  document.body.appendChild(pre);
} });
</script>
"""


def _browser():
    for path in BROWSERS:
        if Path(path).is_file():
            return path
    return shutil.which("chrome") or shutil.which("msedge")


def _run(monkeypatch, tmp_path, start_theme):
    browser = _browser()
    if not browser:
        pytest.skip("no Chrome or Edge found to drive the chart")
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setattr(jobstats, "fetch", lambda *a, **k: dict(FULL))
    page = main.app.test_client().get("/job-engine").get_data(as_text=True)
    assert 'id="chart-volume"' in page, "the page rendered without the volume chart"
    page = page.replace('"/static/', '"' + (ROOT / "static").as_uri() + "/")
    page = re.sub(r"<html\b", f'<html data-theme="{start_theme}"', page, count=1)
    page = page.replace("</body>", PROBE + "</body>")
    (tmp_path / "page.html").write_text(page, encoding="utf-8")
    result = subprocess.run(
        [browser, "--headless=new", "--disable-gpu", "--no-first-run", "--window-size=1200,900",
         f"--user-data-dir={tmp_path / 'profile'}", "--allow-file-access-from-files",
         "--virtual-time-budget=8000", "--dump-dom", (tmp_path / "page.html").as_uri()],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
    found = re.search(r'<pre id="OUT">(.*?)</pre>', result.stdout, re.S)
    assert found and found.group(1), f"probe reported nothing: {result.stdout[-1500:]} {result.stderr[-1500:]}"
    return json.loads(html.unescape(found.group(1)))


def _assert_matches_tokens(s):
    assert s["legend"] == s["ink"], s
    assert s["tickX"] == s["muted"] and s["tickY"] == s["muted"], s
    assert s["grid"] == s["chartGrid"], s
    assert s["drawnLegend"] == s["ink"] and s["drawnTickX"] == s["muted"], s
    assert s["drawnTickY"] == s["muted"] and s["drawnGrid"] == s["chartGrid"], s
    assert s["bar0"] == s["chart2"] and s["bar1"] == s["chart1"], s


@pytest.mark.parametrize("start", ["dark", "light"])
def test_chart_recolours_when_the_theme_toggles(start, monkeypatch, tmp_path):
    loaded, toggled, back = _run(monkeypatch, tmp_path, start)
    assert loaded["theme"] == start and toggled["theme"] != start, (loaded, toggled)
    for snap in (loaded, toggled, back):
        _assert_matches_tokens(snap)
    # not vacuous: the two themes really do differ, and the chart moved with them
    assert loaded["ink"] != toggled["ink"] and loaded["legend"] != toggled["legend"]
    assert loaded["muted"] != toggled["muted"] and loaded["tickX"] != toggled["tickX"]
    assert back["legend"] == loaded["legend"] and back["tickY"] == loaded["tickY"]
