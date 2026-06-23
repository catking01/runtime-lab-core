from __future__ import annotations

from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Any

SUPPORTED_DESCRIPTOR_VERSION = "stage_b1.v1"
ALLOWED_ACTION_TYPES = {"write_text_artifact"}

FIELD_SPECS: dict[str, dict[str, str]] = {
    "descriptor_version": {"class": "required"},
    "descriptor_id": {"class": "derived"},
    "task_ref": {"class": "required"},
    "state_ref": {"class": "required"},
    "transition_intent": {"class": "required"},
    "authority_binding": {"class": "required"},
    "identity_binding": {"class": "required"},
    "capability_boundary": {"class": "required"},
    "executor_eligibility": {"class": "optional"},
    "workspace_boundary": {"class": "required"},
    "artifact_expectation": {"class": "required"},
    "validation_requirements": {"class": "required"},
    "governance_requirements": {"class": "required"},
    "replay_binding": {"class": "required"},
    "audit_binding": {"class": "required"},
    "non_claims": {"class": "required"},
    "logical_clock": {"class": "required"},
    "created_at": {"class": "forbidden"},
    "canonical_hash": {"class": "derived"},
    "descriptor_hash": {"class": "derived"},
    "action_type": {"class": "required"},
    "determinism_level": {"class": "required"},
    "preconditions": {"class": "optional"},
    "postconditions": {"class": "optional"},
    "compatibility_refs": {"class": "optional"},
    "notes": {"class": "optional"},
    "unknown_fields": {"class": "forbidden"},
}

FORBIDDEN_FIELDS = {
    name for name, spec in FIELD_SPECS.items() if spec["class"] == "forbidden"
} | {
    "network_endpoint",
    "shell_command",
    "tool_call",
    "secret_material",
    "executable_blob",
    "mutable_handle",
}

ALLOWED_EXECUTOR_CLASSES = {"descriptor_only", "validator_only"}
REQUIRED_FIELDS = {name for name, spec in FIELD_SPECS.items() if spec["class"] == "required"}
ALLOWED_FIELDS = set(FIELD_SPECS) | FORBIDDEN_FIELDS
OPTIONAL_TEXT_LIST_FIELDS = {"preconditions", "postconditions", "compatibility_refs", "notes"}
REQUIRED_TEXT_LIST_FIELDS = {"non_claims"}
REQUIRED_STRING_FIELDS = {"descriptor_version", "action_type", "determinism_level", "logical_clock"}
NESTED_REQUIRED_STRING_FIELDS = {
    "task_ref": {"task_id"},
    "state_ref": {"state_id"},
    "transition_intent": {"target", "type"},
    "audit_binding": {"evidence_status"},
    "replay_binding": {"mode"},
}
NESTED_REQUIRED_LIST_FIELDS = {
    "identity_binding": {"identity_fields"},
    "audit_binding": {"required_audit_trail"},
    "replay_binding": {"replay_signature_fields"},
}
ARTIFACT_ALLOWED_FIELDS = {"artifact_class", "format", "logical_path", "binding_method"}
ARTIFACT_REQUIRED_FIELDS = ARTIFACT_ALLOWED_FIELDS
REQUIRED_REPLAY_SIGNATURE_FIELDS = ["canonical_hash", "logical_clock"]


def field_specs() -> dict[str, dict[str, str]]:
    return FIELD_SPECS


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_non_empty_string_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(_is_non_empty_string(item) for item in value)


def _validate_required_string_fields(payload: Mapping[str, Any]) -> str | None:
    for field in REQUIRED_STRING_FIELDS:
        if not _is_non_empty_string(payload.get(field)):
            return "B1_DESCRIPTOR_MISSING_REQUIRED_FIELD"
    if payload.get("descriptor_version") != SUPPORTED_DESCRIPTOR_VERSION:
        return "B1_DESCRIPTOR_MISSING_REQUIRED_FIELD"
    if payload.get("action_type") not in ALLOWED_ACTION_TYPES:
        return "B1_DESCRIPTOR_MISSING_REQUIRED_FIELD"
    return None


def _validate_text_list_fields(payload: Mapping[str, Any]) -> str | None:
    for field in REQUIRED_TEXT_LIST_FIELDS:
        if not _is_non_empty_string_list(payload.get(field)):
            return "B1_DESCRIPTOR_MISSING_REQUIRED_FIELD"
    for field in OPTIONAL_TEXT_LIST_FIELDS:
        if field in payload and not _is_non_empty_string_list(payload[field]):
            return "B1_DESCRIPTOR_INVALID_FIELD_TYPE"
    return None


def _validate_nested_fields(payload: Mapping[str, Any]) -> str | None:
    for field, required_keys in NESTED_REQUIRED_STRING_FIELDS.items():
        value = payload.get(field)
        if not isinstance(value, Mapping):
            return "B1_DESCRIPTOR_INVALID_FIELD_TYPE"
        for key in required_keys:
            if not _is_non_empty_string(value.get(key)):
                return "B1_DESCRIPTOR_MISSING_REQUIRED_FIELD"

    for field, required_keys in NESTED_REQUIRED_LIST_FIELDS.items():
        value = payload.get(field)
        if not isinstance(value, Mapping):
            return "B1_DESCRIPTOR_INVALID_FIELD_TYPE"
        for key in required_keys:
            if not _is_non_empty_string_list(value.get(key)):
                return "B1_DESCRIPTOR_MISSING_REQUIRED_FIELD"
        if field == "replay_binding" and value.get("replay_signature_fields") != REQUIRED_REPLAY_SIGNATURE_FIELDS:
            return "B1_DESCRIPTOR_MISSING_REQUIRED_FIELD"

    return None


def _artifact_path_within_workspace_boundary(
    logical_path: str,
    workspace_boundary: Mapping[str, Any],
) -> bool:
    allowed_roots = workspace_boundary.get("allowed_roots")
    if not isinstance(allowed_roots, list) or len(allowed_roots) != 1:
        return False
    allowed_root = allowed_roots[0]
    if not _is_non_empty_string(allowed_root):
        return False

    path = PurePosixPath(logical_path)
    if path.is_absolute() or ".." in path.parts:
        return False

    root = PurePosixPath(allowed_root)
    if ".." in root.parts or root.is_absolute():
        return False

    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _validate_artifact_expectation(payload: Mapping[str, Any]) -> str | None:
    value = payload.get("artifact_expectation")
    if not isinstance(value, list):
        return "B1_DESCRIPTOR_INVALID_FIELD_TYPE"
    for item in value:
        if not isinstance(item, Mapping):
            return "B1_DESCRIPTOR_INVALID_FIELD_TYPE"
        unknown_fields = set(item) - ARTIFACT_ALLOWED_FIELDS
        if unknown_fields:
            return "B1_DESCRIPTOR_UNKNOWN_FIELD"
        for key in ARTIFACT_REQUIRED_FIELDS:
            if not _is_non_empty_string(item.get(key)):
                return "B1_DESCRIPTOR_MISSING_REQUIRED_FIELD"
        if not _artifact_path_within_workspace_boundary(item["logical_path"], payload.get("workspace_boundary", {})):
            return "B1_DESCRIPTOR_MISSING_REQUIRED_FIELD"
    return None


def validate_schema_shape(payload: Any) -> list[str]:
    if not isinstance(payload, Mapping):
        return ["B1_DESCRIPTOR_INVALID_FIELD_TYPE"]

    if any(field in payload for field in FORBIDDEN_FIELDS):
        return ["B1_DESCRIPTOR_FORBIDDEN_FIELD"]

    unknown_fields = sorted(set(payload) - ALLOWED_FIELDS)
    if unknown_fields:
        return ["B1_DESCRIPTOR_UNKNOWN_FIELD"]

    missing = [field for field in REQUIRED_FIELDS if field not in payload]
    if missing:
        return ["B1_DESCRIPTOR_MISSING_REQUIRED_FIELD"]

    string_error = _validate_required_string_fields(payload)
    if string_error:
        return [string_error]

    text_list_error = _validate_text_list_fields(payload)
    if text_list_error:
        return [text_list_error]

    nested_error = _validate_nested_fields(payload)
    if nested_error:
        return [nested_error]

    artifact_error = _validate_artifact_expectation(payload)
    if artifact_error:
        return [artifact_error]

    executor_eligibility = payload.get("executor_eligibility")
    if isinstance(executor_eligibility, Mapping):
        executor_class = executor_eligibility.get("executor_class")
        if executor_class not in ALLOWED_EXECUTOR_CLASSES:
            return ["B1_DESCRIPTOR_UNKNOWN_FIELD"]

    return []
