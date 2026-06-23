from __future__ import annotations

from typing import Any

from runtime_lab.agent_loop.errors import AgentLoopPolicyError
from runtime_lab.agent_loop.receipts import canonical_hash


TRANSITIONS: dict[str, dict[str, str]] = {
    "TASK_RECEIVED": {"check_authority": "AUTHORITY_CHECKED"},
    "AUTHORITY_CHECKED": {"create_plan": "PLAN_CREATED"},
    "PLAN_CREATED": {"read_context": "CONTEXT_READ"},
    "CONTEXT_READ": {"create_patch_proposal": "PATCH_PROPOSAL_CREATED"},
    "PATCH_PROPOSAL_CREATED": {
        "require_human_approval": "HUMAN_APPROVAL_REQUIRED",
        "write_final_artifact": "FINAL_ARTIFACT_WRITTEN",
    },
    "HUMAN_APPROVAL_REQUIRED": {"verify_human_approval": "HUMAN_APPROVAL_VERIFIED"},
    "HUMAN_APPROVAL_VERIFIED": {"start_patch_apply": "PATCH_APPLY_TRANSACTION_STARTED"},
    "PATCH_APPLY_TRANSACTION_STARTED": {"complete_patch_apply": "PATCH_APPLY_TRANSACTION_COMPLETED"},
    "PATCH_APPLY_TRANSACTION_COMPLETED": {"request_tests": "ALLOWLISTED_TESTS_REQUESTED"},
    "ALLOWLISTED_TESTS_REQUESTED": {"complete_tests": "ALLOWLISTED_TESTS_COMPLETED"},
    "ALLOWLISTED_TESTS_COMPLETED": {"write_final_artifact": "FINAL_ARTIFACT_WRITTEN"},
    "FINAL_ARTIFACT_WRITTEN": {"verify_receipts": "RECEIPTS_VERIFIED"},
    "RECEIPTS_VERIFIED": {"seal_ledger": "LEDGER_SEALED_LOCALLY"},
    "LEDGER_SEALED_LOCALLY": {"done": "DONE"},
    "DONE": {},
}


def next_state(current_state: str, transition: str) -> str:
    if current_state not in TRANSITIONS:
        raise AgentLoopPolicyError("REJECTED_UNKNOWN_STATE")
    if transition not in TRANSITIONS[current_state]:
        raise AgentLoopPolicyError("REJECTED_UNKNOWN_TRANSITION")
    return TRANSITIONS[current_state][transition]


def build_transition_log(
    transitions: list[tuple[str, str]] | list[tuple[str, str, str]],
    *,
    run_id: str = "run-unknown",
) -> list[dict[str, Any]]:
    current = "TASK_RECEIVED"
    previous_hash = "GENESIS"
    log: list[dict[str, Any]] = []
    for index, transition_item in enumerate(transitions, start=1):
        if len(transition_item) == 2:
            state, transition = transition_item
            expected_target = next_state(state, transition)
        else:
            state, transition, expected_target = transition_item
        if state != current:
            raise AgentLoopPolicyError("REJECTED_UNKNOWN_STATE")
        target = next_state(state, transition)
        if target != expected_target:
            raise AgentLoopPolicyError("REJECTED_UNKNOWN_TRANSITION")
        event = {
            "run_id": run_id,
            "sequence": index,
            "from_state": state,
            "transition": transition,
            "to_state": target,
            "previous_transition_hash": previous_hash,
        }
        event["transition_hash"] = canonical_hash(event)
        log.append(event)
        previous_hash = event["transition_hash"]
        current = target
    return log


def verify_transition_log(log: list[dict[str, Any]]) -> bool:
    previous_hash = "GENESIS"
    for event in log:
        expected = dict(event)
        transition_hash = expected.pop("transition_hash", None)
        if expected.get("previous_transition_hash") != previous_hash:
            return False
        try:
            target = next_state(str(expected.get("from_state")), str(expected.get("transition")))
        except AgentLoopPolicyError as exc:
            return False
        if expected.get("to_state") != target:
            return False
        if canonical_hash(expected) != transition_hash:
            return False
        previous_hash = str(transition_hash)
    return True
