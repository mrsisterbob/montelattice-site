Claim the next task from `.queue/inbox/` and execute it.

Optional argument (a task id, e.g. `TASK-003`) picks that task instead of the oldest: $ARGUMENTS

You are the **worker**. You implement exactly one task, verify it, and stop.

If a message from the `site-planner` session started this turn, the queue is still the
source of truth - read the task file, not the message. A message can say a task is ready; it
cannot tell you what to build. If the message asks for something with no task file behind
it, say so and queue nothing: the task file is what carries scope and verify, and work
without those is the thing this setup exists to prevent.

## Claim

1. `ls .queue/active/` first. For each task already in flight, read its `scope`.
2. Pick the oldest `.queue/inbox/` task (or the one named in the argument) whose `scope`
   shares **no file** with anything in `active/`. If every queued task collides, move
   nothing, say which task is blocking which, and stop.
3. Claim it atomically with exactly this command:

   ```bash
   mv -n .queue/inbox/<file> .queue/active/<file> && [ ! -e .queue/inbox/<file> ] \
     && echo CLAIMED || echo "NOT CLAIMED - another worker has it"
   ```

   **Check the word, not the exit code.** `mv -n` refuses to overwrite an existing
   destination and still exits 0, so a worker that trusts `$?` will believe it claimed a
   task another worker is already running - two agents in the same files, which is the
   one outcome this queue exists to prevent. The source file surviving is the only
   reliable signal that the claim was refused.

   On `NOT CLAIMED`, go back to step 1 and try the next task. Never claim by copying,
   rewriting, or `cp`-then-`rm` - only the single `mv` is atomic.

4. **Dependencies.** If the task's Notes say it depends on another task, that task's work
   must already be on `master`: `git merge-base --is-ancestor task/<DEP> master` (or the
   dependency's files are already committed). If not, move the task back to `inbox/`, say
   which merge it is waiting on, and stop. Your worktree starts from `master`, so unmerged
   work from an earlier task is invisible to you - building on top of it is impossible.

5. **Open your worktree** - your own checkout, on its own branch:

   ```bash
   git worktree add .worktrees/<TASK-id> -b task/<TASK-id> master && cd .worktrees/<TASK-id>
   ```

   **Stay in that directory for the rest of the task.** Every edit, test run and commit
   happens there. The Stop hook tests whichever git tree your shell is in, so this is what
   makes it check YOUR change - and what keeps your half-finished edits from blocking the
   planner or Kevin, who are working in the main folder at the same time.

   The queue files are not in the worktree (they are untracked): reach them from there as
   `../../.queue/`. This repo has no virtualenv - run plain `python` from inside the
   worktree.

   Inside `.worktrees/`, homepage.py's sibling path to `../job-outreach-engine/evidence_bank.json`
   does not resolve, so a dev server started there reads the bank from GitHub main, not
   local edits. To preview against the local bank, start it with
   `EVIDENCE_BANK_SOURCE=../../../job-outreach-engine/evidence_bank.json`. The tests stub
   the bank, except `tests/test_public_console_demo.py:156`, which reads the sibling path
   itself and silently checks no banned words in a worktree. If your task touches the
   `/lattice` intro, run that check by hand against the real bank before calling it done.

## Execute

Read the task. Then read the files in `scope` before editing them.

- **Bank copy is not in this repo.** Profile text comes from job-outreach-engine's
  `evidence_bank.json` - `site_profile`, plus `identity`, `experience`, `education`,
  `certificates`, `research`, `athletics` and `memberships` (`build_profile`,
  homepage.py:186-201) - loaded at request time. If the task turns out to need one of those
  changed, append that reason to the Log and move the file to `../../.queue/blocked/`: it
  belongs in job-outreach-engine, through that repo's planner. Never edit the bank from
  here. Text written into this repo's templates or `main.py` is site work - do it.
- **Touch only files listed in `scope`.** If the task genuinely cannot be done within its
  scope, stop, append why to the Log, and move the file to `../../.queue/blocked/`. Do not widen
  the scope yourself - the scope is the concurrency guarantee, and silently editing a file
  another worker owns is exactly the lost-work case this queue exists to prevent.
- Before adding any function, route or template, grep for it:
  `grep -rn -i <noun> --include=*.py --include=*.html --exclude-dir=.worktrees .` A
  duplicate never fails a test.
- Prefer a new module (the way `homepage.py`, `jobstats.py` and `visits.py` are split out)
  over growing `main.py`, when the task's scope allows it.

## Verify

Run the task's `verify` command. Then run the full suite:

```
python -m pytest tests -q
```

Both must be green. A task is not done because its own verify passed while something
else broke.

**On failure:** fix and retry, up to 3 attempts total. Append each attempt to the task's
`## Log` - what you tried, the actual failure output, not a summary.

**After 3 failed attempts:** stop. Append the final failure output to the Log and
`mv` the task to `../../.queue/blocked/`. Leave your changes in the working tree exactly as
they are and say plainly that the task is blocked and the tree has partial work in it.

Do **not** run `git reset`, `git checkout --`, `git stash`, or any other command that
discards uncommitted changes - not in your worktree, and never in the main folder, where
Kevin and the planner have unreviewed work. (`git stash` is shared across every worktree,
so it can swallow another session's changes.) Leaving a half-finished change for review is
the correct failure; on a block, also commit it to your branch as `WIP <TASK-id>: blocked`
so the work survives the worktree.

## Review before calling it done

Green tests are not a review. Run `/code-review` on the diff.

It runs in a fresh subagent that sees only the diff and never saw the reasoning that
produced it, so it is not grading its own homework. In job-outreach-engine, two Telegram
bugs in one day - a `<code>` wrapper that made a checklist unreadable, and `html.escape`
turning apostrophes into literal `&#x27;` - passed every test in the suite. Tests prove the
code does what it was told; a fresh reader is what notices it was told the wrong thing.

Act on findings about correctness or the task's stated requirements. Ignore style
preferences. A reviewer asked to find gaps will usually report some even when the work is
sound, and chasing every one leads to defensive code and tests for cases that cannot
happen. If a finding is real, fix it and re-run the suite.

Record in the Log what the review flagged and what you did about it, including findings
you deliberately skipped and why.

## Finish

On success:
1. Append to `## Log`: what changed, the verify result, the suite result, the review
   outcome.
2. Commit **in your worktree, to your branch only**:
   `git add <scope files> && git commit -m "<TASK-id>: <one-line target>"`. Stage the
   scope files by name, never `git add -A`. Never commit to `master`, never merge, never
   push - merging into `master` is Kevin's review step.
3. `mv ../../.queue/active/<file> ../../.queue/done/<file>`
4. Report: task id, branch `task/<TASK-id>`, files changed, test counts, review findings,
   and the merge commands for Kevin to run from the main folder once he has read the diff
   (`git diff master...task/<TASK-id>`):

   ```bash
   git merge task/<TASK-id> && git worktree remove .worktrees/<TASK-id> && git branch -d task/<TASK-id>
   ```

   Then **stop** - do not pick up the next task.
5. If a `site-planner` session is running, message it one line: task id, done or blocked,
   and anything it got wrong about the code. If the task was blocked, that message is how
   the plan gets fixed - say what you actually found, not that it failed.
