from __future__ import annotations

import re
from typing import Any

from runtime_lab.agent_loop.authority import evaluate_authority
from runtime_lab.agent_loop.errors import AgentLoopPolicyError
from runtime_lab.agent_loop.models import AgentLoopAuthority, AgentLoopPolicy, AgentLoopRequest
from runtime_lab.agent_loop.state_machine import TRANSITIONS
from runtime_lab.test_runner.allowlist import DEFAULT_ALLOWLIST


SECRET_LIKE_RE = re.compile(r"(sk-[A-Za-z0-9_-]{20,}|gho_[A-Za-z0-9_]{20,}|Authorization:\s*Bearer\s+\S+)", re.IGNORECASE)
UNBOUNDED_RE = re.compile(r"\b(unbounded|forever|indefinitely|keep going|never stop)\b", re.IGNORECASE)
SCOPE_ESCALATION_RE = re.compile(
    r"\b(production[- ]ready|codex|claude code|remote sealed|team runtime|organization runtime|autonomous|autonomously)\b",
    re.IGNORECASE,
)
MODEL_TOOL_CALL_RE = re.compile(
    r"\b(tool_calls?|executor dispatch|shell|network|fetch|write arbitrary|os\.system|subprocess|curl|bash)\b|https?://",
    re.IGNORECASE,
)


def _result(codes: list[str]) -> dict[str, Any]:
    codes = list(dict.fromkeys(codes))
    return {"accepted": not codes, "rejection_codes": codes}


def _planner_codes(planner_output: dict[str, Any] | None) -> list[str]:
    if not planner_output:
        return []
    if planner_output.get("tool_calls"):
        return ["REJECTED_MODEL_TOOL_CALL"]
    text = " ".join(str(value) for value in planner_output.values())
    if MODEL_TOOL_CALL_RE.search(text):
        return ["REJECTED_MODEL_TOOL_CALL"]
    return []


def validate_agent_loop_request(
    request: AgentLoopRequest,
    *,
    authority: AgentLoopAuthority | None,
    policy: AgentLoopPolicy | None = None,
) -> dict[str, Any]:
    policy = policy or AgentLoopPolicy()
    codes: list[str] = []

    authority_result = evaluate_authority(request=request, authority=authority, policy=policy)
    codes.extend(authority_result["rejection_codes"])

    if not policy.require_receipts or request.force_missing_receipt:
        codes.append("REJECTED_MISSING_RECEIPT")
    if not policy.require_ledger_events or request.force_missing_ledger:
        codes.append("REJECTED_MISSING_LEDGER")
    if not policy.require_replay_bundle or request.force_missing_replay_manifest:
        codes.append("REJECTED_MISSING_REPLAY_MANIFEST")
    if not policy.require_final_report:
        codes.append("REJECTED_MISSING_FINAL_REPORT")
    if policy.max_iterations <= 0 or request.requested_iterations > policy.max_iterations:
        codes.append("REJECTED_ITERATION_LIMIT")
    if len(request.context_requests) > policy.max_context_reads:
        codes.append("REJECTED_CONTEXT_READ_LIMIT")
    if request.patch_proposal_count > policy.max_patch_proposals:
        codes.append("REJECTED_PATCH_PROPOSAL_LIMIT")
    if request.patch_apply_transaction_count > policy.max_patch_apply_transactions:
        codes.append("REJECTED_UNAPPROVED_MUTATION")
    if request.test_run_count > policy.max_test_runs:
        codes.append("REJECTED_TEST_RUNNER_BYPASS")
    if request.allow_live_llm_provider and not policy.allow_live_llm_provider:
        codes.append("REJECTED_LIVE_LLM_PROVIDER_BY_DEFAULT")
    if request.raw_command:
        codes.append("REJECTED_ARBITRARY_COMMAND")
    if request.workspace_mutation_requested:
        codes.append("REJECTED_UNAPPROVED_MUTATION")
    if request.model_driven_executor_dispatch_requested:
        codes.append("REJECTED_MODEL_TOOL_CALL")
    if request.force_ledger_hash_mismatch:
        codes.append("REJECTED_LEDGER_HASH_MISMATCH")
    if request.force_replay_hash_mismatch:
        codes.append("REJECTED_REPLAY_HASH_MISMATCH")
    if request.force_rollback_required:
        codes.append("ROLLBACK_REQUIRED")

    codes.extend(_planner_codes(request.planner_output))

    if SECRET_LIKE_RE.search(request.task_text):
        codes.append("REJECTED_SECRET_RISK")
    if UNBOUNDED_RE.search(request.task_text):
        codes.append("REJECTED_UNBOUNDED_TASK")
    if SCOPE_ESCALATION_RE.search(request.task_text):
        codes.append("REJECTED_SCOPE_ESCALATION")

    if request.requested_initial_state is not None and request.requested_initial_state not in TRANSITIONS:
        codes.append("REJECTED_UNKNOWN_STATE")
    if request.requested_transition is not None:
        initial_state = request.requested_initial_state or "TASK_RECEIVED"
        try:
            if initial_state not in TRANSITIONS:
                raise AgentLoopPolicyError("REJECTED_UNKNOWN_STATE")
            if request.requested_transition not in TRANSITIONS[initial_state]:
                raise AgentLoopPolicyError("REJECTED_UNKNOWN_TRANSITION")
        except AgentLoopPolicyError as exc:
            codes.append(exc.code)

    if request.mode.value == "SUPERVISED_APPLY":
        if not policy.allow_patch_apply:
            codes.append("REJECTED_UNAPPROVED_MUTATION")
        if policy.require_human_approval_for_apply and (
            not request.approval_packet or "approval_id" not in request.approval_packet
        ):
            codes.append("REJECTED_MISSING_HUMAN_APPROVAL")
    if request.test_command_id:
        if not policy.allow_test_runner:
            codes.append("REJECTED_TEST_RUNNER_BYPASS")
        elif request.test_command_id not in DEFAULT_ALLOWLIST:
            codes.append("REJECTED_DISALLOWED_TEST_COMMAND")
    if request.test_run_result is not None and not request.test_run_result.get("receipt"):
        codes.append("REJECTED_TEST_RUNNER_RECEIPT")

    result = _result(codes)
    result["authority_decision_hash"] = authority_result["authority_decision_hash"]
    return result
