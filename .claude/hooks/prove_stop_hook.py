"""Prove the Stop hook blocks a red tree, passes a green one, and never tests another repo.

Pipes real Stop payloads through verify_suites.py as a subprocess - the same way Claude
Code runs it - against a throwaway detached worktree, so master's working tree is never
touched. Prints one line per case and exits non-zero if any case fails.

    python .claude/hooks/prove_stop_hook.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HOOK_DIR, "verify_suites.py")
SITE = os.path.dirname(os.path.dirname(HOOK_DIR))
PROBE = os.path.join(SITE, ".worktrees", "_hookproof")
OTHER_REPO = "C:/Users/kjmil/crypto-trading-engine"
FAILING_TEST = os.path.join("tests", "test_zz_hookproof.py")
EXPECTED_PASSED = "92 passed"

# A pytest plugin that records every urlopen URL and still makes the call, so the suite
# behaves exactly as it does without the spy.
NETSPY = '''
import os, urllib.request
_real = urllib.request.urlopen
def _spy(url, *args, **kwargs):
    target = getattr(url, "full_url", url)
    with open(os.environ["NETSPY_LOG"], "a", encoding="utf-8") as fh:
        fh.write(str(target) + "\\n")
    return _real(url, *args, **kwargs)
urllib.request.urlopen = _spy
'''

results = []


def check(name, ok, detail=""):
    results.append(ok)
    line = f"{'PASS' if ok else 'FAIL'}  {name}"
    if detail and not ok:
        line += f"  -- {detail}"
    print(line, flush=True)


def run_hook(cwd, hook=HOOK, stop_hook_active=False):
    payload = {"hook_event_name": "Stop", "stop_hook_active": stop_hook_active, "cwd": cwd}
    proc = subprocess.run(
        [sys.executable, hook],
        input=json.dumps(payload), capture_output=True, text=True, timeout=360,
    )
    return proc.returncode, proc.stdout.strip()


def as_block(stdout):
    try:
        out = json.loads(stdout)
    except ValueError:
        return None
    return out if out.get("decision") == "block" else None


def slashed(path):
    return os.path.normcase(os.path.normpath(path)).replace("\\", "/")


def git(*args, cwd=SITE):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                          timeout=60, check=True)


def main():
    print(f"interpreter: {sys.executable}")

    code, out = run_hook(SITE)
    check("1. green main tree is silent", code == 0 and out == "", f"exit={code} out={out!r}")

    if os.path.exists(PROBE):
        git("worktree", "remove", "--force", PROBE)
    git("worktree", "add", "--detach", PROBE, "HEAD")
    try:
        prove_on_probe()
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", PROBE], cwd=SITE,
                       capture_output=True, text=True)
        subprocess.run(["git", "worktree", "prune"], cwd=SITE, capture_output=True, text=True)
        check("cleanup: probe worktree removed", not os.path.exists(PROBE))

    print(f"{sum(results)}/{len(results)} checks passed")
    return 0 if all(results) else 1


def prove_on_probe():
    failing = os.path.join(PROBE, FAILING_TEST)
    with open(failing, "w", encoding="utf-8") as fh:
        fh.write("def test_hookproof_is_red():\n    assert 1 == 2\n")

    for label, cwd in (("worktree root", PROBE), ("worktree subfolder", os.path.join(PROBE, "tests"))):
        code, out = run_hook(cwd)
        blk = as_block(out)
        reason = slashed(blk["reason"]) if blk else ""
        ok = (code == 0 and blk is not None and "test_zz_hookproof" in reason
              and slashed(PROBE) in reason)
        check(f"2. failing worktree blocks ({label})", ok, f"exit={code} out={out[:300]!r}")

    code, out = run_hook(PROBE, stop_hook_active=True)
    check("5. loop guard: stop_hook_active on a red tree is silent",
          code == 0 and out == "", f"exit={code} out={out[:300]!r}")

    # Cross-repo: the session shell sits in crypto, which has its own green tests/. The hook
    # must test the site instead. A copy of the hook inside the red probe makes that
    # observable: if it tested crypto it would be silent, testing the site it blocks.
    # If crypto is missing, not a repo, or has no tests/, the hook falls back to the site
    # before the common-dir comparison is ever reached and both checks below pass vacuously.
    other_top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=OTHER_REPO,
                               capture_output=True, text=True).stdout.strip()         if os.path.isdir(OTHER_REPO) else ""
    check("4. precondition: other repo is a git tree with its own tests/",
          bool(other_top) and os.path.isdir(os.path.join(other_top, "tests")),
          f"{OTHER_REPO} toplevel={other_top!r}")
    sys.path.insert(0, HOOK_DIR)
    import verify_suites
    resolved = verify_suites.tree_under_test(OTHER_REPO)
    check("4. cross-repo cwd resolves to the site, not crypto",
          os.path.samefile(resolved, SITE), f"resolved to {resolved}")
    probe_hook = os.path.join(PROBE, ".claude", "hooks", "verify_suites.py")
    os.makedirs(os.path.dirname(probe_hook), exist_ok=True)
    shutil.copyfile(HOOK, probe_hook)
    code, out = run_hook(OTHER_REPO, hook=probe_hook)
    blk = as_block(out)
    reason = slashed(blk["reason"]) if blk else ""
    check("4. cross-repo cwd runs the site suite (red probe blocks)",
          code == 0 and blk is not None and "test_zz_hookproof" in reason
          and slashed(OTHER_REPO) not in reason, f"exit={code} out={out[:300]!r}")

    os.remove(failing)
    code, out = run_hook(PROBE)
    check("3. worktree with failing file deleted is silent",
          code == 0 and out == "", f"exit={code} out={out[:300]!r}")

    spy_dir = tempfile.mkdtemp(prefix="netspy_")
    try:
        with open(os.path.join(spy_dir, "hookproof_netspy.py"), "w", encoding="utf-8") as fh:
            fh.write(NETSPY)
        log = os.path.join(spy_dir, "urls.log")
        open(log, "w").close()
        env = dict(os.environ, NETSPY_LOG=log,
                   PYTHONPATH=os.pathsep.join(filter(None, [spy_dir, os.environ.get("PYTHONPATH")])))
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "tests", "-q", "-p", "hookproof_netspy",
             "-p", "no:cacheprovider"],
            cwd=PROBE, env=env, capture_output=True, text=True, timeout=300,
        )
        last = (proc.stdout.strip().splitlines() or [""])[-1]
        check(f"3. worktree suite: {EXPECTED_PASSED}, no failures",
              proc.returncode == 0 and last.startswith(EXPECTED_PASSED) and "failed" not in last
              and "error" not in last, f"exit={proc.returncode} last={last!r}")
        with open(log, encoding="utf-8") as fh:
            urls = [u for u in fh.read().splitlines() if u]
        github = [u for u in urls if "raw.githubusercontent.com" in u]
        # An empty log would also mean the spy never loaded, so it must have seen something.
        check(f"3. no raw.githubusercontent.com fetch ({len(urls)} urlopen calls seen)",
              bool(urls) and not github, f"{github[:3] or 'spy recorded nothing'}")
    finally:
        shutil.rmtree(spy_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
