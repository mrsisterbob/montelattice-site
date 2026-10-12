"""/queue-run builds each task in a fresh general-purpose subagent while the worker stays in the
main folder. These pin the command's instructions, not what a model does with them.
Run: python -m pytest tests/test_queue_run_subagent.py -q
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUEUE_RUN = (ROOT / ".claude" / "commands" / "queue-run.md").read_text(encoding="utf-8")
# Hard-wrapped prose: assertions on phrases run on this, so re-wrapping a paragraph breaks nothing.
FLAT = re.sub(r"\s+", " ", QUEUE_RUN)


def section(heading):
    start = QUEUE_RUN.index(heading)
    nxt = re.search(r"^## ", QUEUE_RUN[start + len(heading):], re.M)
    return QUEUE_RUN[start:start + len(heading) + nxt.start()] if nxt else QUEUE_RUN[start:]


def test_the_build_agent_is_general_purpose_never_a_fork_or_a_worktree_isolation():
    assert 'subagent_type: "general-purpose"' in QUEUE_RUN
    assert 'Never `"fork"`' in QUEUE_RUN
    assert 'never `isolation: "worktree"`' in FLAT
    assert "Leave `model` and `effort` unset" in QUEUE_RUN


def test_the_build_agent_prompt_block_carries_the_wrapper_and_the_queue_name():
    assert "### Build agent prompt" in QUEUE_RUN
    prompt = QUEUE_RUN.split("### Build agent prompt", 1)[1]
    assert "for the montelattice-site queue" in prompt
    assert 'out=$(mktemp); <command> >"$out" 2>&1; rc=$?' in prompt
    assert "tail -n 1" in prompt and "tail -n 60" in prompt
    assert 'echo "exit=$rc"' in prompt
    assert "reply \"TASK-n: blocked - bank copy\"" in prompt


def test_the_agent_never_commits_merges_moves_queue_files_or_messages():
    prompt = QUEUE_RUN.split("### Build agent prompt", 1)[1]
    assert "Do NOT commit, run /code-review, move queue files, merge, or message anyone" \
        in re.sub(r"\s+", " ", prompt)
    assert "Your final reply is ONE line" in prompt


def test_the_worker_rechecks_the_agent_itself_and_a_red_recheck_counts():
    text = QUEUE_RUN.replace("\n", " ")
    assert "Do not trust the line - re-check it" in text
    assert "`SubagentStop`" in QUEUE_RUN
    assert "A red re-check is one more failed attempt" in text


def test_the_worker_never_cds_into_the_worktree_for_building():
    assert "&& cd .worktrees/" not in QUEUE_RUN
    assert "**Stay in the main folder.**" in QUEUE_RUN
    # The one place it enters a worktree is the review, and it comes straight back.
    assert "`cd` there for the review only" in QUEUE_RUN.replace("\n", " ")


def test_the_three_context_rules_exist_and_the_site_wording_is_used():
    keep = section("## Keep context small")
    assert "Grep first, read line ranges" in keep
    assert "A passing command shows only its last line" in keep
    assert "Never re-read an unchanged file" in keep
    assert "grep -rn -i <noun> --include=*.py --include=*.html --exclude-dir=.worktrees ." in QUEUE_RUN
    assert "python -m pytest tests -q -p no:cacheprovider" in QUEUE_RUN


def test_the_large_files_named_are_large_on_disk():
    keep = section("## Keep context small")
    for name in ("main.py", "static/css/rapture.css", "templates/console.html"):
        assert name in keep
        lines = (ROOT / name).read_text(encoding="utf-8").count("\n")
        assert lines > 500, (name, lines)


def test_no_engine_only_text_survived_the_port():
    assert ".venv" not in QUEUE_RUN
    assert "FUNCTION_INDEX" not in QUEUE_RUN
    assert "test_main_integration" not in QUEUE_RUN
    assert "`main`" not in QUEUE_RUN


def test_a_dirty_main_folder_rule_and_the_agent_running_rule_are_reconciled():
    assert "even if it is dirty" in FLAT


def test_an_empty_verify_is_a_failure_and_the_frontmatter_is_read_to_its_closing_fence():
    assert 'EMPTY VERIFY - treat as red' in QUEUE_RUN
    assert "sed -n '2,/^---/p'" in QUEUE_RUN
    assert "1,12p" not in QUEUE_RUN
