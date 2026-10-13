"""The /job-engine follow-up planner uses the engine's own gaps, and this test fails the moment the
site's offsets drift from the engine's code. Run: python -m pytest tests -q
"""
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import jobstats  # noqa: E402
import main  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    monkeypatch.setattr(jobstats, "fetch", lambda: None)
    return main.app.test_client()


@pytest.fixture
def html(client):
    r = client.get("/job-engine")
    assert r.status_code == 200
    return r.get_data(as_text=True)


def _engine_checkout():
    """Kevin's real job-outreach-engine checkout, or None. ROOT's sibling first; from a
    .worktrees/TASK-n checkout, the main checkout the worktree belongs to (trusted only when ROOT
    is itself the toplevel of its git tree), as tests/test_public_console_demo.py does for the bank."""
    sibling = ROOT.parent / "job-outreach-engine"
    if (sibling / "pipeline_utils.py").exists():
        return sibling
    try:
        top, common = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--show-toplevel", "--git-common-dir"],
            cwd=ROOT, capture_output=True, text=True, timeout=5,
        ).stdout.splitlines()[:2]
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    if not top or Path(top).resolve() != ROOT:
        return None
    main_checkout = Path(common).resolve().parent.parent / "job-outreach-engine"
    return main_checkout if (main_checkout / "pipeline_utils.py").exists() else None


def _offsets(html):
    root = re.search(r'<div class="data-card followup-planner"[^>]*>', html, re.S).group(0)
    return {k: int(v) for k, v in re.findall(r'data-([\w-]+)="(\d+)"', root)}


def _const(src, pattern):
    m = re.search(pattern, src, re.M)
    assert m, f"constant not found in the engine: {pattern}"
    return int(m.group(1))


def test_followup_offsets_match_the_engines_own_constants(html):
    engine = _engine_checkout()
    if engine is None:
        pytest.skip(f"job-outreach-engine not found beside {ROOT.parent} or the main checkout - offsets unchecked")
    src = (engine / "pipeline_utils.py").read_text(encoding="utf-8", errors="replace")
    followup_1 = _const(src, r"^FOLLOWUP_1_DAYS = (\d+)")
    followup_2 = _const(src, r"^FOLLOWUP_2_DAYS = (\d+)")
    bury = _const(src, r"^FOLLOWUP_BURY_DAYS = (\d+)")
    cold_nudge = _const(src, r"^CARMEN_LADDER_DAYS_COLD = \((\d+),\)")
    grace = _const(src, r"^CARMEN_KILL_GRACE_DAYS = (\d+)")
    reply = _const(src, r"^REPLY_FOLLOWUP_DAYS = (\d+)")
    got = _offsets(html)
    assert got["app-followup"] == followup_1
    assert got["app-close"] == bury
    assert got["cold-nudge"] == cold_nudge
    assert got["cold-close"] == cold_nudge + grace
    assert got["reply-checkback"] == reply
    assert followup_2 not in got.values(), "the retired FOLLOWUP_2 rung must not be shown"


def test_followup_planner_has_exactly_the_five_offsets_and_no_retired_rung(html):
    got = _offsets(html)
    assert set(got) == {"app-followup", "app-close", "cold-nudge", "cold-close", "reply-checkback"}


def test_followup_planner_is_client_side_only(html):
    start = html.index('id="followup-planner"')
    block = html[start:html.index("</script>", start)]
    assert "fetch(" not in block and "XMLHttpRequest" not in block and "localStorage" not in block
    assert not re.search(r'<script[^>]+src=', block)


def test_followup_planner_has_its_own_heading_and_the_static_gaps_without_js(html):
    assert '<h2 class="section-heading">Follow-Up Planner</h2>' in html
    assert "follow up 10 days after you send it" in html  # readable with JS off


def test_followup_planner_job_engine_template_holds_no_digits_for_it():
    src = (ROOT / "templates" / "job_engine.html").read_text(encoding="utf-8")
    assert '{% include "_followup_planner.html" %}' in src


def test_followup_planner_every_dataset_name_the_script_reads_is_on_the_root(html):
    """No test executes the JS, so pin the names it reads: a rename would turn dates into NaN."""
    start = html.index('id="followup-planner"')
    script = html[html.index("<script>", start):html.index("</script>", start)]
    read = {re.sub(r"([A-Z])", lambda m: "-" + m.group(1).lower(), n) for n in re.findall(r"[^\w.]d\.(\w+)", script)}
    assert read and read <= set(_offsets(html)), read - set(_offsets(html))
