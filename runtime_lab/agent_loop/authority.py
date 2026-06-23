from __future__ import annotations

from dataclasses import asdict
from typing import Any

from runtime_lab.agent_loop.models import AgentLoopAuthority, AgentLoopPolicy, AgentLoopRequest
from runtime_lab.agent_loop.receipts import canonical_hash


def _decision(*, accepted: bool, rejection_codes: list[str], authority: AgentLoopAuthority | None, request: AgentLoopRequest) -> dict[str, Any]:
    result = {
        "accepted": accepted,
        "rejection_codes": list(dict.fromkeys(rejection_codes)),
        "task_id": request.task_id,
        "run_id": request.run_id,
        "mode": request.mode.value,
        "supervision_required": authority.supervision_required if authority else True,
        "actor_id": authority.actor_id if authority else None,
        "autonomous_operation_allowed": authority.allow_autonomous_mode if authority else False,
        "model_driven_executor_dispatch_allowed": authority.allow_model_driven_executor_dispatch if authority else False,
    }
    result["authority_decision_hash"] = canonical_hash(result)
    return result


def evaluate_authority(
    request: AgentLoopRequest,
    *,
    authority: AgentLoopAuthority | None,
    policy: AgentLoopPolicy | None = None,
) -> dict[str, Any]:
    policy = policy or AgentLoopPolicy()
    if authority is None:
        return _decision(accepted=False, rejection_codes=["REJECTED_MISSING_AUTHORITY"], authority=None, request=request)
    if authority.task_id != request.task_id:
        return _decision(accepted=False, rejection_codes=["REJECTED_MISSING_AUTHORITY"], authority=authority, request=request)
    if authority.allow_autonomous_mode:
        return _decision(accepted=False, rejection_codes=["REJECTED_AUTONOMOUS_MODE"], authority=authority, request=request)
    if request.mode.value not in {mode.value for mode in authority.allowed_modes}:
        return _decision(accepted=False, rejection_codes=["REJECTED_SCOPE_ESCALATION"], authority=authority, request=request)
    if request.mode.value == "SUPERVISED_APPLY" and not authority.allow_patch_apply:
        return _decision(accepted=False, rejection_codes=["REJECTED_UNAPPROVED_MUTATION"], authority=authority, request=request)
    if request.test_command_id and not authority.allow_test_runner:
        return _decision(accepted=False, rejection_codes=["REJECTED_TEST_RUNNER_BYPASS"], authority=authority, request=request)
    if request.model_driven_executor_dispatch_requested or authority.allow_model_driven_executor_dispatch:
        return _decision(accepted=False, rejection_codes=["REJECTED_MODEL_TOOL_CALL"], authority=authority, request=request)
    if request.allow_live_llm_provider and not policy.allow_live_llm_provider:
        return _decision(accepted=False, rejection_codes=["REJECTED_LIVE_LLM_PROVIDER_BY_DEFAULT"], authority=authority, request=request)

    result = _decision(accepted=True, rejection_codes=[], authority=authority, request=request)
    result["authority"] = asdict(authority)
    return result
