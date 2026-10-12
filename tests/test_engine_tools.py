"""tools.py is the only list of tool logos the site may show. Every entry must be a service
job-outreach-engine really calls, so this re-checks each entry's evidence string against the real
engine checkout. A missing checkout SKIPS visibly (and the task's verify refuses a skip): an
unchecked list is not a verified one. Run: python -m pytest tests -q
"""
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import tools  # noqa: E402

# In the engine, but not called by it (search links, filter lists, profile URLs). Never shown.
EXCLUDED = ("Apollo", "Jooble", "SmartRecruiters", "Workable", "Indeed", "LinkedIn")


def _engine_checkout():
    """Kevin's real job-outreach-engine checkout, or None when it is not on this machine.

    ROOT's sibling first (the main checkout). In a .worktrees/TASK-n checkout that sibling does not
    exist, so fall back to the main checkout the worktree belongs to: the parent of git's common
    dir, trusted only when ROOT is itself the toplevel of its git tree (same rule as
    tests/test_public_console_demo.py::_evidence_bank_path).
    """
    sibling = ROOT.parent / "job-outreach-engine"
    if (sibling / "main.py").exists():
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
    return main_checkout if (main_checkout / "main.py").exists() else None


def test_every_tool_names_a_call_site_that_exists_in_the_engine():
    engine = _engine_checkout()
    if engine is None:
        pytest.skip(f"job-outreach-engine not found beside {ROOT.parent} or the main checkout - evidence unchecked")
    for tool in tools.TOOLS:
        path = engine / tool.engine_file
        assert path.is_file(), (tool.name, tool.engine_file)
        text = path.read_text(encoding="utf-8", errors="replace")
        assert tool.needle in text, (tool.name, tool.engine_file, tool.needle)


def test_the_list_is_not_empty_and_names_are_unique():
    names = [t.name for t in tools.TOOLS]
    assert len(names) >= 10
    assert len(set(names)) == len(names)


def test_no_excluded_name_appears_in_tools_py():
    source = (ROOT / "tools.py").read_text(encoding="utf-8").lower()
    for name in EXCLUDED:
        assert name.lower() not in source, name


def test_every_mark_is_plain_path_data_with_no_hardcoded_colour():
    for tool in tools.TOOLS:
        if tool.svg_path is None:
            continue
        assert re.fullmatch(r"[MmLlHhVvCcSsQqTtAaZz0-9eE.,\s+-]+", tool.svg_path), tool.name
        assert "#" not in tool.svg_path and "fill" not in tool.svg_path.lower(), tool.name
        assert tool.svg_viewbox == "0 0 24 24", tool.name


def test_marks_without_a_licensed_source_are_none_not_invented():
    # Simple Icons 16.35.0 has no icon for these; a made-up path would be a drawn-from-memory logo.
    for tool in tools.TOOLS:
        if tool.name in ("Lever", "Ashby", "Remotive", "JSearch", "Hunter", "Prospeo", "GetProspect"):
            assert tool.svg_path is None, tool.name
