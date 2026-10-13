"""The four Proof cards on `/` each show their own repo's measured lines of code and test-function
count, from the build snapshot. Nothing here is typed by hand. Run: python -m pytest tests -q
"""
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import buildstats  # noqa: E402
import homepage  # noqa: E402
import main  # noqa: E402

BANK = {"identity": {"name": "K"}, "site_profile": {"claim": "c"}}
ORDER = ["job-outreach-engine", "crypto-trading-engine", "docfiler", "budget-tracker"]


def _build(repos, **extra):
    base = {"commit_hours": 150, "tracked_lines": 40000, "generated_at": datetime(2026, 10, 13, tzinfo=timezone.utc),
            "repo_count": 5, "unreachable": [], "repos": repos}
    return dict(base, **extra)


def _figs(a, t):
    return {"tracked_lines": a, "test_functions": t}


@pytest.fixture
def render(monkeypatch):
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setattr(homepage, "load_bank", lambda: BANK)

    def go(build):
        monkeypatch.setattr(buildstats, "load", lambda *a, **k: build)
        return main.app.test_client().get("/").get_data(as_text=True)
    return go


def _cards(html):
    systems = html[html.index('<div class="systems">'):]
    systems = systems[:systems.index("</div>\n  </div>")]
    return systems.split('<div class="sys">')[1:]


def test_each_card_shows_its_own_repos_figures(render):
    repos = {"job-outreach-engine": _figs(31111, 901), "crypto-trading-engine": _figs(3222, 12),
             "docfiler": _figs(1333, 44), "budget-tracker": _figs(1444, 27)}
    cards = _cards(render(_build(repos)))
    assert len(cards) == 4
    for name, card in zip(ORDER, cards):
        lines, tests = repos[name]["tracked_lines"], repos[name]["test_functions"]
        assert f">{lines:,}</span> lines of code" in card, name
        assert f">{tests:,}</span> test functions" in card, name
        # no other repo's lines leak onto this card
        for other, figs in repos.items():
            if other != name:
                assert f">{figs['tracked_lines']:,}<" not in card, (name, other)


def test_a_missing_figure_is_hidden_not_filled(render):
    repos = {"job-outreach-engine": _figs(31111, 901), "crypto-trading-engine": _figs(3222, 12),
             "docfiler": {"tracked_lines": 1333}, "budget-tracker": {"test_functions": 27}}
    cards = _cards(render(_build(repos)))
    docfiler, budget = cards[2], cards[3]
    assert '<span class="sys-fig-n">1,333</span> lines of code' in docfiler and "test functions" not in docfiler
    assert '<span class="sys-fig-n">27</span> test functions' in budget and "lines of code" not in budget


def test_a_repo_absent_from_the_snapshot_shows_no_figure_row(render):
    cards = _cards(render(_build({"job-outreach-engine": _figs(31111, 901)})))
    assert "sys-figs" in cards[0]
    assert all("sys-figs" not in c for c in cards[1:])


@pytest.mark.parametrize("build", [None, _build({})])
def test_no_usable_snapshot_means_no_figures_and_no_note(render, build):
    html = render(build)
    assert "sys-figs" not in html and "sys-note" not in html
    assert "lines of code" not in html


def test_figures_follow_the_snapshot_not_the_template(render):
    first = render(_build({"docfiler": _figs(111, 5)}))
    second = render(_build({"docfiler": _figs(222, 6)}))
    assert ">111<" in first and ">111<" not in second
    assert ">222<" in second and ">222<" not in first


def test_the_section_says_what_the_figures_measure_and_when(render):
    html = render(_build({"docfiler": _figs(1333, 44)}))
    note = re.search(r'<p class="sys-note">(.*?)</p>', html, re.S).group(1)
    assert "Oct 13" in note and "git-tracked" in note and "def test_" in note and "not of test cases" in note
    assert html.index("sys-figs") < html.index('class="sys-note"')  # the footnote follows the cards


def test_system_figures_use_tokens_only(render):
    css = main.app.test_client().get("/static/css/profile.css").get_data(as_text=True)
    for sel in (r"\.sys-figs", r"\.sys-fig-n", r"\.sys-note"):
        body = re.search(sel + r"\s*\{([^}]*)\}", css).group(1)
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b", body), sel
