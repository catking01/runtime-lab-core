from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from runtime_lab.kernel20.coverage import (
    MINIMAL_KERNEL_BINDING_12,
    minimal_kernel_binding_coverage,
    full_kernel20_coverage,
    describe_kernel20_coverage,
)


TASK_IDENTITY = "MISSING_TASK_IDENTITY"
AUTHORITY_BINDING = "MISSING_AUTHORITY_BINDING"
EXECUTOR_WORKSPACE = "EXECUTOR_WITHOUT_WORKSPACE_BOUNDARY"
ARTIFACT_VALIDATION = "ARTIFACT_WITHOUT_VALIDATION_BINDING"
REPLAY_RECEIPT_LEDGER_HASH = "REPLAY_WITHOUT_RECEIPT_LEDGER_HASH"
TOOL_CAPABILITY = "TOOL_WITHOUT_CAPABILITY"
HANDOFF_ACTOR_RECORD = "HANDOFF_WITHOUT_ACTOR_RECORD"
STATE_TRANSITION_AUDIT = "STATE_MUTATION_WITHOUT_TRANSITION_AUDIT"
EXECUTION_GOVERNANCE = "EXECUTION_BEFORE_GOVERNANCE"
KERNEL_20_BINDING = "KERNEL_20_BINDING_INCOMPLETE"
MINIMAL_SPINE_BINDING = "MINIMAL_SPINE_BINDING_INCOMPLETE"


MINIMAL_KERNEL_BINDING = MINIMAL_KERNEL_BINDING_12
DESCRIPTOR_SPINE_BINDING_12 = MINIMAL_KERNEL_BINDING_12
MINIMAL_SPINE_KERNEL_RELEVANT_FIELDS = (
    "task_ref",
    "identity_binding",
    "authority_binding",
    "state_ref",
    "transition_intent",
    "audit_binding",
    "executor_eligibility",
    "workspace_boundary",
    "artifact_expectation",
    "validation_requirements",
    "governance_requirements",
    "replay_binding",
)

MINIMAL_SPINE_FIELDS = frozenset(MINIMAL_SPINE_KERNEL_RELEVANT_FIELDS)


def _is_mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


def _has_non_empty_mapping(payload: Mapping[str, Any], field: str) -> bool:
    return _is_mapping(payload.get(field)) and bool(payload[field])


def _has_non_empty_list(payload: Mapping[str, Any], field: str) -> bool:
    return isinstance(payload.get(field), list) and bool(payload[field])


def _executor_requested(payload: Mapping[str, Any]) -> bool:
    eligibility = payload.get("executor_eligibility")
    if not _is_mapping(eligibility):
        return False
    return eligibility.get("requested") is True or bool(eligibility.get("executor_class"))


def _workspace_bound(payload: Mapping[str, Any]) -> bool:
    workspace = payload.get("workspace_boundary")
    if not _is_mapping(workspace):
        return False
    return bool(workspace.get("mode")) and isinstance(workspace.get("allowed_roots"), list) and bool(workspace["allowed_roots"])


def _artifact_validation_bound(payload: Mapping[str, Any]) -> bool:
    validation = payload.get("validation_requirements")
    if not _is_mapping(validation):
        return False
    bindings = validation.get("artifact_validation_bindings")
    validators = validation.get("required_validators")
    return isinstance(bindings, list) and bool(bindings) and isinstance(validators, list) and bool(validators)


def _replay_receipt_bound(payload: Mapping[str, Any]) -> bool:
    replay = payload.get("replay_binding")
    if not _is_mapping(replay):
        return True
    if not replay.get("mode"):
        return False
    return all(replay.get(field) for field in ("receipt_ref", "receipt_hash", "ledger_ref"))


def _tool_capability_declared(payload: Mapping[str, Any]) -> bool:
    tool = payload.get("tool_invocation")
    if not _is_mapping(tool):
        return True
    capability = payload.get("capability_boundary")
    if not _is_mapping(capability):
        return False
    declared_tools = capability.get("tool_capabilities")
    return isinstance(declared_tools, list) and tool.get("tool_name") in declared_tools


def _handoff_recorded(payload: Mapping[str, Any]) -> bool:
    if "actor_transfer" not in payload:
        return True
    return _has_non_empty_mapping(payload, "handoff_record")


def _state_mutation_audited(payload: Mapping[str, Any]) -> bool:
    mutation = payload.get("state_mutation")
    if not (_is_mapping(mutation) and mutation.get("mutates") is True):
        return True
    return _has_non_empty_mapping(payload, "transition_intent") and _has_non_empty_mapping(payload, "audit_binding")


def _governance_approved_before_execution(payload: Mapping[str, Any]) -> bool:
    if not _executor_requested(payload):
        return True
    governance = payload.get("governance_requirements")
    return _is_mapping(governance) and governance.get("decision") == "approved"


def _kernel_20_binding_present(payload: Mapping[str, Any]) -> bool:
    binding = payload.get("kernel_binding")
    if not _is_mapping(binding):
        return False
    coverage = binding.get("coverage")
    return binding.get("kernel") == "Kernel 20" and isinstance(coverage, list) and bool(coverage)


def _kernel_20_minimal_bound(payload: Mapping[str, Any]) -> bool:
    binding = payload.get("kernel_binding")
    if not _is_mapping(binding):
        return False
    return minimal_kernel_binding_coverage(binding)


def _kernel_20_full_bound(payload: Mapping[str, Any]) -> bool:
    binding = payload.get("kernel_binding")
    return full_kernel20_coverage(binding)


def _minimal_spine_bound(payload: Mapping[str, Any]) -> bool:
    binding = payload.get("minimal_spine_binding")
    if not _is_mapping(binding):
        return False
    return set(binding.get("fields", [])) >= MINIMAL_SPINE_FIELDS and all(field in payload for field in MINIMAL_SPINE_FIELDS)


def validate_descriptor_spine_contract(payload: Any) -> dict[str, Any]:
    """Validate descriptor-to-Kernel-20/Minimal-Spine bindability without execution."""
    if not _is_mapping(payload):
        return {
            "accepted": False,
            "rejection_codes": [TASK_IDENTITY],
            "kernel_20_checked": False,
            "minimal_spine_checked": False,
        }

    rejection_codes: list[str] = []

    if not _has_non_empty_mapping(payload, "task_ref"):
        rejection_codes.append(TASK_IDENTITY)
    if not _has_non_empty_mapping(payload, "authority_binding"):
        rejection_codes.append(AUTHORITY_BINDING)
    if _executor_requested(payload) and not _workspace_bound(payload):
        rejection_codes.append(EXECUTOR_WORKSPACE)
    if _has_non_empty_list(payload, "artifact_expectation") and not _artifact_validation_bound(payload):
        rejection_codes.append(ARTIFACT_VALIDATION)
    if not _replay_receipt_bound(payload):
        rejection_codes.append(REPLAY_RECEIPT_LEDGER_HASH)
    if not _tool_capability_declared(payload):
        rejection_codes.append(TOOL_CAPABILITY)
    if not _handoff_recorded(payload):
        rejection_codes.append(HANDOFF_ACTOR_RECORD)
    if not _state_mutation_audited(payload):
        rejection_codes.append(STATE_TRANSITION_AUDIT)
    if not _governance_approved_before_execution(payload):
        rejection_codes.append(EXECUTION_GOVERNANCE)

    kernel_20_checked = _kernel_20_binding_present(payload)
    kernel_20_minimal_checked = _kernel_20_minimal_bound(payload)
    kernel_20_full_checked = _kernel_20_full_bound(payload)
    minimal_spine_checked = _minimal_spine_bound(payload)
    if not kernel_20_checked:
        rejection_codes.append(KERNEL_20_BINDING)
    elif not kernel_20_minimal_checked:
        # Enforce that any declared Kernel 20 binding also satisfies the
        # minimal Kernel20 binding expectation.
        rejection_codes.append(KERNEL_20_BINDING)
    if not minimal_spine_checked:
        rejection_codes.append(MINIMAL_SPINE_BINDING)

    return {
        "accepted": not rejection_codes,
        "rejection_codes": rejection_codes,
        "kernel_20_checked": kernel_20_checked,
        "kernel_20_minimal_checked": kernel_20_minimal_checked,
        "kernel_20_full_checked": kernel_20_full_checked,
        "kernel20_coverage_report": describe_kernel20_coverage(payload.get("kernel_binding")),
        "minimal_spine_checked": minimal_spine_checked,
    }
