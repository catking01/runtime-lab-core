"""Deterministic artifact-store control layer for R116.

R116 validates artifact-store requests and emits canonical receipts/manifests.
It intentionally does not write artifacts, dispatch executors, invoke tools,
invoke LLMs, or implement a replay engine.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Any

from runtime_lab.authority.canonical import canonical_hash

ARTIFACT_REQUEST_MALFORMED = "ARTIFACT_REQUEST_MALFORMED"
ARTIFACT_POLICY_MALFORMED = "ARTIFACT_POLICY_MALFORMED"
ARTIFACT_TASK_BINDING_REQUIRED = "ARTIFACT_TASK_BINDING_REQUIRED"
ARTIFACT_TASK_BINDING_MISMATCH = "ARTIFACT_TASK_BINDING_MISMATCH"
ARTIFACT_DESCRIPTOR_HASH_MISMATCH = "ARTIFACT_DESCRIPTOR_HASH_MISMATCH"
ARTIFACT_AUTHORITY_RECEIPT_MISMATCH = "ARTIFACT_AUTHORITY_RECEIPT_MISMATCH"
ARTIFACT_WORKSPACE_TRANSACTION_RECEIPT_REQUIRED = "ARTIFACT_WORKSPACE_TRANSACTION_RECEIPT_REQUIRED"
ARTIFACT_WORKSPACE_TRANSACTION_RECEIPT_MISMATCH = "ARTIFACT_WORKSPACE_TRANSACTION_RECEIPT_MISMATCH"
ARTIFACT_CONTENT_HASH_MISMATCH = "ARTIFACT_CONTENT_HASH_MISMATCH"
ARTIFACT_TYPE_NOT_ALLOWED = "ARTIFACT_TYPE_NOT_ALLOWED"
ARTIFACT_MEDIA_TYPE_NOT_ALLOWED = "ARTIFACT_MEDIA_TYPE_NOT_ALLOWED"
ARTIFACT_SIZE_LIMIT_EXCEEDED = "ARTIFACT_SIZE_LIMIT_EXCEEDED"
ARTIFACT_NAME_PATH_TRAVERSAL_REJECTED = "ARTIFACT_NAME_PATH_TRAVERSAL_REJECTED"
ARTIFACT_NAME_ABSOLUTE_PATH_REJECTED = "ARTIFACT_NAME_ABSOLUTE_PATH_REJECTED"
ARTIFACT_MANIFEST_MISSING_REQUIRED_FIELD = "ARTIFACT_MANIFEST_MISSING_REQUIRED_FIELD"
ARTIFACT_MANIFEST_FORBIDDEN_FIELD = "ARTIFACT_MANIFEST_FORBIDDEN_FIELD"

MANIFEST_REQUIRED_FIELDS = {"schema_version", "artifact_name", "artifact_type", "media_type"}
MANIFEST_ALLOWED_FIELDS = MANIFEST_REQUIRED_FIELDS | {"content_hash", "size_bytes"}
MANIFEST_FORBIDDEN_FIELDS = {
    "shell_command",
    "tool_call",
    "tool_invocation",
    "llm_invocation",
    "network_endpoint",
    "secret_material",
    "executable_blob",
    "mutable_handle",
    "replay_engine",
}


def _is_mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


def _string_list(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    if not all(isinstance(item, str) for item in value):
        return None
    return list(value)


def _sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _content_bytes(content: Any) -> bytes | None:
    if isinstance(content, str):
        return content.encode("utf-8")
    if isinstance(content, bytes):
        return content
    return None


def _has_traversal(path: str) -> bool:
    return any(part == ".." for part in PurePosixPath(path).parts)


def _receipt_hash_payload(receipt: Mapping[str, Any]) -> dict[str, Any]:
    candidate = dict(receipt)
    candidate.pop("receipt_hash", None)
    return candidate


def _base_result(*, accepted: bool, status: str, rejection_codes: list[str], receipt: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "accepted": accepted,
        "status": status,
        "rejection_codes": list(dict.fromkeys(rejection_codes)),
        "receipt": receipt,
        "executor_dispatch_performed": False,
        "tool_invocation_performed": False,
        "llm_invocation_performed": False,
        "replay_engine_performed": False,
    }


def _reject(code: str) -> dict[str, Any]:
    return _base_result(accepted=False, status="rejected", rejection_codes=[code])


def _manifest_error(manifest: Any) -> str | None:
    if not _is_mapping(manifest):
        return ARTIFACT_MANIFEST_MISSING_REQUIRED_FIELD
    if MANIFEST_FORBIDDEN_FIELDS & set(manifest):
        return ARTIFACT_MANIFEST_FORBIDDEN_FIELD
    if set(manifest) - MANIFEST_ALLOWED_FIELDS:
        return ARTIFACT_MANIFEST_FORBIDDEN_FIELD
    for field in MANIFEST_REQUIRED_FIELDS:
        if not isinstance(manifest.get(field), str) or not manifest.get(field):
            return ARTIFACT_MANIFEST_MISSING_REQUIRED_FIELD
    return None


def _policy_list(policy: Mapping[str, Any], field: str) -> list[str] | None:
    return _string_list(policy.get(field))


def _validate_policy(policy: Any) -> dict[str, Any] | None:
    if not _is_mapping(policy):
        return None
    policy_map = dict(policy)
    required_string_fields = (
        "task_id",
        "descriptor_hash",
        "authority_receipt_hash",
        "workspace_transaction_receipt_hash",
    )
    for field in required_string_fields:
        if not isinstance(policy_map.get(field), str) or not policy_map.get(field):
            return None
    if _policy_list(policy_map, "allowed_artifact_types") is None:
        return None
    if _policy_list(policy_map, "allowed_media_types") is None:
        return None
    if not isinstance(policy_map.get("max_size_bytes"), int) or policy_map["max_size_bytes"] < 0:
        return None
    return policy_map


def _artifact_id(content_hash: str) -> str:
    return f"artifact_{content_hash.removeprefix('sha256:')[:16]}"


def _accepted_receipt(request: Mapping[str, Any], policy: Mapping[str, Any], content_hash: str, content_size: int) -> dict[str, Any]:
    manifest = {
        "schema_version": "artifact_manifest.v1",
        "artifact_name": request["artifact_name"],
        "artifact_type": request["artifact_type"],
        "media_type": request["media_type"],
        "content_hash": content_hash,
        "size_bytes": content_size,
    }
    manifest_hash = canonical_hash(manifest)
    metadata = {
        "artifact_name": request["artifact_name"],
        "artifact_type": request["artifact_type"],
        "media_type": request["media_type"],
        "size_bytes": content_size,
        "task_id": request["task_id"],
        "descriptor_hash": request["descriptor_hash"],
    }
    receipt = {
        "schema_version": "artifact_receipt.v1",
        "artifact_id": _artifact_id(content_hash),
        "artifact_name": request["artifact_name"],
        "artifact_type": request["artifact_type"],
        "media_type": request["media_type"],
        "size_bytes": content_size,
        "content_hash": content_hash,
        "metadata_hash": canonical_hash(metadata),
        "manifest_hash": manifest_hash,
        "manifest": manifest,
        "task_id": request["task_id"],
        "descriptor_hash": request["descriptor_hash"],
        "authority_receipt_hash": request["authority_receipt_hash"],
        "workspace_transaction_receipt_hash": request["workspace_transaction_receipt_hash"],
        "policy_hash": canonical_hash(
            {
                "task_id": policy["task_id"],
                "descriptor_hash": policy["descriptor_hash"],
                "authority_receipt_hash": policy["authority_receipt_hash"],
                "workspace_transaction_receipt_hash": policy["workspace_transaction_receipt_hash"],
                "allowed_artifact_types": sorted(policy["allowed_artifact_types"]),
                "allowed_media_types": sorted(policy["allowed_media_types"]),
                "max_size_bytes": policy["max_size_bytes"],
            }
        ),
        "executor_dispatch_performed": False,
        "tool_invocation_performed": False,
        "llm_invocation_performed": False,
        "replay_engine_performed": False,
        "receipt_hash": "",
    }
    receipt["receipt_hash"] = canonical_hash(_receipt_hash_payload(receipt))
    return receipt


def verify_artifact_receipt(receipt: Mapping[str, Any]) -> bool:
    """Verify a deterministic R116 artifact receipt hash."""

    if not _is_mapping(receipt):
        return False
    provided = receipt.get("receipt_hash")
    return isinstance(provided, str) and provided.startswith("sha256:") and canonical_hash(
        _receipt_hash_payload(receipt)
    ) == provided


def store_artifact(request: Any, policy: Any) -> dict[str, Any]:
    """Validate an artifact-store request and emit a deterministic receipt.

    This is an artifact-store control layer. It does not persist files.
    """

    if not _is_mapping(request):
        return _reject(ARTIFACT_REQUEST_MALFORMED)
    policy_map = _validate_policy(policy)
    if policy_map is None:
        return _reject(ARTIFACT_POLICY_MALFORMED)

    request_map = dict(request)
    if not isinstance(request_map.get("task_id"), str) or not request_map.get("task_id"):
        return _reject(ARTIFACT_TASK_BINDING_REQUIRED)
    if request_map["task_id"] != policy_map["task_id"]:
        return _reject(ARTIFACT_TASK_BINDING_MISMATCH)
    if request_map.get("descriptor_hash") != policy_map["descriptor_hash"]:
        return _reject(ARTIFACT_DESCRIPTOR_HASH_MISMATCH)
    if request_map.get("authority_receipt_hash") != policy_map["authority_receipt_hash"]:
        return _reject(ARTIFACT_AUTHORITY_RECEIPT_MISMATCH)
    if not isinstance(request_map.get("workspace_transaction_receipt_hash"), str) or not request_map.get(
        "workspace_transaction_receipt_hash"
    ):
        return _reject(ARTIFACT_WORKSPACE_TRANSACTION_RECEIPT_REQUIRED)
    if request_map["workspace_transaction_receipt_hash"] != policy_map["workspace_transaction_receipt_hash"]:
        return _reject(ARTIFACT_WORKSPACE_TRANSACTION_RECEIPT_MISMATCH)

    for field in ("artifact_name", "artifact_type", "media_type"):
        if not isinstance(request_map.get(field), str) or not request_map.get(field):
            return _reject(ARTIFACT_REQUEST_MALFORMED)

    artifact_name = request_map["artifact_name"]
    path = PurePosixPath(artifact_name)
    if path.is_absolute():
        return _reject(ARTIFACT_NAME_ABSOLUTE_PATH_REJECTED)
    if _has_traversal(artifact_name):
        return _reject(ARTIFACT_NAME_PATH_TRAVERSAL_REJECTED)

    manifest_error = _manifest_error(request_map.get("manifest"))
    if manifest_error:
        return _reject(manifest_error)
    manifest = dict(request_map["manifest"])
    for field in ("artifact_name", "artifact_type", "media_type"):
        if manifest[field] != request_map[field]:
            return _reject(ARTIFACT_MANIFEST_MISSING_REQUIRED_FIELD)

    if request_map["artifact_type"] not in policy_map["allowed_artifact_types"]:
        return _reject(ARTIFACT_TYPE_NOT_ALLOWED)
    if request_map["media_type"] not in policy_map["allowed_media_types"]:
        return _reject(ARTIFACT_MEDIA_TYPE_NOT_ALLOWED)

    content = _content_bytes(request_map.get("content"))
    if content is None:
        return _reject(ARTIFACT_REQUEST_MALFORMED)
    if len(content) > policy_map["max_size_bytes"]:
        return _reject(ARTIFACT_SIZE_LIMIT_EXCEEDED)

    content_hash = _sha256_bytes(content)
    if request_map.get("expected_content_hash") != content_hash:
        return _reject(ARTIFACT_CONTENT_HASH_MISMATCH)

    receipt = _accepted_receipt(request_map, policy_map, content_hash, len(content))
    return _base_result(accepted=True, status="stored", rejection_codes=[], receipt=receipt)
