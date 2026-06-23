from __future__ import annotations

import pytest

from runtime_lab.agent_loop.errors import AgentLoopPolicyError
from runtime_lab.agent_loop.state_machine import build_transition_log, next_state, verify_transition_log


def test_known_transition_advances_state():
    assert next_state("TASK_RECEIVED", "check_authority") == "AUTHORITY_CHECKED"


def test_unknown_state_fails_closed():
    with pytest.raises(AgentLoopPolicyError) as exc:
        next_state("SURPRISE", "check_authority")

    assert exc.value.code == "REJECTED_UNKNOWN_STATE"


def test_unknown_transition_fails_closed():
    with pytest.raises(AgentLoopPolicyError) as exc:
        next_state("TASK_RECEIVED", "launch_shell")

    assert exc.value.code == "REJECTED_UNKNOWN_TRANSITION"


def test_transition_log_hash_chain_is_stable():
    log = build_transition_log(
        [
            ("TASK_RECEIVED", "check_authority", "AUTHORITY_CHECKED"),
            ("AUTHORITY_CHECKED", "create_plan", "PLAN_CREATED"),
            ("PLAN_CREATED", "read_context", "CONTEXT_READ"),
        ]
    )

    assert verify_transition_log(log) is True
    assert log[0]["previous_transition_hash"] == "GENESIS"
    assert log[-1]["transition_hash"].startswith("sha256:")


def test_transition_log_detects_tamper():
    log = build_transition_log([("TASK_RECEIVED", "check_authority", "AUTHORITY_CHECKED")])
    log[0]["to_state"] = "DONE"

    assert verify_transition_log(log) is False
