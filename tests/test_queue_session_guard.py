"""/queue-run and /queue-add check which session they run in before doing queue work. These pin
the commands' instructions, not what a model does with them: ListAgents and SendMessage cannot
run in a test. Run: python -m pytest tests/test_queue_session_guard.py -q
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUEUE_RUN = (ROOT / ".claude" / "commands" / "queue-run.md").read_text(encoding="utf-8")
QUEUE_ADD = (ROOT / ".claude" / "commands" / "queue-add.md").read_text(encoding="utf-8")
# Hard-wrapped prose: phrase assertions run on this, so re-wrapping a paragraph breaks nothing.
RUN_FLAT = re.sub(r"\s+", " ", QUEUE_RUN)
ADD_FLAT = re.sub(r"\s+", " ", QUEUE_ADD)
GUARD = "## Which session is this"


def test_both_commands_check_the_session_before_any_queue_work():
    assert GUARD in QUEUE_RUN and GUARD in QUEUE_ADD
    assert QUEUE_RUN.index(GUARD) < QUEUE_RUN.index("## Claim")
    assert QUEUE_ADD.index(GUARD) < QUEUE_ADD.index("## Then read what already exists")
    assert QUEUE_ADD.index(GUARD) < QUEUE_ADD.index("## First, check the request belongs in this repo")


def test_the_right_session_names_are_site_worker_and_site_planner():
    assert "Named exactly `site-worker`" in QUEUE_RUN
    assert "/rename site-worker" in QUEUE_RUN
    assert 'to: "site-worker"' in QUEUE_RUN
    assert "Named exactly `site-planner`" in QUEUE_ADD
    assert "/rename site-planner" in QUEUE_ADD
    assert 'to: "site-planner"' in QUEUE_ADD


def test_the_wrong_session_relay_headers():
    assert "Forwarded verbatim from Kevin's /queue-run in <this session's name>. Run it here as typed." in QUEUE_RUN
    assert ("Forwarded verbatim from Kevin's /queue-add in <this session's name>. "
            "Queue it under your /queue-add rules.") in QUEUE_ADD
    assert "Drop its leading `/queue-run` token" in RUN_FLAT
    assert "Never forward it again" in RUN_FLAT


def test_a_request_forwarded_in_from_the_engine_is_kevins_and_never_goes_back():
    assert "`job-outreach-engine.`" in QUEUE_ADD
    assert "Never forward any of it back" in ADD_FLAT
    assert "session `planner`" in ADD_FLAT
    assert "ignore it" in ADD_FLAT
    assert "never for a request that was itself forwarded in from the engine" in ADD_FLAT


def test_the_site_to_engine_header_still_ends_in_montelattice_site():
    lines = [ln for ln in QUEUE_ADD.splitlines() if ln.strip().startswith("Forwarded verbatim from Kevin's /queue-add in montelattice-site")]
    assert len(lines) == 1
    assert lines[0].endswith("in montelattice-site.")
    assert "to: \"planner\"" in QUEUE_ADD


def test_the_not_forwarded_block_carries_the_header_line():
    assert "header line included" in ADD_FLAT


def test_queue_status_keeps_no_guard_and_says_so():
    assert "`/queue-status` only reads the queue and has no such guard" in RUN_FLAT
    assert "`/queue-status` only reads the queue and has no such guard" in ADD_FLAT
    status = (ROOT / ".claude" / "commands" / "queue-status.md").read_text(encoding="utf-8")
    assert GUARD not in status and "ListAgents" not in status


def test_the_engines_session_names_did_not_survive_the_port():
    for text in (QUEUE_RUN, QUEUE_ADD):
        assert not re.search(r"/rename (worker|planner)([^-a-z]|$)", text, re.M)
        assert 'to: "worker"' not in text
