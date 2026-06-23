"""Fail-closed verification for R114 authority packets."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .canonical import canonical_hash, packet_hash_payload
from .errors import (
    AUTHORITY_PACKET_ARTIFACT_SCOPE_MISMATCH,
    AUTHORITY_PACKET_CAPABILITY_ESCALATION,
    AUTHORITY_PACKET_CAPABILITY_NOT_GRANTED,
    AUTHORITY_PACKET_DESCRIPTOR_HASH_MISMATCH,
    AUTHORITY_PACKET_FORGED_IDENTITY,
    AUTHORITY_PACKET_HASH_MISMATCH,
    AUTHORITY_PACKET_MALFORMED,
    AUTHORITY_PACKET_STALE_OR_NOT_YET_VALID,
    AUTHORITY_PACKET_TASK_BINDING_MISMATCH,
    AUTHORITY_PACKET_WORKSPACE_SCOPE_MISMATCH,
)

R114_CURRENT_EPOCH = "r114-local-epoch"
EXPECTED_ISSUER_IDENTITY_ID = "governance:runtime_lab"
EXPECTED_ISSUER_ROLE = "governance_authority"
EXPECTED_SUBJECT_ACTOR_ID = "actor:local_runtime"
EXPECTED_SUBJECT_ACTOR_TYPE = "runtime_actor"
ALLOWED_CAPABILITY = {"capability": "admission.evaluate", "scope": "descriptor_intake_only"}


def _rejected(packet: Mapping[str, Any] | None, codes: list[str]) -> dict[str, Any]:
    return {
        "accepted": False,
        "rejection_codes": list(dict.fromkeys(codes)),
        "authority_packet_id": packet.get("packet_id") if isinstance(packet, Mapping) else None,
        "authority_packet_hash": packet.get("payload_hash") if isinstance(packet, Mapping) else None,
    }


def _accepted(packet: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "accepted": True,
        "rejection_codes": [],
        "authority_packet_id": packet.get("packet_id"),
        "authority_packet_hash": packet.get("payload_hash"),
    }


def _is_mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


def _descriptor_hash(payload: Mapping[str, Any]) -> str:
    from .packet import compute_descriptor_payload_hash

    return compute_descriptor_payload_hash(payload)


def _payload_task_id(payload: Mapping[str, Any]) -> str:
    task_ref = payload.get("task_ref")
    if _is_mapping(task_ref):
        task_id = task_ref.get("task_id")
        if isinstance(task_id, str):
            return task_id
    return ""


def _payload_roots(payload: Mapping[str, Any]) -> list[str]:
    workspace = payload.get("workspace_boundary")
    if _is_mapping(workspace):
        roots = workspace.get("allowed_roots")
        if isinstance(roots, list):
            return sorted(item for item in roots if isinstance(item, str))
    return []


def _packet_roots(packet: Mapping[str, Any]) -> list[str]:
    workspace = packet.get("workspace_binding")
    if _is_mapping(workspace):
        roots = workspace.get("allowed_roots")
        if isinstance(roots, list):
            return sorted(item for item in roots if isinstance(item, str))
    return []


def _payload_artifacts(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    raw_items = payload.get("artifact_expectation")
    if not isinstance(raw_items, list):
        return []
    normalized = []
    for item in raw_items:
        if not _is_mapping(item):
            continue
        artifact_class = item.get("artifact_class")
        logical_path = item.get("logical_path")
        if isinstance(artifact_class, str) and isinstance(logical_path, str):
            normalized.append({"artifact_class": artifact_class, "logical_path": logical_path})
    return sorted(normalized, key=lambda value: (value["artifact_class"], value["logical_path"]))


def _packet_artifacts(packet: Mapping[str, Any]) -> list[dict[str, str]]:
    binding = packet.get("artifact_binding")
    if not _is_mapping(binding):
        return []
    raw_items = binding.get("expected_artifacts")
    if not isinstance(raw_items, list):
        return []
    normalized = []
    for item in raw_items:
        if not _is_mapping(item):
            continue
        artifact_class = item.get("artifact_class")
        logical_path = item.get("logical_path")
        if isinstance(artifact_class, str) and isinstance(logical_path, str):
            normalized.append({"artifact_class": artifact_class, "logical_path": logical_path})
    return sorted(normalized, key=lambda value: (value["artifact_class"], value["logical_path"]))


def _capability_codes(packet: Mapping[str, Any]) -> list[str]:
    grants = packet.get("capability_grants")
    if not isinstance(grants, list):
        return [AUTHORITY_PACKET_CAPABILITY_NOT_GRANTED]

    normalized = [dict(grant) for grant in grants if _is_mapping(grant)]
    if ALLOWED_CAPABILITY not in normalized:
        return [AUTHORITY_PACKET_CAPABILITY_NOT_GRANTED]

    if any(grant != ALLOWED_CAPABILITY for grant in normalized):
        return [AUTHORITY_PACKET_CAPABILITY_ESCALATION]

    return []


def verify_authority_packet(packet: Any, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Verify an R114 authority packet against a descriptor payload."""

    if not _is_mapping(packet):
        return _rejected(None, [AUTHORITY_PACKET_MALFORMED])

    packet_map = dict(packet)
    required = (
        "schema_version",
        "packet_id",
        "issuer",
        "subject",
        "task_binding",
        "governance_binding",
        "workspace_binding",
        "artifact_binding",
        "capability_grants",
        "payload_hash",
    )
    if any(key not in packet_map for key in required):
        return _rejected(packet_map, [AUTHORITY_PACKET_MALFORMED])

    expected_hash = canonical_hash(packet_hash_payload(packet_map))
    packet_hash = packet_map.get("payload_hash")
    expected_packet_id = f"authpkt_{expected_hash.removeprefix('sha256:')[:16]}"
    if packet_hash != expected_hash or packet_map.get("packet_id") != expected_packet_id:
        return _rejected(packet_map, [AUTHORITY_PACKET_HASH_MISMATCH])

    issuer = packet_map.get("issuer")
    subject = packet_map.get("subject")
    if not _is_mapping(issuer) or not _is_mapping(subject):
        return _rejected(packet_map, [AUTHORITY_PACKET_MALFORMED])
    if issuer.get("identity_id") != EXPECTED_ISSUER_IDENTITY_ID or issuer.get("role") != EXPECTED_ISSUER_ROLE:
        return _rejected(packet_map, [AUTHORITY_PACKET_FORGED_IDENTITY])
    if subject.get("actor_id") != EXPECTED_SUBJECT_ACTOR_ID or subject.get("actor_type") != EXPECTED_SUBJECT_ACTOR_TYPE:
        return _rejected(packet_map, [AUTHORITY_PACKET_FORGED_IDENTITY])

    if packet_map.get("not_before") not in (None, R114_CURRENT_EPOCH):
        return _rejected(packet_map, [AUTHORITY_PACKET_STALE_OR_NOT_YET_VALID])
    if packet_map.get("expires_at") not in (None, R114_CURRENT_EPOCH):
        return _rejected(packet_map, [AUTHORITY_PACKET_STALE_OR_NOT_YET_VALID])

    task_binding = packet_map.get("task_binding")
    if not _is_mapping(task_binding):
        return _rejected(packet_map, [AUTHORITY_PACKET_MALFORMED])
    if task_binding.get("descriptor_hash") != _descriptor_hash(payload):
        return _rejected(packet_map, [AUTHORITY_PACKET_DESCRIPTOR_HASH_MISMATCH])
    if task_binding.get("task_id") != _payload_task_id(payload):
        return _rejected(packet_map, [AUTHORITY_PACKET_TASK_BINDING_MISMATCH])

    capability_codes = _capability_codes(packet_map)
    if capability_codes:
        return _rejected(packet_map, capability_codes)

    if _packet_roots(packet_map) != _payload_roots(payload):
        return _rejected(packet_map, [AUTHORITY_PACKET_WORKSPACE_SCOPE_MISMATCH])

    if _packet_artifacts(packet_map) != _payload_artifacts(payload):
        return _rejected(packet_map, [AUTHORITY_PACKET_ARTIFACT_SCOPE_MISMATCH])

    return _accepted(packet_map)
