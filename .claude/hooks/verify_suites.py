"""Stop hook: refuse to end a turn that leaves the site's test suite red.

Ported from job-outreach-engine/.claude/hooks/verify_suites.py. Same contract, different
suite: this repo's tests live in tests/ and run on the system Python (there is no .venv).

Every rule in .claude/commands/queue-run.md is advisory - prose a worker chooses to follow.
This one is not. The turn does not end until pytest is green.

Contract (docs: code.claude.com/docs/en/hooks):
  stdin  - JSON with stop_hook_active, cwd, ...
  stdout - {"decision": "block", "reason": "..."} to keep the turn open, or nothing
  exit 0 either way; a non-zero exit is a broken hook, not a failed check

stop_hook_active is the loop guard: when it is true the previous block is already being
worked on, so blocking again would spin.

Written in Python because this machine has no jq, and a hook that cannot parse its input
fails open - which looks exactly like a passing check.
"""

import json
import os
import subprocess
import sys

TEST_DIR = "tests"
TIMEOUT_SECONDS = 300
# Three rev-parse calls run before pytest. 300 + 3*5 stays under the 330s settings.json
# timeout, so a hang still reaches the TimeoutExpired block instead of being killed silently.
GIT_TIMEOUT_SECONDS = 5


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    if payload.get("stop_hook_active"):
        return

    cwd = tree_under_test(payload.get("cwd"))

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", TEST_DIR, "-q", "--no-header",
             "-p", "no:cacheprovider"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        block(f"The site tests did not finish within {TIMEOUT_SECONDS}s. Something is "
              "hanging - find it before ending the turn.")
        return
    except Exception as exc:
        block(f"Could not run the site tests: {exc}. The turn cannot be verified.")
        return

    if result.returncode == 0:
        return

    tail = failure_summary(result.stdout or result.stderr or "")
    block(
        f"The site tests are RED in {cwd}, so this turn is not done.\n\n"
        f"{tail}\n\n"
        "Fix the failures and run `python -m pytest tests -q` again. If the change is "
        "genuinely correct and the test encodes the old behavior, say so explicitly and "
        "explain why - do not delete or skip a test to get to green."
    )


def tree_under_test(session_cwd):
    """The root of the git tree this session is working in.

    A worker cd'd into .worktrees/TASK-n/ gets its own worktree tested, so its half-finished
    edit never blocks the planner, and theirs never block it. A shell in a subfolder resolves
    to its tree's root, so pytest still finds tests/.

    The tree must belong to THIS repo: same git common dir as the repo the hook lives in,
    which admits the main checkout and every worktree of it. A shell that has wandered into
    another repo with its own tests/ (crypto-trading-engine) would otherwise run that suite,
    get a green and pass the turn without the site suite ever running.

    Falls back to the repo this hook lives in when the cwd is missing, outside any git tree,
    in another repo, or a tree without tests/ - a hook that cannot find the tests must test
    the main repo, never silently test nothing.
    """
    fallback = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if not session_cwd:
        return fallback
    try:
        top = git_rev_parse(session_cwd, "--show-toplevel")
        if not top or not os.path.isdir(os.path.join(top, TEST_DIR)):
            return fallback
        ours = git_rev_parse(fallback, "--path-format=absolute", "--git-common-dir")
        theirs = git_rev_parse(session_cwd, "--path-format=absolute", "--git-common-dir")
    except Exception:
        return fallback
    if ours and theirs and same_path(ours, theirs):
        return top
    return fallback


def git_rev_parse(cwd, *args):
    return subprocess.run(
        ["git", "rev-parse", *args],
        cwd=cwd, capture_output=True, text=True, timeout=GIT_TIMEOUT_SECONDS,
    ).stdout.strip()


def same_path(a, b):
    """git returns forward slashes; os.path on Windows builds backslashes."""
    return os.path.normcase(os.path.normpath(a)) == os.path.normcase(os.path.normpath(b))


def failure_summary(output, max_lines=30):
    """Start at the FAILURES banner; -q output is mostly progress dots."""
    lines = output.strip().splitlines()

    for i, line in enumerate(lines):
        if "= FAILURES =" in line or "= ERRORS =" in line:
            return "\n".join(lines[i:i + max_lines])

    signal = [ln for ln in lines
              if ("::" in ln or " failed" in ln or " error" in ln)
              and not set(ln.strip()) <= {".", "F", "E", "s", "x", "%", "[", "]", " "}
              and not ln.strip().endswith("%]")]
    if signal:
        return "\n".join(signal[-max_lines:])

    return "\n".join(lines[-max_lines:])


def block(reason):
    json.dump({"decision": "block", "reason": reason}, sys.stdout)


if __name__ == "__main__":
    main()
