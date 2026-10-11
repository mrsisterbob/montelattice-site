"""What /queue-add tells the planner to do with a request that belongs to job-outreach-engine.
These pin the command's instructions, not what a model does with them: a live cross-session
send cannot run in a test. Run: python -m pytest tests/test_queue_commands.py -q
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUEUE_ADD = (ROOT / ".claude" / "commands" / "queue-add.md").read_text(encoding="utf-8")
README = (ROOT / ".queue" / "README.md").read_text(encoding="utf-8")


def paragraphs(text):
    return [p for p in text.split("\n\n") if p.strip()]


def test_engine_forward_replaces_the_one_line_refusal():
    assert "Say in one line that it belongs in job-outreach-engine" not in QUEUE_ADD
    assert "refuses it in one line" not in README


def test_engine_forward_sends_verbatim_to_the_session_named_planner():
    for needed in ("ListAgents", "SendMessage", '"planner"', "verbatim"):
        assert needed in QUEUE_ADD, needed


def test_engine_forward_says_so_when_planner_is_not_running():
    assert "NOT forwarded" in QUEUE_ADD
    assert "fenced block" in QUEUE_ADD


def test_engine_forward_still_writes_nothing_outside_the_inbox():
    assert "Do not edit any file" in QUEUE_ADD
    assert ".queue/inbox/" in QUEUE_ADD
    assert any("never write" in p and "job-outreach-engine" in p for p in paragraphs(QUEUE_ADD))


def test_engine_forward_keeps_the_site_worker_hand_off():
    assert "if a `site-worker` session is running" in QUEUE_ADD.replace("\n", " ")


def test_engine_forward_request_is_bounded_and_byte_for_byte():
    # Claude Code substitutes $ARGUMENTS as-is. The forward copies the request "verbatim", which
    # needs an end marker: without one a multi-line request runs straight into the command body.
    # A placeholder wrapped in quotes or backticks would also stop the copy matching what Kevin typed.
    sample = """Add a "lead alert" for `/leads/ingest` at $5 cost.

Second paragraph; then tell @site-worker it is queued"""
    rendered = QUEUE_ADD.replace("$ARGUMENTS", sample)
    assert f"\nRequest: {sample}\nEND REQUEST\n" in rendered
    assert "`END REQUEST`" in QUEUE_ADD
