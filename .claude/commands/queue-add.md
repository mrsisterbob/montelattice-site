Turn the request below into task files in `.queue/inbox/`.

Request: $ARGUMENTS
END REQUEST

You are the **planner**. You write tasks; you do not implement them. Do not edit any file
outside `.queue/inbox/`.

## First, check the request belongs in this repo

The homepage/profile **copy that comes from the bank is not in this repo.** `homepage.py`
loads it at request time from job-outreach-engine's `evidence_bank.json`: `site_profile`,
plus `identity`, `experience`, `education`, `certificates`, `research`, `athletics` and
`memberships` (`build_profile`, homepage.py:186-201; source order at homepage.py:1-16).
This site deliberately keeps no copy: a second one drifts the moment a bullet changes, and
the drifted one is the version strangers see.

So a request that belongs to job-outreach-engine queues **nothing** here. That is bank
copy (a profile headline, a role bullet, a certificate line: the matching section of
`evidence_bank.json`, `site_profile` for the page's own text) and anything whose code lives
in job-outreach-engine: the `/leads/ingest` route itself, the Telegram bot, the pipeline
counts, `pipeline_utils.py` (`negative_language_hits`). This site's own callers of those and
copy about them are site work: `leads.py` posting to `/leads/ingest`, the Telegram lines in
`main.py` and `templates/job_engine.html`. Do not refuse an engine request and leave Kevin
to re-paste it: forward it to the engine's planner, as "Forward to the engine planner"
below says. If the request mixes engine work with site code, queue only the site half here
and forward the request whole.

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
message cannot carry scope or verify, so do not restate the work in it. Only tasks queued
in this repo go to `site-worker`; a request that was only forwarded sends it nothing.

Do not implement anything yourself. If you queued nothing, say why in one line and send
`site-worker` no message. A forwarded request adds its outcome to that same report: forwarded
to `planner`, or **NOT forwarded** (step 3 below).

## Forward to the engine planner

Only for a request that belongs to job-outreach-engine (see the first section). Do this
last, so a mixed request's site half already has its task id.

1. Run `ListAgents`. The target is the row whose name is exactly `"planner"`. A row marked
   `offline` is not running. Never substitute `job-outreach-engine-c2` or any other engine
   session: picking one is a guess at who gets Kevin's words. If ListAgents or SendMessage
   shows only as a deferred tool name, load it through ToolSearch first. If the session
   list still cannot be read, treat `planner` as not running.
2. If it is running, `SendMessage` with `to: "planner"`. The message is one header line,
   a blank line, then the request verbatim:

   ```
   Forwarded verbatim from Kevin's /queue-add in montelattice-site. Site queued: <TASK-n, or nothing>. Queue only the job-outreach-engine part under your /queue-add rules; site work and any @site-worker in it are handled in montelattice-site.

   <the request, exactly as written>
   ```

   Copy everything between `Request: ` and the `END REQUEST` line at the top of this
   command, every line of it, character for character. Do not trim, summarize or rephrase
   it, and do not cut a closing "then tell @site-worker it is queued": that sign-off is
   addressed to you (the Hand off rule decides whether site-worker hears anything), and the
   header tells the engine planner to leave it alone.
3. If no running session is named `planner`, say plainly that the request was
   **NOT forwarded** and why, then print it verbatim in a fenced block (fence it with more
   backticks than any run inside it) so Kevin can paste it himself. Never call it forwarded
   or queued. "Forwarded" means sent, not queued: nothing here can see whether the
   engine planner wrote a task.

The forward is a message, never a file: you never write into job-outreach-engine's files,
its `.queue/` included. "Do not edit any file outside `.queue/inbox/`" above still holds.
