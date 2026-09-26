"""Measure the build figures on the profile page and write them to data/build_stats.json.

Run on Kevin's machine, where every repo is checked out side by side under the same parent:

    python build_stats.py

Render has only this repo, so production never measures anything. It reads the committed
snapshot (see buildstats.py), which is why the figures refresh when this script is re-run and
the JSON is committed and deployed, and not otherwise.

Two figures, both measured, neither estimated:
  commit_hours   Distinct clock-hours ("%Y-%m-%d %H" of the author date) containing at least one
                 commit, unioned across every repo so an hour with commits in two repos counts
                 once. A FLOOR, not a total: hours with no commit (debugging, reading, deploys)
                 and work done before a repo's first commit are invisible to it.
  tracked_lines  Lines in git-tracked code files only (CODE_EXTENSIONS), so virtualenvs, build
                 artifacts, data dumps and lockfiles never inflate it.

A repo that is missing or fails to read is listed under "unreachable" and left out of both
figures. The script never fills a gap with a guess.
"""
from __future__ import annotations

import json
import os
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


def measure(parent: str = PARENT, repos: list[str] = REPOS) -> dict:
    hours: set[str] = set()
    per_repo, unreachable = {}, []
    first = last = None
    for name in repos:
        path = os.path.join(parent, name)
        try:
            h = commit_hours(path)
            lines = tracked_lines(path)
        except (OSError, subprocess.CalledProcessError):
            unreachable.append(name)
            continue
        hours |= h
        if h:
            first = min(first or min(h), min(h))
            last = max(last or max(h), max(h))
        per_repo[name] = {"commit_hours": len(h), "tracked_lines": sum(lines.values()), "by_extension": lines}
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
