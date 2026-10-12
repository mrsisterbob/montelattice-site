"""/queue-run merges a green task into master itself, under a lock. These pin the command's
instructions, not what a model does with them. Run: python -m pytest tests/test_queue_run_merge.py -q
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUEUE_RUN = (ROOT / ".claude" / "commands" / "queue-run.md").read_text(encoding="utf-8")
README = (ROOT / ".queue" / "README.md").read_text(encoding="utf-8")


def test_merge_lock_is_taken_with_mkdir_and_released_with_rmdir():
    assert "mkdir .queue/merge.lock" in QUEUE_RUN
    assert "rmdir .queue/merge.lock" in QUEUE_RUN


def test_merge_is_no_ff_so_a_revert_has_one_commit_to_undo():
    assert "git merge --no-ff task/" in QUEUE_RUN
    assert "git revert -m 1" in QUEUE_RUN


def test_a_conflict_is_aborted_and_a_dirty_or_wrong_branch_holds_the_merge():
    assert "git merge --abort" in QUEUE_RUN
    assert "git status --porcelain" in QUEUE_RUN
    assert "git symbolic-ref --short HEAD" in QUEUE_RUN


def test_done_move_comes_after_the_merge_and_the_revert_path():
    merge = QUEUE_RUN.index("git merge --no-ff task/")
    revert = QUEUE_RUN.index("git revert -m 1 --no-edit")
    rerun = QUEUE_RUN.index("6. **Re-run the suite on `master`")
    done = QUEUE_RUN.index("mv .queue/active/<file> .queue/done/<file>")
    assert merge < rerun < revert < done


def test_a_requeued_branch_is_resumed_not_recreated():
    assert "git branch --list task/" in QUEUE_RUN


def test_dependencies_are_met_by_done_not_by_a_branch_check():
    assert "merge-base --is-ancestor" not in QUEUE_RUN
    assert ".queue/done/" in QUEUE_RUN


def test_the_worker_no_longer_stops_after_one_task():
    assert "do not pick up the next task" not in QUEUE_RUN
    assert "go back to **Claim**" in QUEUE_RUN


def test_no_engine_only_text_survived_the_port():
    assert "`main`" not in QUEUE_RUN
    assert ".venv" not in QUEUE_RUN
    assert "FUNCTION_INDEX" not in QUEUE_RUN
    assert "test_main_integration" not in QUEUE_RUN
    assert "--force" not in QUEUE_RUN.replace("never\n   `--force`", "")


def test_readme_describes_the_auto_merge_not_a_hand_merge():
    assert "merge.lock" in README
    assert "and you merge" not in README
    assert "merged into master" in README
    assert "git merge task/TASK-n &&" not in README
