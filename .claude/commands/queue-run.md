Claim the next task from `.queue/inbox/` and execute it.

Optional argument (a task id, e.g. `TASK-003`) picks that task instead of the oldest: $ARGUMENTS

You are the **worker**. You implement one task at a time, verify it, merge it into `master`,
and go back for the next one, until the inbox is empty or nothing left in it can run (see
"When the loop ends" at the bottom). Never push.

If a message from the `site-planner` session started this turn, the queue is still the
source of truth - read the task file, not the message. A message can say a task is ready; it
cannot tell you what to build. If the message asks for something with no task file behind
it, say so and queue nothing: the task file is what carries scope and verify, and work
without those is the thing this setup exists to prevent.

## Claim

1. `ls .queue/active/` first. For each task already in flight, read its `scope`.
2. Pick the oldest `.queue/inbox/` task (or the one named in the argument) that passes both
   checks below, reading its frontmatter and its dependency lines
   (`grep -inE 'depend|requires|after TASK|blocked on|TASK-[0-9]+' <file>`) **where it sits
   in the inbox**, before claiming it:
   - its `scope` shares **no file** with anything in `active/`;
   - every task its Notes say it depends on is in `.queue/done/` (step 4).

   A task that fails either check stays in the inbox; add it to a skip list you keep for
   this whole run and never pick it again in this run. Without that list, "oldest" picks
   the same waiting task every time round the loop and nothing behind it ever runs. If no
   task passes, move nothing, say which task is waiting on what, and end the loop.
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

4. **Dependencies** (checked in step 2, before the claim). A dependency is met only when its
   task file is in `.queue/done/` - `done/` means merged into `master`, because a task only
   moves there after its merge passes the suite on `master` (Finish, step 7). Do not check
   for the dependency's branch: Finish deletes it on every merge, so a branch-based check
   fails for exactly the dependencies that landed. Your worktree starts from `master`, so
   unmerged work from an earlier task is invisible to you - building on top of it is
   impossible.

5. **Open your worktree** - your own checkout, on its own branch, from the main folder
   (where every claim happens; Finish returns you there for the next task):

   ```bash
   git worktree add .worktrees/<TASK-id> -b task/<TASK-id> master && cd .worktrees/<TASK-id>
   ```

   **A re-queued task may already have a branch.** Every blocked, held or conflicted task
   keeps `task/<TASK-id>` (and usually `.worktrees/<TASK-id>`), so `-b` fails for it. Check
   `git branch --list task/<TASK-id>` first. If it exists, resume on it instead: use
   `.worktrees/<TASK-id>` as it is if that directory exists, otherwise
   `git worktree add .worktrees/<TASK-id> task/<TASK-id>`. Read the task's Log to see why it
   stopped. If the Log records a **revert** (Finish, step 6), the branch's commits are already
   in `master`'s history, so merging it again does nothing ("Already up to date"). Re-land
   the work on the branch first:

   ```bash
   git -C .worktrees/<TASK-id> merge --no-ff master -m "Bring master into task/<TASK-id>"   # brings the revert in
   git -C .worktrees/<TASK-id> revert --no-edit <revert-sha>                               # puts the work back as new commits
   ```

   then fix what turned `master` red, on top.

   If the Log records a **merge conflict** instead, the branch is on a stale base: bring
   `master` in first (`git -C .worktrees/<TASK-id> merge master`), resolve the conflict inside
   the task's `scope`, and re-verify before going on. Otherwise it conflicts the same way again.

   **Stay in the worktree while you build.** Every edit, test run and commit happens there.
   The Stop hook tests whichever git tree your shell is in, so this is what makes it check
   YOUR change - and what keeps your half-finished edits from blocking the planner or Kevin,
   who are working in the main folder at the same time. **Finish starts by going back to the
   main folder** (its steps 3-8 run there).

   The queue files are not in the worktree (they are untracked): reach them from there as
   `../../.queue/`. This repo has no virtualenv - run plain `python` from inside the
   worktree.

   Inside `.worktrees/`, homepage.py's sibling path to `../job-outreach-engine/evidence_bank.json`
   does not resolve, so a dev server started there reads the bank from GitHub main, not
   local edits. To preview against the local bank, start it with
   `EVIDENCE_BANK_SOURCE=../../../job-outreach-engine/evidence_bank.json`. The tests stub
   the bank, except the `/lattice` banned-words test in `tests/test_public_console_demo.py`,
   which finds the real bank beside the main checkout from a worktree, and skips visibly
   (never passes empty) when it cannot. A skip there means banned words went unchecked.

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
  scope, stop, append why to the Log, and move the file to `../../.queue/blocked/` (then
  commit any partial work as `WIP <TASK-id>: blocked`, go back to the main folder and continue
  the loop, as under "After 3 failed attempts"). Do not widen
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
python -m pytest tests -q -p no:cacheprovider
```

Both must be green. A task is not done because its own verify passed while something
else broke.

**On failure:** fix and retry, up to 3 attempts total. Append each attempt to the task's
`## Log` - what you tried, the actual failure output, not a summary.

**After 3 failed attempts:** stop. Append the final failure output to the Log and
`mv` the task to `../../.queue/blocked/`. Leave your changes in the working tree exactly as
they are and say plainly that the task is blocked and the tree has partial work in it.
Commit it to your branch as `WIP <TASK-id>: blocked` (stage the changed files by name, never
`git add -A`) so the work survives, go back to the
main folder, and continue the loop with the next task. Nothing was merged, so `master` is
untouched.

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

On success - verify, the suite and the review all green:

0. **Go back to the main folder** (`cd` out of `.worktrees/<TASK-id>`). Steps 3-8 run there,
   and every worktree command below is written as `git -C .worktrees/<TASK-id> ...` so it
   works from either place.
1. Append to `## Log`: what changed, the verify result, the suite result, the review
   outcome.
2. Commit **to the task's branch**:
   `git -C .worktrees/<TASK-id> add <scope files> && git -C .worktrees/<TASK-id> commit -m
   "<TASK-id>: <one-line target>"`. Stage the scope files by name, never `git add -A`.
3. **Take the merge lock, then check the main folder:**

   ```bash
   mkdir .queue/merge.lock && echo LOCKED || echo "LOCK HELD - another worker is merging"
   ```

   `mkdir` is atomic, so only one worker at a time runs steps 3-7 in the shared main
   folder; without it, one worker's suite run would include another's half-tested merge
   and revert the wrong task. On `LOCK HELD`, wait about a minute and retry; after ten
   tries, hold the task (append "merge held: lock" to the Log, `mv` it from `active/` to
   `blocked/`, keep the worktree and branch), stop the loop and tell Kevin the lock may be
   stale (`rmdir .queue/merge.lock` clears it). Release it (`rmdir .queue/merge.lock`) at the end of step 7 or on any exit
   from steps 3-6. An empty directory is invisible to git, so it never trips the check below.

   ```bash
   git status --porcelain
   git symbolic-ref --short HEAD
   out=$(mktemp); python -m pytest tests -q -p no:cacheprovider >"$out" 2>&1; rc=$?
   if [ $rc -eq 0 ]; then tail -n 1 "$out"; else tail -n 60 "$out"; fi
   rm -f "$out"; echo "exit=$rc"
   ```

   A green run prints one line, a red one its last 60. Read the printed `exit=` line, not
   the tool status: the wrapper itself always exits 0.

   - If `git status --porcelain` prints anything, or the branch is not `master`, **do not
     merge.** That output is Kevin's or the planner's unreviewed work, and a merge on top of
     it mixes their changes into yours. (The task files and `.worktrees/` are gitignored, so
     the queue itself never trips this.) Append the output to the Log,
     `mv .queue/active/<file> .queue/blocked/<file>` with "merge held: main folder not
     clean", keep the worktree and branch, release the lock, tell Kevin, and **stop the
     loop**: every later merge would hit the same wall, and later tasks may depend on this one.
   - If the suite run (the **baseline**) is red, `master` was already broken before your
     merge. Do not merge - a red after it would be blamed on your task and reverted. Hold the
     task the same way ("merge held: master red before merge", with the failing test names),
     release the lock, and **stop the loop**. Keep the baseline's list of failing tests either way.
4. **Merge, always with `--no-ff`:**

   ```bash
   git merge --no-ff task/<TASK-id> -m "Merge <TASK-id>: <one-line target>"
   ```

   `--no-ff` is required. A fast-forward leaves no merge commit, and then step 6 has no
   single commit for `git revert -m 1` to undo. Right after it, run `git rev-parse HEAD` and
   keep that as the `<merge-sha>`. If the merge printed "Already up to date" it made no
   commit: there is nothing to revert, so skip step 6's revert and do not use `HEAD`.
5. **If the merge stops:**
   - **Conflict** (`git rev-parse -q --verify MERGE_HEAD` prints a sha): `git merge --abort`.
     The folder was clean at step 3, so this restores it exactly. Append the conflicting
     paths to the Log, `mv .queue/active/<file> .queue/blocked/<file>`, keep the worktree
     and branch, release the lock, tell Kevin, and continue the loop with the next task.
   - **Refused before starting** (that command prints nothing; e.g. "would be overwritten"
     because someone edited the main folder after step 3): nothing was merged and there is
     nothing to abort. Treat it as a held merge (step 3, first bullet) and stop the loop.
6. **Re-run the suite on `master`, from the main folder** (same command as the baseline,
   quiet output included).
   **If anything is red, first run `git status --porcelain` again.** If it prints anything,
   someone edited the main folder during the run, and the red cannot be pinned on your
   merge: do **not** revert. Append both outputs to the Log, leave the merge in place,
   release the lock, tell Kevin, and stop the loop. If it is still clean, the red is your
   merge's - undo it with a new commit, never by moving `master` back:

   ```bash
   git revert -m 1 --no-edit <merge-sha>
   ```

   Then re-run the suite. If `master` is green again, append the red output **and the revert
   commit's sha** to the Log, `mv .queue/active/<file> .queue/blocked/<file>`, keep the
   worktree and branch, release the lock, tell Kevin, and continue the loop. The branch alone
   cannot be merged again - its commits are already in `master`'s history - which is why the
   sha goes in the Log: Claim step 5 uses it to re-land the work. If `master` is **still**
   red after the revert, stop the loop and tell Kevin with the output - do not attempt a
   second fix.
7. **Green on `master`:** only now remove the worktree and branch, mark the task done, and
   release the lock. If the worktree has uncommitted changes, keep it and tell Kevin - never
   `--force`.

   ```bash
   git -C .worktrees/<TASK-id> status --porcelain
   git worktree remove .worktrees/<TASK-id> && git branch -d task/<TASK-id>
   mv .queue/active/<file> .queue/done/<file>
   rmdir .queue/merge.lock
   ```

   Removal waits until `master` is proven green, so a reverted merge still has its branch.
   `done/` therefore means merged into `master`; dependency checks (Claim, step 4) rely on it.
8. Report one line - task id, merged / blocked / held, test counts, review findings - and if
   a `site-planner` session is running, message it the same line plus anything it got wrong
   about the code. If the task was blocked, that message is how the plan gets fixed - say
   what you actually found, not that it failed. Then go back to **Claim** from the main folder.

**Telling Kevin** means a plain line in your own output, plus the planner message in step 8.
The same shape for every guard: what happened, the task id, and where the work is (branch
`task/<TASK-id>`).

**The only git writes on `master` are two: a `--no-ff` merge and a `git revert`.** Never push.
Never commit there directly, never reset, never stash.

## When the loop ends

Keep claiming until the inbox is empty, or until every task left in it is on this run's
skip list (Claim, step 2) - colliding in scope with `active/`, or waiting on a dependency
that is not in `done/`. A dependency sitting in `blocked/` means its dependents wait; name
them in the final report.

A "TASK-n queued" message from the planner that arrives mid-loop needs no action - the loop
already reads the inbox. The loop also stops early at a held merge (steps 3 and 5), at a
red it cannot pin on its own merge, or at a `master` that stays red after a revert (step 6).

**Where you end the turn.** The Stop hook tests the git tree your shell is in. End in the
main folder only if `git status --porcelain` is empty there - then the hook tests exactly
what you merged. If the main folder is dirty (every held-merge stop), `cd` into the held
task's worktree before you finish, so the hook tests your work and not Kevin's. If the
hook ever reports red in files outside the scope of the task you just ran, do not edit
them: report the failure and stop.

Final report: each task with its outcome, then what is left in the inbox and why it did
not run.
