"""The hero's optional subline: bank copy, rendered directly under the claim, nothing when blank.
Run: python -m pytest tests -q
"""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import homepage  # noqa: E402
import main  # noqa: E402


def _bank(**site):
    return {"identity": {"name": "K"}, "site_profile": dict({"claim": "A claim."}, **site)}


@pytest.fixture
def render(monkeypatch):
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")

    def go(bank):
        monkeypatch.setattr(homepage, "load_bank", lambda: bank)
        return main.app.test_client().get("/").get_data(as_text=True)
    return go


def _masthead(html):
    start = html.index('<header class="masthead">')
    return html[start:html.index("</header>", start)]  # the shared topbar's </header> comes first


def test_subline_renders_directly_after_the_claim(render):
    m = _masthead(render(_bank(subline="Series 65 in progress.")))
    assert re.search(r'<p class="claim">.*?</p>\s*<p class="subline">Series 65 in progress\.</p>', m, re.S)


@pytest.mark.parametrize("site", [{}, {"subline": ""}, {"subline": "   "}, {"subline": None}, {"subline": ["a", "b"]}])
def test_no_subline_when_the_field_is_absent_or_blank(render, site):
    assert 'class="subline"' not in render(_bank(**site))


def test_subline_is_escaped_plain_text(render):
    html = render(_bank(subline="<b>x</b> & <script>1</script>"))
    assert "<b>x</b>" not in html and "<script>1</script>" not in html
    assert '<p class="subline">&lt;b&gt;x&lt;/b&gt; &amp; &lt;script&gt;1&lt;/script&gt;</p>' in html


def test_subline_does_not_get_claim_emphasis(render):
    html = render(_bank(subline="_not emphasised_"))
    assert '<p class="subline">_not emphasised_</p>' in html


def test_503_page_has_no_subline(render):
    assert 'class="subline"' not in render(None)


def test_subline_css_uses_a_token_not_a_hex(render):
    css = main.app.test_client().get("/static/css/profile.css").get_data(as_text=True)
    rule = re.search(r"\.subline\s*\{([^}]*)\}", css).group(1)
    assert "color: var(--on-teal)" in rule and not re.search(r"#[0-9a-fA-F]{3,8}\b", rule)
