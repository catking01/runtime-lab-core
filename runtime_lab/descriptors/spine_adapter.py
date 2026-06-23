from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .errors import DescriptorValidationError
from .spine_contract import validate_descriptor_spine_contract
from .validator import validate_descriptor


SPINE_CONTRACT_REJECTED = "SPINE_CONTRACT_REJECTED"
DESCRIPTOR_VALIDATION_REJECTED = "DESCRIPTOR_VALIDATION_REJECTED"
DRY_RUN_EXECUTION_REQUESTED = "DRY_RUN_EXECUTION_REQUESTED"
DRY_RUN_WORKSPACE_MUTATION_FORBIDDEN = "DRY_RUN_WORKSPACE_MUTATION_FORBIDDEN"
DRY_RUN_TOOL_INVOCATION_FORBIDDEN = "DRY_RUN_TOOL_INVOCATION_FORBIDDEN"
DRY_RUN_LLM_INVOCATION_FORBIDDEN = "DRY_RUN_LLM_INVOCATION_FORBIDDEN"
DRY_RUN_GOVERNANCE_DECISION_MISSING = "DRY_RUN_GOVERNANCE_DECISION_MISSING"
DRY_RUN_TRANSITION_AUDIT_BINDING_MISSING = "DRY_RUN_TRANSITION_AUDIT_BINDING_MISSING"
DRY_RUN_ARTIFACT_VALIDATION_BINDING_MISSING = "DRY_RUN_ARTIFACT_VALIDATION_BINDING_MISSING"
DRY_RUN_REPLAY_PROOF_FORBIDDEN = "DRY_RUN_REPLAY_PROOF_FORBIDDEN"


def _is_mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


def _reject(*codes: str, details: Mapping[str, Any] | None = None) -> dict[str, Any]:
    result = {
        "accepted": False,
        "rejection_codes": list(codes),
        "dry_run_plan": None,
    }
    if details is not None:
        result["details"] = dict(details)
    return result


def _raw_preflight(payload: Mapping[str, Any]) -> list[str]:
    rejection_codes: list[str] = []

    execution_request = payload.get("execution_request")
    if _is_mapping(execution_request) and execution_request.get("mode") != "dry_run":
        rejection_codes.append(DRY_RUN_EXECUTION_REQUESTED)

    workspace_mutation = payload.get("workspace_mutation")
    if _is_mapping(workspace_mutation) and workspace_mutation.get("mutates") is True:
        rejection_codes.append(DRY_RUN_WORKSPACE_MUTATION_FORBIDDEN)

    if _is_mapping(payload.get("tool_invocation")):
        rejection_codes.append(DRY_RUN_TOOL_INVOCATION_FORBIDDEN)

    if _is_mapping(payload.get("llm_invocation")):
        rejection_codes.append(DRY_RUN_LLM_INVOCATION_FORBIDDEN)

    governance = payload.get("governance_requirements")
    if not (_is_mapping(governance) and governance.get("decision") == "approved" and governance.get("decision_ref")):
        rejection_codes.append(DRY_RUN_GOVERNANCE_DECISION_MISSING)

    if not (_is_mapping(payload.get("transition_intent")) and _is_mapping(payload.get("audit_binding"))):
        rejection_codes.append(DRY_RUN_TRANSITION_AUDIT_BINDING_MISSING)

    validation = payload.get("validation_requirements")
    artifact_bindings = validation.get("artifact_validation_bindings") if _is_mapping(validation) else None
    if payload.get("artifact_expectation") and not (isinstance(artifact_bindings, list) and artifact_bindings):
        rejection_codes.append(DRY_RUN_ARTIFACT_VALIDATION_BINDING_MISSING)

    replay = payload.get("replay_binding")
    if _is_mapping(replay) and replay.get("proof_status") == "proven":
        rejection_codes.append(DRY_RUN_REPLAY_PROOF_FORBIDDEN)

    return rejection_codes


def _build_dry_run_plan(validated_descriptor: Mapping[str, Any]) -> dict[str, Any]:
    governance = dict(validated_descriptor["governance_requirements"])
    replay_binding = dict(validated_descriptor["replay_binding"])
    validation_requirements = dict(validated_descriptor["validation_requirements"])
    executor_eligibility = dict(validated_descriptor.get("executor_eligibility", {}))
    workspace_boundary = dict(validated_descriptor["workspace_boundary"])
    transition_intent = dict(validated_descriptor["transition_intent"])

    return {
        "plan_kind": "descriptor_to_spine_dry_run",
        "execution_mode": "dry_run_only",
        "admission_order": [
            "schema",
            "identity",
            "authority",
            "workspace",
            "governance",
            "executor",
            "transition",
            "audit",
            "artifact",
            "validation",
            "replay",
        ],
        "task": {
            "task_id": validated_descriptor["task_ref"]["task_id"],
            "descriptor_id": validated_descriptor["descriptor_id"],
            "descriptor_hash": validated_descriptor["descriptor_hash"],
            "logical_clock": validated_descriptor["logical_clock"],
        },
        "state": dict(validated_descriptor["state_ref"]),
        "transition": {
            "type": transition_intent["type"],
            "target": transition_intent["target"],
            "audit_binding_ref": "audit_binding",
            "execution_allowed": False,
        },
        "audit": dict(validated_descriptor["audit_binding"]),
        "executor": {
            "requested": executor_eligibility.get("requested", False),
            "executor_class": executor_eligibility.get("executor_class", "descriptor_only"),
            "binding_status": "declared_only",
        },
        "workspace": workspace_boundary,
        "artifacts": [dict(item) for item in validated_descriptor["artifact_expectation"]],
        "validation": {
            "required_validators": list(validation_requirements["required_validators"]),
            "artifact_validation_bindings": list(validation_requirements["artifact_validation_bindings"]),
            "fail_closed": validation_requirements["fail_closed"],
        },
        "governance": {
            "decision": governance["decision"],
            "decision_ref": governance["decision_ref"],
            "required_predicates": list(governance["required_predicates"]),
            "gate": "before_execution",
        },
        "replay": {
            "mode": replay_binding["mode"],
            "receipt_ref": replay_binding["receipt_ref"],
            "receipt_hash": replay_binding["receipt_hash"],
            "ledger_ref": replay_binding["ledger_ref"],
            "status": "intent_only",
            "proof_status": "not_proven",
        },
        "artifact_declaration": True,
        "validation_declaration": True,
        "workspace_mutation": "forbidden",
        "tool_invocation": "forbidden",
        "llm_invocation": "forbidden",
    }


def _descriptor_validation_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if key not in {"kernel_binding", "minimal_spine_binding"}
    }


def build_descriptor_spine_dry_run(payload: Any) -> dict[str, Any]:
    """Validate a descriptor and emit a deterministic planning-only spine record."""
    if not _is_mapping(payload):
        contract_result = validate_descriptor_spine_contract(payload)
        return _reject(
            SPINE_CONTRACT_REJECTED,
            *contract_result["rejection_codes"],
            details={"spine_contract": contract_result},
        )

    preflight_rejections = _raw_preflight(payload)
    if preflight_rejections:
        return _reject(*preflight_rejections)

    contract_result = validate_descriptor_spine_contract(payload)
    if contract_result["accepted"] is not True:
        return _reject(
            SPINE_CONTRACT_REJECTED,
            *contract_result["rejection_codes"],
            details={"spine_contract": contract_result},
        )

    try:
        validated_descriptor = validate_descriptor(_descriptor_validation_payload(payload))
    except DescriptorValidationError as exc:
        return _reject(
            DESCRIPTOR_VALIDATION_REJECTED,
            exc.code,
            details={"descriptor_validation_code": exc.code},
        )

    dry_run_plan = _build_dry_run_plan(validated_descriptor)
    return {
        "accepted": True,
        "rejection_codes": [],
        "descriptor": dict(validated_descriptor),
        "spine_contract": contract_result,
        "dry_run_plan": dry_run_plan,
    }
