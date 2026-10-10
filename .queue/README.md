# The task queue

A mailbox between two Claude Code terminals: a **site-planner** (auto mode - plan mode blocks its writes to .queue/inbox/) that writes
tasks, and a **site-worker** (bypass permissions) that executes them one at a time. Same
loop as job-outreach-engine's `.queue/`, rewritten for this repo.

## Copy does not live here

Profile text from the bank is not in this repo. `homepage.py` loads it at request time from
job-outreach-engine's `evidence_bank.json` - `site_profile`, plus `identity`, `experience`,
`education`, `certificates`, `research`, `athletics` and `memberships` (`build_profile`,
homepage.py:186-201; source order at homepage.py:1-16). A change to that copy is queued in
job-outreach-engine, not here: `/queue-add` here refuses it in one line, and `/queue-run`
moves a task that turns out to need one to `blocked/`. Text written into this repo's
templates or `main.py` is ordinary site work.

## State is the directory, not a field

```
inbox/    queued, nobody has claimed it      planner writes here
active/   a worker is on it right now        worker only
done/     verify passed                      worker only
blocked/  verify failed 3x, or scope clash   worker only
```

One task is one file, and the directory it sits in IS its state. Claiming a task is a
single `mv -n`, an atomic rename: two workers cannot both claim the same task, because
the second rename refuses to overwrite the destination.

Watch the one trap: `mv -n` refuses **silently and still exits 0**. The only reliable
test of a claim is whether the source file disappeared, which is what `/queue-run` checks.
Plain `mv`, not `git mv` - a fresh task file is untracked, so `git mv` fails outright, and
staging every task would drag queue churn through the index you are trying to review.

**This is deliberately not a single QUEUE.md.** A shared markdown file has no locking.
The planner appending TASK-004 while the worker rewrites the file to mark TASK-001 done
silently loses one of the two writes - no error, no trace, the task just never runs.
One writer per file is what makes the loss impossible rather than unlikely.

## Task file format

Filename: `TASK-<n>-<short-slug>.md`

```markdown
---
id: TASK-003
scope: jobstats.py, tests/test_job_dashboard.py
verify: python -m pytest tests/test_job_dashboard.py -q
---

## Target
One sentence describing what "done" looks like.

## Notes
Anything the worker needs that is not obvious from the scope: a file:line to start at,
a prior decision, a trap to avoid.

## Log
<!-- worker appends here: attempt, verify output, outcome -->
```

### `scope` is load-bearing

It lists every file the task may touch, and the worker refuses a task whose scope
overlaps anything already in `active/`. That is the entire concurrency story: `main.py`
and the shared templates are what most tasks want, so two workers in the same file at
once is the realistic way to lose work. The guard makes the collision a refusal instead.

### `verify` is required

A command that exits 0 when the task is genuinely done. Not "the helper returns the right
thing" - the command that proves the page actually serves it on the next request. A task
without a real verify command does not go in the queue.

## Running it

One-time setup, per machine:

```
# in the planner terminal (auto mode, shift+tab - NOT plan mode)
/rename site-planner

# in the worker terminal (bypass permissions)
/rename site-worker
```

Then, per task - you type one line, in the planner only:

```
/queue-add <what you want built>, then tell @site-worker it is queued
```

The planner writes the task file and sends `@site-worker` a message. **The worker is idle,
so Claude Code starts a new turn with that message** - it wakes up, runs `/queue-run`, and
works. You do not type in the worker terminal.

Nothing watches the `inbox/` directory; no file appearing there triggers anything. The
message is what wakes the worker, not the file. If messaging is off or the planner is not
running, `/queue-run` typed by hand does the same thing.

This needs `crossSessionInbound: "accept"` in your USER settings (`~/.claude/settings.json`,
or `/config` -> "Messages from your other sessions"). The copy in this repo's
`.claude/settings.json` does nothing on its own: a project file may only make that key
stricter, never `accept`. Without the user setting, messages between an auto-mode and a
bypass session are held for approval in both directions and dropped after five minutes -
the worker would look like it was ignoring the planner.

`/queue-status` in either terminal shows the whole queue without changing anything.

## The Stop hook

`.claude/hooks/verify_suites.py` runs `python -m pytest tests -q` when a turn ends and
blocks it if the suite is red. It blocks once per stop: when Claude stops again with
`stop_hook_active` set, the hook lets the turn end rather than spin, so a second stop can
still end red. It tests the git tree the session's shell is in -
the main checkout, or a worker's `.worktrees/TASK-n/` - so each session only answers for
its own work. It only accepts this repo's trees: a shell that has wandered into another
repo with its own `tests/` gets this site's suite run, never the other repo's.
`.claude/hooks/prove_stop_hook.py` proves all of that against a throwaway worktree.

## The worker works in its own worktree, and you merge

Each claimed task gets its own checkout: `.worktrees/TASK-n/` on branch `task/TASK-n`,
started from `master`. The worker edits, tests and commits there, never on `master`.

Why: with one shared folder, every agent's Stop hook would test every other agent's
half-finished edits, and one session's mid-save file turns another session's turn red.

Your review step is the merge, from the main folder:

```bash
git diff master...task/TASK-n          # read it
git merge task/TASK-n && git worktree remove .worktrees/TASK-n && git branch -d task/TASK-n
```

Two consequences to know:
- **A task can only build on merged work.** The worktree starts from `master`, so if
  TASK-4 needs TASK-3, merge TASK-3 first - the worker checks and waits rather than
  starting blind.
- **The worker never touches `master`** - no commit, merge, push, reset or stash there.
  Your uncommitted work in the main folder is never in its reach.

Known gap: inside `.worktrees/`, homepage.py's sibling path
(`../job-outreach-engine/evidence_bank.json`) does not resolve, so a dev server started in a
worktree reads the bank from GitHub main, not your local edits. Start it with
`EVIDENCE_BANK_SOURCE=../../../job-outreach-engine/evidence_bank.json` to preview the local
bank. The tests stub the bank (`EVIDENCE_BANK_SOURCE` or a `load_bank` monkeypatch) and make
no GitHub fetch. The exception is `tests/test_public_console_demo.py:156`, which reads the
sibling bank directly and silently checks no banned words when it is missing
(job-outreach-engine's queue has TASK-10 to fix that; drop this note once it merges). For
that one check, a green worktree run is weaker than a green run on `master`.
