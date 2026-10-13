"""Measure the build figures on the profile page and write them to data/build_stats.json.

It runs in two places, and both need every repo checked out side by side under one parent:

    python build_stats.py            # by hand, on Kevin's machine

and daily in .github/workflows/build-stats.yml, which publishes the JSON to the orphan branch
`build-stats` (never to master). It measures pushed history only.

Render has only this repo, so production never measures anything. buildstats.py reads the
`build-stats` branch and the committed snapshot and keeps the newer valid one (the committed
file also covers a failed fetch), so the figures stay current without a commit to master.

Two figures, both measured, neither estimated, plus a per-repo test-function count:
  commit_hours   Distinct clock-hours ("%Y-%m-%d %H" of the author date) containing at least one
                 commit, unioned across every repo so an hour with commits in two repos counts
                 once. A FLOOR, not a total: hours with no commit (debugging, reading, deploys)
                 and work done before a repo's first commit are invisible to it.
  tracked_lines  Lines in git-tracked code files only (CODE_EXTENSIONS), so virtualenvs, build
                 artifacts, data dumps and lockfiles never inflate it.

A third figure is kept per repo, never summed:
  test_functions Lines that start (after any indent) with `def test_` or `async def test_`,
                 across the repo's git-tracked .py files.
                 A static count of test FUNCTIONS, not of test cases run: a parametrized test
                 counts once, and a helper named test_*, or a line inside a string that looks
                 like one, counts too. It is read from the working tree, like tracked_lines.

A repo that is missing or fails to read is listed under "unreachable" and left out of both
figures (a failure while counting test functions marks the repo unreachable too). The script
never fills a gap with a guess.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(HERE)
REPOS = ["job-outreach-engine", "crypto-trading-engine", "montelattice-site", "docfiler", "budget-tracker"]
CODE_EXTENSIONS = (".py", ".gs", ".js", ".html", ".css")
SNAPSHOT_PATH = os.path.join(HERE, "data", "build_stats.json")


def _git(repo_path: str, *args: str) -> str:
    return subprocess.run(["git", "-C", repo_path, *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", check=True).stdout


def commit_hours(repo_path: str) -> set[str]:
    out = _git(repo_path, "log", "--format=%ad", "--date=format:%Y-%m-%d %H")
    return {line.strip() for line in out.splitlines() if line.strip()}


def tracked_lines(repo_path: str) -> dict[str, int]:
    """Lines per extension across tracked code files, counted like `wc -l` (newline count)."""
    counts: dict[str, int] = {}
    for rel in _git(repo_path, "ls-files", "-z").split("\0"):
        ext = os.path.splitext(rel)[1].lower()
        if not rel or ext not in CODE_EXTENSIONS:
            continue
        try:
            with open(os.path.join(repo_path, rel), "rb") as f:
                n = f.read().count(b"\n")
        except OSError:
            continue  # tracked but deleted from the working tree: not code that exists
        counts[ext] = counts.get(ext, 0) + n
    return counts


TEST_DEF = re.compile(r"^\s*(?:async\s+)?def test_", re.M)


def count_test_functions(repo_path: str) -> int:
    """Count of `def test_` lines in the repo's tracked .py files (see the module docstring)."""
    total = 0
    for rel in _git(repo_path, "ls-files", "-z").split("\0"):
        if not rel or os.path.splitext(rel)[1].lower() != ".py":
            continue
        try:
            with open(os.path.join(repo_path, rel), "r", encoding="utf-8", errors="replace") as f:
                total += len(TEST_DEF.findall(f.read()))
        except OSError:
            continue  # tracked but deleted from the working tree
    return total


def measure(parent: str = PARENT, repos: list[str] = REPOS) -> dict:
    hours: set[str] = set()
    per_repo, unreachable = {}, []
    first = last = None
    for name in repos:
        path = os.path.join(parent, name)
        try:
            h = commit_hours(path)
            lines = tracked_lines(path)
            tests = count_test_functions(path)
        except (OSError, subprocess.CalledProcessError):
            unreachable.append(name)
            continue
        hours |= h
        if h:
            first = min(first or min(h), min(h))
            last = max(last or max(h), max(h))
        per_repo[name] = {"commit_hours": len(h), "tracked_lines": sum(lines.values()), "test_functions": tests,
                          "by_extension": lines}
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit_hours": len(hours),
        "tracked_lines": sum(r["tracked_lines"] for r in per_repo.values()),
        "first_commit_hour": first,
        "last_commit_hour": last,
        "repos": per_repo,
        "unreachable": unreachable,
    }


if __name__ == "__main__":
    stats = measure()
    if not stats["repos"]:
        raise SystemExit("No repo was readable; snapshot left untouched.")
    os.makedirs(os.path.dirname(SNAPSHOT_PATH), exist_ok=True)
    with open(SNAPSHOT_PATH, "w", encoding="utf-8", newline="\n") as f:
        json.dump(stats, f, indent=2)
        f.write("\n")
    print(json.dumps({k: v for k, v in stats.items() if k != "repos"}, indent=2))
    for name, r in stats["repos"].items():
        print(f"  {name:24s} {r['commit_hours']:4d} commit-hours  {r['tracked_lines']:6d} lines  {r['by_extension']}")
