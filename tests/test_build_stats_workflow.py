"""The scheduled workflow that publishes build_stats.json to the `build-stats` branch.

Structural only: GitHub's scheduler cannot run here. PyYAML is not a dependency, so these
assert on the workflow's text. The real check is Actions -> Build stats -> Run workflow, then
opening buildstats.SNAPSHOT_URL and confirming it serves today's JSON.

Run: python -m pytest tests -q
"""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import build_stats  # noqa: E402

WORKFLOW = ROOT / ".github" / "workflows" / "build-stats.yml"


@pytest.fixture(scope="module")
def text():
    return WORKFLOW.read_text(encoding="utf-8")


def _code(text):
    """The workflow without comment lines, so a comment cannot satisfy or trip an assertion."""
    return "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))


def test_every_repo_is_checked_out_at_full_depth(text):
    code = _code(text)
    for name in build_stats.REPOS:
        if name == "montelattice-site":
            assert re.search(r"path:\s*montelattice-site\b", code)
        else:
            assert f"repository: mrsisterbob/{name}" in code, name
            assert re.search(rf"path:\s*{re.escape(name)}\b", code), name
    assert code.count("actions/checkout@v4") == len(build_stats.REPOS)
    assert code.count("fetch-depth: 0") == len(build_stats.REPOS), "a checkout is shallow"


def test_runs_daily_and_by_hand_with_write_permission(text):
    code = _code(text)
    assert re.search(r"^\s*schedule:\s*\n\s*-\s*cron:", code, re.M)
    assert "workflow_dispatch:" in code
    assert re.search(r"contents:\s*write", code)


def test_python_matches_render(text):
    render = (ROOT / "render.yaml").read_text(encoding="utf-8")
    want = re.search(r"PYTHON_VERSION\s*\n?\s*value:\s*[\"']?(3\.\d+)", render)
    if want is None:
        pytest.skip("render.yaml pins no python version")
    assert f'python-version: "{want.group(1)}"' in text


def test_a_partial_or_empty_measurement_is_never_published(text):
    code = _code(text)
    guard, publish = code.index("unreachable"), code.index("git push")
    assert guard < publish, "the guard must run before the push"
    assert re.search(r'commit_hours"\]\s*>\s*0', code) and re.search(r'tracked_lines"\]\s*>\s*0', code)
    assert "sys.exit" in code


def test_publishes_only_to_the_build_stats_branch(text):
    code = _code(text)
    pushes = re.findall(r"^\s*git push\b.*$", code, re.M)
    assert len(pushes) == 1
    assert pushes[0].rstrip().endswith("HEAD:refs/heads/build-stats")
    assert not re.search(r"\b(master|main)\b", pushes[0])
    assert re.search(r"--orphan build-stats\b", code)


def test_the_branch_and_file_match_the_url_the_site_reads(text):
    # The suite blanks buildstats.SNAPSHOT_URL (conftest), so read the shipped default from source.
    src = (ROOT / "buildstats.py").read_text(encoding="utf-8")
    m = re.search(r'^SNAPSHOT_URL = "https://raw\.githubusercontent\.com/([^/]+)/([^/]+)/([^/]+)/([^"]+)"', src, re.M)
    assert m, "buildstats.SNAPSHOT_URL default not found"
    owner, repo, branch, filename = m.groups()
    assert f"refs/heads/{branch}" in text and f"--orphan {branch}" in text
    assert f"git add {filename}" in text
    assert repo == "montelattice-site" and "github.repository" in text  # the bot pushes to this repo


def test_ci_measures_pushed_history_only_is_documented(text):
    assert "pushed history only" in text.lower()
