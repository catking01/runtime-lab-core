"""Hash-bound authority packet construction and verification for R114."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from runtime_lab import descriptors
from runtime_lab.descriptors import schema

from .canonical import canonical_hash, packet_hash_payload
from .verify import verify_authority_packet

R114_AUTHORITY_SCHEMA_VERSION = "authority_packet.v1"
R114_CURRENT_EPOCH = "r114-local-epoch"
ISSUER_IDENTITY_ID = "governance:runtime_lab"
ISSUER_ROLE = "governance_authority"
SUBJECT_ACTOR_ID = "actor:local_runtime"
SUBJECT_ACTOR_TYPE = "runtime_actor"
ADMISSION_CAPABILITY_GRANT = {"capability": "admission.evaluate", "scope": "descriptor_intake_only"}


def _descriptor_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    allowed = set(schema.ALLOWED_FIELDS)
    return {key: value for key, value in payload.items() if key in allowed}


def compute_descriptor_payload_hash(payload: Mapping[str, Any]) -> str:
    """Compute the descriptor canonical hash used by authority task binding."""

    validated = descriptors.validator.validate_descriptor(_descriptor_payload(payload))
    descriptor_hash = validated.get("canonical_hash")
    if not isinstance(descriptor_hash, str) or not descriptor_hash:
        raise ValueError("descriptor canonical hash missing")
    return descriptor_hash


def _task_id(payload: Mapping[str, Any]) -> str:
    task_ref = payload.get("task_ref")
    if isinstance(task_ref, Mapping):
        value = task_ref.get("task_id")
        if isinstance(value, str):
            return value
    return ""


def _workspace_roots(payload: Mapping[str, Any]) -> list[str]:
    workspace = payload.get("workspace_boundary")
    if isinstance(workspace, Mapping):
        roots = workspace.get("allowed_roots")
        if isinstance(roots, list):
            return [item for item in roots if isinstance(item, str)]
    return []


def _artifact_expectations(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    raw_items = payload.get("artifact_expectation")
    if not isinstance(raw_items, list):
        return []
    items: list[dict[str, str]] = []
    for item in raw_items:
        if not isinstance(item, Mapping):
            continue
        artifact_class = item.get("artifact_class")
        logical_path = item.get("logical_path")
        if isinstance(artifact_class, str) and isinstance(logical_path, str):
            items.append({"artifact_class": artifact_class, "logical_path": logical_path})
    return items


def _complete_packet_hash(packet: dict[str, Any]) -> dict[str, Any]:
    payload_hash = canonical_hash(packet_hash_payload(packet))
    return {
        **packet,
        "packet_id": f"authpkt_{payload_hash.removeprefix('sha256:')[:16]}",
        "payload_hash": payload_hash,
    }


def build_authority_packet(
    payload: Mapping[str, Any],
    *,
    issuer_identity_id: str = ISSUER_IDENTITY_ID,
    issuer_role: str = ISSUER_ROLE,
    subject_actor_id: str = SUBJECT_ACTOR_ID,
    subject_actor_type: str = SUBJECT_ACTOR_TYPE,
    task_id: str | None = None,
    decision_ref: str | None = None,
    policy_epoch: str = "r114",
    workspace_ref: str | None = None,
    allowed_roots: Sequence[str] | None = None,
    expected_artifacts: Sequence[Mapping[str, str]] | None = None,
    capability_grants: Sequence[Mapping[str, str]] | None = None,
    not_before: str | None = R114_CURRENT_EPOCH,
    expires_at: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic R114 authority packet for descriptor intake."""

    descriptor_hash = compute_descriptor_payload_hash(payload)
    governance = payload.get("governance_requirements")
    packet = {
        "schema_version": R114_AUTHORITY_SCHEMA_VERSION,
        "packet_id": "",
        "issuer": {
            "identity_id": issuer_identity_id,
            "role": issuer_role,
        },
        "subject": {
            "actor_id": subject_actor_id,
            "actor_type": subject_actor_type,
        },
        "task_binding": {
            "task_id": task_id if task_id is not None else _task_id(payload),
            "descriptor_hash": descriptor_hash,
        },
        "governance_binding": {
            "decision_ref": decision_ref
            if decision_ref is not None
            else governance.get("decision_ref", "")
            if isinstance(governance, Mapping)
            else "",
            "policy_epoch": policy_epoch,
        },
        "workspace_binding": {
            "workspace_ref": workspace_ref if workspace_ref is not None else f"workspace:{_task_id(payload)}",
            "allowed_roots": list(allowed_roots) if allowed_roots is not None else _workspace_roots(payload),
        },
        "artifact_binding": {
            "expected_artifacts": [dict(item) for item in expected_artifacts]
            if expected_artifacts is not None
            else _artifact_expectations(payload),
        },
        "capability_grants": [dict(item) for item in capability_grants]
        if capability_grants is not None
        else [dict(ADMISSION_CAPABILITY_GRANT)],
        "not_before": not_before,
        "expires_at": expires_at,
        "payload_hash": "",
    }
    return _complete_packet_hash(packet)
