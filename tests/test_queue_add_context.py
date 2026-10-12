"""/queue-add carries the three keep-context-small rules. These pin the command's instructions,
not what a model does with them. Run: python -m pytest tests/test_queue_add_context.py -q
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUEUE_ADD = (ROOT / ".claude" / "commands" / "queue-add.md").read_text(encoding="utf-8")
FLAT = re.sub(r"\s+", " ", QUEUE_ADD)
HEADING = "## Keep context small"


def keep_section():
    start = QUEUE_ADD.index(HEADING)
    nxt = re.search(r"^## ", QUEUE_ADD[start + len(HEADING):], re.M)
    return QUEUE_ADD[start:start + len(HEADING) + nxt.start()]


def test_the_section_exists_before_the_reading_steps():
    assert HEADING in QUEUE_ADD
    assert QUEUE_ADD.index(HEADING) < QUEUE_ADD.index("## Then read what already exists")


def test_the_three_rules_are_present():
    keep = re.sub(r"\s+", " ", keep_section())
    assert "Grep first, read line ranges" in keep
    assert "A passing command shows only its last line" in keep
    assert "Never re-read an unchanged file" in keep


def test_the_quiet_wrapper_prints_one_line_on_pass_sixty_on_fail_and_the_exit_code():
    keep = keep_section()
    assert 'out=$(mktemp); <command> >"$out" 2>&1; rc=$?' in keep
    assert 'tail -n 1 "$out"' in keep
    assert 'tail -n 60 "$out"' in keep
    assert 'echo "exit=$rc"' in keep


def test_a_verify_is_run_as_bash_c_of_a_variable_never_single_quoted():
    keep = re.sub(r"\s+", " ", keep_section())
    assert 'bash -c "$V"' in keep
    assert "never wrap it in `bash -c '...'`" in keep


def test_every_large_file_named_exists_and_is_over_500_lines():
    for name in ("main.py", "static/css/rapture.css", "templates/console.html"):
        assert f"`{name}`" in keep_section(), name
        lines = (ROOT / name).read_text(encoding="utf-8").count("\n")
        assert lines > 500, (name, lines)


def test_the_proof_run_prints_in_full_and_the_pass_regex_run_prints_one_line():
    assert "prints in full" in FLAT
    assert "should show one line" in FLAT


def test_code_is_read_by_grep_and_line_range():
    assert "grep for the lines, then read that range" in FLAT


def test_the_site_duplicate_check_is_kept_and_no_engine_only_text_came_with_the_port():
    assert "--include=*.py --include=*.html --exclude-dir=.worktrees" in QUEUE_ADD
    assert "FUNCTION_INDEX" not in QUEUE_ADD
    assert ".venv" not in QUEUE_ADD
    assert "test_main_integration" not in QUEUE_ADD
