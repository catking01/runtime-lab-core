from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .spine_adapter import build_descriptor_spine_dry_run


NOOP_BRIDGE_INVALID_DRY_RUN_PLAN = "NOOP_BRIDGE_INVALID_DRY_RUN_PLAN"
NOOP_BRIDGE_DRY_RUN_REJECTED = "NOOP_BRIDGE_DRY_RUN_REJECTED"
NOOP_BRIDGE_EXECUTION_REQUESTED = "NOOP_BRIDGE_EXECUTION_REQUESTED"
NOOP_BRIDGE_WORKSPACE_MUTATION_FORBIDDEN = "NOOP_BRIDGE_WORKSPACE_MUTATION_FORBIDDEN"
NOOP_BRIDGE_TOOL_INVOCATION_FORBIDDEN = "NOOP_BRIDGE_TOOL_INVOCATION_FORBIDDEN"
NOOP_BRIDGE_LLM_INVOCATION_FORBIDDEN = "NOOP_BRIDGE_LLM_INVOCATION_FORBIDDEN"
NOOP_BRIDGE_GOVERNANCE_DECISION_MISSING = "NOOP_BRIDGE_GOVERNANCE_DECISION_MISSING"
NOOP_BRIDGE_TRANSITION_AUDIT_BINDING_MISSING = "NOOP_BRIDGE_TRANSITION_AUDIT_BINDING_MISSING"
NOOP_BRIDGE_ARTIFACT_VALIDATION_BINDING_MISSING = "NOOP_BRIDGE_ARTIFACT_VALIDATION_BINDING_MISSING"
NOOP_BRIDGE_REPLAY_PROOF_FORBIDDEN = "NOOP_BRIDGE_REPLAY_PROOF_FORBIDDEN"

_BRIDGE_CODE_MAP = {
    "DRY_RUN_EXECUTION_REQUESTED": NOOP_BRIDGE_EXECUTION_REQUESTED,
    "DRY_RUN_WORKSPACE_MUTATION_FORBIDDEN": NOOP_BRIDGE_WORKSPACE_MUTATION_FORBIDDEN,
    "DRY_RUN_TOOL_INVOCATION_FORBIDDEN": NOOP_BRIDGE_TOOL_INVOCATION_FORBIDDEN,
    "DRY_RUN_LLM_INVOCATION_FORBIDDEN": NOOP_BRIDGE_LLM_INVOCATION_FORBIDDEN,
    "DRY_RUN_GOVERNANCE_DECISION_MISSING": NOOP_BRIDGE_GOVERNANCE_DECISION_MISSING,
    "DRY_RUN_TRANSITION_AUDIT_BINDING_MISSING": NOOP_BRIDGE_TRANSITION_AUDIT_BINDING_MISSING,
    "DRY_RUN_ARTIFACT_VALIDATION_BINDING_MISSING": NOOP_BRIDGE_ARTIFACT_VALIDATION_BINDING_MISSING,
    "DRY_RUN_REPLAY_PROOF_FORBIDDEN": NOOP_BRIDGE_REPLAY_PROOF_FORBIDDEN,
}


def _reject(*codes: str, details: Mapping[str, Any] | None = None) -> dict[str, Any]:
    result = {
        "accepted": False,
        "rejection_codes": list(codes),
        "noop_bridge_receipt": None,
        "workspace_probe": {
            "mutated": False,
            "touched_paths": [],
        },
    }
    if details is not None:
        result["details"] = dict(details)
    return result


def _is_mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


def _valid_dry_run_plan(dry_run_plan: Any) -> bool:
    if not _is_mapping(dry_run_plan):
        return False
    if dry_run_plan.get("plan_kind") != "descriptor_to_spine_dry_run":
        return False
    if dry_run_plan.get("execution_mode") != "dry_run_only":
        return False
    required_fields = {
        "task",
        "state",
        "transition",
        "audit",
        "artifacts",
        "validation",
        "governance",
        "replay",
    }
    return required_fields <= set(dry_run_plan)


def _bridge_rejection_codes(dry_run_result: Mapping[str, Any]) -> list[str]:
    codes: list[str] = []
    for code in dry_run_result.get("rejection_codes", []):
        mapped = _BRIDGE_CODE_MAP.get(code)
        if mapped:
            codes.append(mapped)
        else:
            codes.append(code)
    if codes and codes[0] not in {
        "SPINE_CONTRACT_REJECTED",
        NOOP_BRIDGE_EXECUTION_REQUESTED,
        NOOP_BRIDGE_WORKSPACE_MUTATION_FORBIDDEN,
        NOOP_BRIDGE_TOOL_INVOCATION_FORBIDDEN,
        NOOP_BRIDGE_LLM_INVOCATION_FORBIDDEN,
        NOOP_BRIDGE_GOVERNANCE_DECISION_MISSING,
        NOOP_BRIDGE_TRANSITION_AUDIT_BINDING_MISSING,
        NOOP_BRIDGE_ARTIFACT_VALIDATION_BINDING_MISSING,
        NOOP_BRIDGE_REPLAY_PROOF_FORBIDDEN,
    }:
        codes.insert(0, NOOP_BRIDGE_DRY_RUN_REJECTED)
    return codes


def _build_noop_bridge_receipt_from_plan(
    descriptor: Mapping[str, Any],
    dry_run_plan: Mapping[str, Any],
) -> dict[str, Any]:
    task = dict(dry_run_plan["task"])
    return {
        "bridge_kind": "descriptor_to_spine_noop_execution_bridge",
        "bridge_receipt_id": f"noop-bridge-{task['descriptor_id']}",
        "task": task,
        "state": dict(dry_run_plan["state"]),
        "transition": {
            **dict(dry_run_plan["transition"]),
            "execution_mode": "noop_only",
            "receipt_status": "recorded_without_side_effects",
        },
        "audit": {
            **dict(dry_run_plan["audit"]),
            "event_kind": "noop_execution_bridge_recorded",
        },
        "governance": dict(dry_run_plan["governance"]),
        "artifacts": [dict(item) for item in dry_run_plan["artifacts"]],
        "validation": {
            **dict(dry_run_plan["validation"]),
            "receipt_status": "validated_without_execution",
        },
        "replay": {
            **dict(dry_run_plan["replay"]),
            "receipt_binding_status": "intent_receipt_only",
            "proof_status": "not_proven",
        },
        "workspace_effects": {
            "mutated": False,
            "touched_paths": [],
        },
        "tool_invocation": {
            "invoked": False,
            "tools": [],
        },
        "llm_invocation": {
            "invoked": False,
            "models": [],
        },
        "descriptor_hash": descriptor["descriptor_hash"],
        "descriptor_id": descriptor["descriptor_id"],
        "execution_result": "noop_receipt_only",
    }


def build_noop_bridge_receipt(dry_run_result: Any) -> dict[str, Any]:
    if not _is_mapping(dry_run_result):
        return _reject(NOOP_BRIDGE_INVALID_DRY_RUN_PLAN)

    if dry_run_result.get("accepted") is not True:
        return _reject(
            *_bridge_rejection_codes(dry_run_result),
            details={"dry_run_result": dict(dry_run_result)},
        )

    dry_run_plan = dry_run_result.get("dry_run_plan")
    descriptor = dry_run_result.get("descriptor")
    if not (_valid_dry_run_plan(dry_run_plan) and _is_mapping(descriptor)):
        return _reject(NOOP_BRIDGE_INVALID_DRY_RUN_PLAN)

    noop_bridge_receipt = _build_noop_bridge_receipt_from_plan(descriptor, dry_run_plan)
    return {
        "accepted": True,
        "rejection_codes": [],
        "descriptor": dict(descriptor),
        "spine_contract": dict(dry_run_result["spine_contract"]),
        "dry_run_plan": dict(dry_run_plan),
        "noop_bridge_receipt": noop_bridge_receipt,
        "workspace_probe": {
            "mutated": False,
            "touched_paths": [],
        },
    }


def build_descriptor_spine_noop_bridge(payload: Any) -> dict[str, Any]:
    return build_noop_bridge_receipt(build_descriptor_spine_dry_run(payload))
