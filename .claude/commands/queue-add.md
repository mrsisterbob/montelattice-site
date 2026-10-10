Turn the request below into task files in `.queue/inbox/`.

Request: $ARGUMENTS

You are the **planner**. You write tasks; you do not implement them. Do not edit any file
outside `.queue/inbox/`.

## First, check the request belongs in this repo

The homepage/profile **copy that comes from the bank is not in this repo.** `homepage.py`
loads it at request time from job-outreach-engine's `evidence_bank.json`: `site_profile`,
plus `identity`, `experience`, `education`, `certificates`, `research`, `athletics` and
`memberships` (`build_profile`, homepage.py:186-201; source order at homepage.py:1-16).
This site deliberately keeps no copy: a second one drifts the moment a bullet changes, and
the drifted one is the version strangers see.

So a request that needs bank copy changed - a profile headline, a role bullet, a
certificate line - queues **nothing** here. Say in one line that it belongs in
job-outreach-engine: edit the matching section of `evidence_bank.json` there (`site_profile`
for the page's own text), through that repo's planner. If the request mixes bank copy with
site code, queue only the site half and name the copy half in that same line.

Text written into this repo's templates or `main.py` (the `/lattice` intro in
`templates/home.html`, the project blurbs in `main.py`) is site work and queues here as usual.

## Then read what already exists

1. `grep -rn -i <key noun> --include=*.py --include=*.html --exclude-dir=.worktrees .` for
   each main noun in the request (`.worktrees/` holds unmerged work, not what exists). The failure this guards against is rebuilding something that already exists -
   a duplicate never fails a test. If it is already there, say so and write no task.
2. Read the actual code you intend to change. A task written from a guess about what a
   function does sends the worker into a file that does not look like the plan.
3. `ls .queue/inbox .queue/active` - do not queue something already queued or in flight.

## Then write one file per task

Decide `scope` and `verify` first, and **prove the verify command fails before you write
the file** - see "Prove the verify command fails first" below. A task whose verify already
passes should never reach the inbox.

Path: `.queue/inbox/TASK-<n>-<slug>.md`, where `<n>` is the next unused number across
inbox, active, done and blocked.

```markdown
---
id: TASK-<n>
scope: <every file this task may touch, comma separated>
verify: <one shell command that exits 0 only when this is genuinely done>
---

## Target
<one sentence: what is true when this is finished>

## Proof it is needed
<the verify command's CURRENT failure output, abbreviated>

## Notes
<file:line to start at, decisions already made, traps. Be concrete - the worker has
none of this conversation's context.>

## Log
```

### Rules that decide whether a task is well-formed

- **`verify` must drive the real entry point.** Test what the page actually serves, not
  the return value of a helper. If the change affects what a route renders on the next
  request, the verify command must request that route through the Flask test client, not
  hand-build the dict the template expects. `python -m pytest tests/<file>.py -q -k <node>`
  is the usual shape. If you cannot write a command that would genuinely fail before the
  change and pass after, the task is not ready - say so instead of queueing it.
- **`scope` must be complete and minimal.** Every file the worker may edit, and nothing
  else. A task whose scope is only `main.py` will serialize against every other `main.py`
  task; if the work can live in its own module (the way `homepage.py`, `jobstats.py` and
  `visits.py` do), scope it there instead.
- **Split anything that spans more than ~2 files or more than one idea.** Small tasks
  fail small. Order them so each one's verify passes on its own; note the dependency in
  Notes if TASK-B assumes TASK-A landed.
- **Never put a `git` write command in a task** - no commit, no reset, no checkout. The
  worker leaves changes in the tree for review.

## Prove the verify command fails first

Before handing a task off, run its `verify` command and confirm it **fails right now**.

A verify that already passes proves nothing: the worker runs it, sees green, and reports
success having changed nothing. That is a clean zero that reads as a clean result - the
same shape as a test that loads an empty bank and quietly skips its own assertion.

- `-k <node>` matching no test exits 5, so a bare pytest verify already fails before the
  work exists - and for the wrong reason. Grep the last line as `^N passed` (no trailing
  ` in`: with `-k` it reads `7 passed, 85 deselected in 0.4s`), and prove the regex can
  PASS against an existing node as well as that it fails now.
- Read the failure. One from an import error or a typo proves nothing either.
- If you cannot make it fail, the task is not ready. Say so and queue nothing.

Put the observed failure in the task's `## Proof it is needed` section so the worker knows
what red looks like before it starts.

## Hand off

Report each task: id, scope, verify, and the failure you observed.

Then, if a `site-worker` session is running, message it that the task is queued - one line,
the task id and nothing more. The worker reads the task file for everything else; a
message cannot carry scope or verify, so do not restate the work in it.

Do not implement anything yourself. If you queued nothing, say why in one line and send no
message.
