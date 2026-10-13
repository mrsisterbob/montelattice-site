"""/queue-run pushes `master` itself after a green merge (2026-10-13: Kevin asked for the worker to
push; the Render deploy is his), with one plain `git push origin master`, and never on a held,
conflicted, reverted or red path. A rejected push is reported and stops the loop; it is never
forced, rebased, reset or pulled through. The first group pins the command's instructions; the
second RUNS the push block it contains against a real bare remote on this machine, no network.
Run: python -m pytest tests/test_queue_run_push.py -q
"""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
QUEUE_RUN = (ROOT / ".claude" / "commands" / "queue-run.md").read_text(encoding="utf-8")
README = (ROOT / ".queue" / "README.md").read_text(encoding="utf-8")
BANNED = ["--force", "--force-with-lease", " -f", "+master", "rebase", "reset", "pull", "fetch", "merge"]


def _step7():
    start = QUEUE_RUN.index("7. **Green on `master`:** only now")
    end = QUEUE_RUN.index("8. Report one line")
    return QUEUE_RUN[start:end]


def _push_block():
    blocks = re.findall(r"```bash\n(.*?)```", QUEUE_RUN, re.S)
    found = [b for b in blocks if "git push origin master" in b]
    assert len(found) == 1, "exactly one fenced bash block carries the push"
    return found[0]


# --- the instructions ----------------------------------------------------------------------------

def test_the_push_is_a_plain_git_push_origin_master():
    assert "git push origin master" in QUEUE_RUN
    block = _push_block()
    for word in BANNED:
        assert word not in block, (word, block)


def test_the_push_comes_after_the_green_rerun_and_the_done_move_and_before_the_lock_is_released():
    rerun = QUEUE_RUN.index("6. **Re-run the suite on `master`")
    step7 = QUEUE_RUN.index("7. **Green on `master`:** only now")
    done = QUEUE_RUN.index("mv .queue/active/<file> .queue/done/<file>", step7)
    push = QUEUE_RUN.index("git push origin master", step7)
    release = QUEUE_RUN.index("rmdir .queue/merge.lock", step7)
    assert rerun < done < push < release


def test_never_push_is_gone_and_the_no_push_paths_are_named():
    assert "Never push." not in QUEUE_RUN
    step7 = " ".join(_step7().split()).lower()
    for path in ("held merge", "conflict", "already up to date", "revert", "red"):
        assert path in step7, path
    assert "never push" in step7


def test_a_rejected_push_stops_the_loop_and_is_never_forced_or_retried():
    step7 = " ".join(_step7().split())
    assert "PUSH REJECTED" in step7 and "stop the loop" in step7 and "keep the task in `done/`" in step7
    assert "never forced, rebased, reset" in step7
    assert "--force" not in QUEUE_RUN.replace("never\n   `--force`", "")


def test_the_report_line_and_the_guard_summary_carry_the_push():
    assert "pushed <hash>" in QUEUE_RUN and "push rejected" in QUEUE_RUN
    assert "three: a `--no-ff` merge, a `git revert`, and a plain" in QUEUE_RUN


def test_the_readme_says_the_same():
    assert "git push origin master" in README
    assert "2026-10-13" in README and "Render" in README


# --- the block, run for real ---------------------------------------------------------------------

def _bash():
    for candidate in (r"C:\Program Files\Git\bin\bash.exe", r"C:\Program Files (x86)\Git\bin\bash.exe"):
        if Path(candidate).is_file():
            return candidate
    found = shutil.which("bash")
    assert found, "no bash on this machine to run the push block"
    return found


def _git(cwd, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd, check=True,
                          capture_output=True, text=True, encoding="utf-8").stdout.strip()


def _commit(repo, name):
    (Path(repo) / name).write_text(name, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", name)


def _repos(tmp_path):
    remote = tmp_path / "remote.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "master", str(remote))
    work = tmp_path / "work"
    _git(tmp_path, "clone", "-q", str(remote), str(work))
    _git(work, "checkout", "-q", "-B", "master")
    _commit(work, "seed")
    _git(work, "push", "-q", "origin", "master")
    return remote, work


def _run_block(work):
    return subprocess.run([_bash(), "-c", _push_block()], cwd=work, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def test_happy_path_pushes_and_reports_the_hash(tmp_path):
    remote, work = _repos(tmp_path)
    _commit(work, "task")
    head = _git(work, "rev-parse", "HEAD")
    out = _run_block(work).stdout
    assert f"PUSHED {head}" in out, out
    assert _git(remote, "rev-parse", "master") == head


def test_rejected_push_is_reported_and_nothing_is_forced_or_pulled(tmp_path):
    remote, work = _repos(tmp_path)
    other = tmp_path / "other"
    _git(tmp_path, "clone", "-q", str(remote), str(other))
    _commit(other, "ahead")
    _git(other, "push", "-q", "origin", "master")
    ahead = _git(other, "rev-parse", "HEAD")
    _commit(work, "mine")
    head = _git(work, "rev-parse", "HEAD")
    tracking = _git(work, "rev-parse", "origin/master")
    result = _run_block(work)
    assert "PUSH REJECTED" in result.stdout and "PUSHED" not in result.stdout, result
    assert _git(work, "rev-parse", "HEAD") == head                  # master untouched, still merged locally
    assert _git(remote, "rev-parse", "master") == ahead             # nothing forced
    assert _git(work, "rev-parse", "origin/master") == tracking     # no fetch or pull ran
