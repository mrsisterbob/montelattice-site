"""The bars are plain again and the homepage's bottom mirrors its top (2026-10-13, after "I WANT THE
TOP AND BOTTOM PARTS TO BE LIKE THIS ONE IN THE IMAGE"): plain top bar and footer, a "Get in touch"
band with a 2px brass rule at its top edge and the lines inside it, one 2px brass rule between it
and a plain footer bar, "See my work" in its own box, the footnote its own marked-off block.
Layout is measured in real headless Chrome. Run: python -m pytest tests -q
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

# Every contact line and the footnote render, as on the live page.
BANK = {"identity": {"name": "K", "email": "k@example.com", "github": "github.com/example",
                     "linkedin_url": "https://www.linkedin.com/in/example"},
        "site_profile": {"resume_note": "Available on request, tailored to the role.",
                         "footnote": "Everything on this page is drawn from a banked record of my own work "
                                     "and is checked before it ships."}}
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


# --- Flask ----------------------------------------------------------------------------------------

def test_no_served_sheet_draws_a_layer_on_the_bars(client):
    for name in ("topbar.css", "rapture.css", "profile.css", "toolweb.css", "tokens.css"):
        css = re.sub(r"/\*.*?\*/", "", client.get(f"/static/css/{name}").get_data(as_text=True), flags=re.S)
        assert ".topbar::before" not in css and ".site-footer::before" not in css, name


def test_homepage_footer_follows_the_contact_band_and_the_line_is_shown_once(client):
    html = _home(client)
    assert html.index('class="contact"') < html.index('<footer class="site-footer">')
    assert html.count("This site sets no cookies and loads no trackers.") == 1
    assert 'class="privacy-line"' not in html


def test_one_footer_partial_is_shared_and_neither_template_writes_its_own():
    for name in ("base.html", "profile.html"):
        src = (ROOT / "templates" / name).read_text(encoding="utf-8")
        assert '{% include "_footer.html" %}' in src, name
        assert '<footer class="site-footer">' not in src, name
    assert '<footer class="site-footer">' in (ROOT / "templates" / "_footer.html").read_text(encoding="utf-8")


def test_the_footer_rules_live_in_the_sheet_the_homepage_loads(client):
    home = _home(client)
    sheets = re.findall(r'href="(/static/css/[^"]+)"', home)
    assert any("topbar.css" in s for s in sheets) and not any("rapture.css" in s for s in sheets)
    topbar = client.get("/static/css/topbar.css").get_data(as_text=True)
    assert ".site-footer {" in topbar and ".site-footer__link" in topbar and ".contact + .site-footer" in topbar
    assert ".site-footer" not in client.get("/static/css/rapture.css").get_data(as_text=True).replace(
        "The site footer lives in topbar.css", "")


# --- Chrome ---------------------------------------------------------------------------------------

PROBE = r"""<script>
window.addEventListener("load", function () {
  var root = document.documentElement;
  function q(s) { return document.querySelector(s); }
  function cs(el, pseudo) { return getComputedStyle(el, pseudo || null); }
  var out = {clientWidth: root.clientWidth, scrollWidth: root.scrollWidth, theme: root.getAttribute("data-theme")};
  var bar = q(".topbar"), foot = q(".site-footer"), contact = q(".contact"), steps = q(".next-steps"),
      note = q(".footnote");
  out.barBefore = bar ? cs(bar, "::before").content : null;
  out.footBefore = foot ? cs(foot, "::before").content : null;
  if (foot) {
    var fr = foot.getBoundingClientRect(), fs = cs(foot);
    out.footer = {top: fr.top, borderTop: parseFloat(fs.borderTopWidth), borderTopColor: fs.borderTopColor,
                  marginTop: parseFloat(fs.marginTop), bg: fs.backgroundColor};
  }
  if (contact) {
    var cr = contact.getBoundingClientRect(), c = cs(contact), cb = cs(contact, "::before");
    out.contact = {bottom: cr.bottom, borderTop: parseFloat(c.borderTopWidth), borderTopColor: c.borderTopColor,
                   borderBottom: parseFloat(c.borderBottomWidth), clientW: contact.clientWidth,
                   clientH: contact.clientHeight, beforeW: parseFloat(cb.width), beforeH: parseFloat(cb.height),
                   beforeContent: cb.content, beforeAnim: cb.animationName};
  }
  if (steps) {
    var s = cs(steps);
    out.steps = {bg: s.backgroundColor, body: cs(document.body).backgroundColor,
                 border: parseFloat(s.borderTopWidth), borderColor: s.borderTopColor};
  }
  if (note) {
    var n = cs(note);
    out.note = {borderTop: parseFloat(n.borderTopWidth), marginTop: parseFloat(n.marginTop)};
  }
  var pre = document.createElement("pre");
  pre.id = "OUT";
  pre.textContent = JSON.stringify(out);
  document.body.appendChild(pre);
});
</script>
"""


def _measure(path, width, theme, tmp_path, monkeypatch):
    browser = next((p for p in BROWSERS if Path(p).is_file()), None) or shutil.which("chrome") or shutil.which("msedge")
    if not browser:
        pytest.skip("no Chrome or Edge found to measure layout")
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setattr(homepage, "load_bank", lambda: BANK)
    monkeypatch.setattr(jobstats, "fetch", lambda *a, **k: None)
    page = main.app.test_client().get(path).get_data(as_text=True)
    page = page.replace('"/static/', '"' + (ROOT / "static").as_uri() + "/")
    page = page.replace('data-theme="dark"', f'data-theme="{theme}"', 1)
    # the head script reads storage; a fresh profile has none, so the served attribute stands
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
         "--virtual-time-budget=5000", "--dump-dom", (tmp_path / "wrapper.html").as_uri()],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    found = re.search(r'<pre id="RESULT">(.*?)</pre>', result.stdout, re.S)
    assert found and found.group(1), f"probe reported nothing: {result.stdout[-1500:]} {result.stderr[-800:]}"
    return json.loads(htmllib.unescape(found.group(1)))


def _brass_rgb(client, theme):
    css = client.get("/static/css/tokens.css").get_data(as_text=True)
    block = (re.search(r':root,\s*:root\[data-theme="light"\] \{(.*?)^\}', css, re.S | re.M)
             if theme == "light" else re.search(r':root\[data-theme="dark"\] \{(.*?)\}', css, re.S)).group(1)
    h = re.search(r"--brass:\s*(#[0-9A-Fa-f]{6})", block).group(1).lstrip("#")
    return "rgb(%d, %d, %d)" % tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("width", [1280, 375])
def test_homepage_bottom_mirrors_the_top(width, theme, tmp_path, monkeypatch, client):
    out = _measure("/", width, theme, tmp_path, monkeypatch)
    brass = _brass_rgb(client, theme)
    assert out["theme"] == theme, out
    assert out["barBefore"] == "none" and out["footBefore"] == "none", out  # plain bars
    c, f = out["contact"], out["footer"]
    # From 1000px the cover is zoomed 1.1 (TASK-64): a 2px rule renders 2 device px, reported as 2/1.1.
    zoomed = width >= 1000
    rule_min, hair_min = (1.8, 0.9) if zoomed else (2, 1)
    assert c["borderTop"] >= rule_min and c["borderTopColor"] == brass, ("the band's top rule", c)
    assert c["borderBottom"] == 0, c  # one rule between band and footer: the footer's own top border
    assert abs(f["top"] - c["bottom"]) < 0.5, ("a gap between the band and the footer", f, c)
    assert f["marginTop"] == 0 and f["borderTop"] == 2 and f["borderTopColor"] == brass, ("the single rule", f)
    # the lines stay inside the band's padding box, below its top rule
    assert abs(c["beforeW"] - c["clientW"]) < 0.5 and abs(c["beforeH"] - c["clientH"]) < 0.5, c
    assert c["beforeContent"] != "none" and c["beforeAnim"] == "constellation-drift", c
    s = out["steps"]
    assert s["bg"] not in ("rgba(0, 0, 0, 0)", "transparent") and s["bg"] != s["body"], s
    assert s["border"] >= hair_min, s  # 1px renders as 1/1.1 when zoomed (TASK-64)
    n = out["note"]
    assert n["borderTop"] >= hair_min and n["marginTop"] >= 40, n
    assert out["scrollWidth"] <= out["clientWidth"], out


def test_product_pages_keep_a_brass_rule_over_a_plain_footer(tmp_path, monkeypatch, client):
    out = _measure("/job-engine", 1280, "dark", tmp_path, monkeypatch)
    f = out["footer"]
    assert out["footBefore"] == "none" and out["barBefore"] == "none", out
    assert f["borderTop"] == 2 and f["borderTopColor"] == _brass_rgb(client, "dark"), f
    assert f["marginTop"] > 0, f  # on product pages the page ground sits between content and footer
