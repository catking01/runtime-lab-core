"""Bounded real executor v0 for R117.

R117 intentionally supports only the `write_text_artifact` action. It requires
R114 authority, R115 workspace transaction, and R116 artifact receipt bindings
before writing one text artifact into an isolated workspace root.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from runtime_lab.artifact_store import verify_artifact_receipt
from runtime_lab.authority.canonical import canonical_hash
from runtime_lab.authority.packet import compute_descriptor_payload_hash
from runtime_lab.authority.verify import verify_authority_packet
from runtime_lab.workspace import verify_workspace_transaction_receipt

EXECUTOR_REQUEST_MALFORMED = "EXECUTOR_REQUEST_MALFORMED"
EXECUTOR_ACTION_NOT_ALLOWED = "EXECUTOR_ACTION_NOT_ALLOWED"
EXECUTOR_FORBIDDEN_FIELD = "EXECUTOR_FORBIDDEN_FIELD"
EXECUTOR_AUTHORITY_PACKET_REQUIRED = "EXECUTOR_AUTHORITY_PACKET_REQUIRED"
EXECUTOR_DESCRIPTOR_HASH_MISMATCH = "EXECUTOR_DESCRIPTOR_HASH_MISMATCH"
EXECUTOR_WORKSPACE_TRANSACTION_RECEIPT_REQUIRED = "EXECUTOR_WORKSPACE_TRANSACTION_RECEIPT_REQUIRED"
EXECUTOR_WORKSPACE_TRANSACTION_RECEIPT_INVALID = "EXECUTOR_WORKSPACE_TRANSACTION_RECEIPT_INVALID"
EXECUTOR_WORKSPACE_TRANSACTION_RECEIPT_MISMATCH = "EXECUTOR_WORKSPACE_TRANSACTION_RECEIPT_MISMATCH"
EXECUTOR_ARTIFACT_RECEIPT_REQUIRED = "EXECUTOR_ARTIFACT_RECEIPT_REQUIRED"
EXECUTOR_ARTIFACT_RECEIPT_INVALID = "EXECUTOR_ARTIFACT_RECEIPT_INVALID"
EXECUTOR_ARTIFACT_RECEIPT_MISMATCH = "EXECUTOR_ARTIFACT_RECEIPT_MISMATCH"
EXECUTOR_CONTENT_HASH_MISMATCH = "EXECUTOR_CONTENT_HASH_MISMATCH"
EXECUTOR_OUTPUT_PATH_ABSOLUTE_REJECTED = "EXECUTOR_OUTPUT_PATH_ABSOLUTE_REJECTED"
EXECUTOR_OUTPUT_PATH_TRAVERSAL_REJECTED = "EXECUTOR_OUTPUT_PATH_TRAVERSAL_REJECTED"
EXECUTOR_OUTPUT_PATH_OUTSIDE_WORKSPACE = "EXECUTOR_OUTPUT_PATH_OUTSIDE_WORKSPACE"
EXECUTOR_DENIED_PATH_REJECTED = "EXECUTOR_DENIED_PATH_REJECTED"

FORBIDDEN_REQUEST_FIELDS = {
    "shell_command",
    "subprocess",
    "command",
    "tool_call",
    "tool_invocation",
    "llm_call",
    "llm_invocation",
    "network_endpoint",
    "http_request",
    "socket",
    "replay_engine",
    "arbitrary_action",
}


def _is_mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


def _sha256_text(content: str) -> str:
    return "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()


def _has_traversal(path: str) -> bool:
    return any(part == ".." for part in PurePosixPath(path).parts)


def _normalize_path(path: str) -> str:
    return str(PurePosixPath(path))


def _path_within_root(path: str, root: str) -> bool:
    normalized_path = _normalize_path(path)
    normalized_root = _normalize_path(root)
    return normalized_path == normalized_root or normalized_path.startswith(f"{normalized_root}/")


def _receipt_hash_payload(receipt: Mapping[str, Any]) -> dict[str, Any]:
    candidate = dict(receipt)
    candidate.pop("receipt_hash", None)
    return candidate


def _base_result(
    *,
    accepted: bool,
    status: str,
    rejection_codes: list[str],
    receipt: dict[str, Any] | None = None,
    artifact_write_performed: bool = False,
) -> dict[str, Any]:
    return {
        "accepted": accepted,
        "status": status,
        "rejection_codes": list(dict.fromkeys(rejection_codes)),
        "receipt": receipt,
        "artifact_write_performed": artifact_write_performed,
        "tool_invocation_performed": False,
        "llm_invocation_performed": False,
        "network_access_performed": False,
        "replay_engine_performed": False,
    }


def _reject(code: str) -> dict[str, Any]:
    return _base_result(accepted=False, status="rejected", rejection_codes=[code])


def _task_id(payload: Mapping[str, Any]) -> str:
    task_ref = payload.get("task_ref")
    if _is_mapping(task_ref):
        task_id = task_ref.get("task_id")
        if isinstance(task_id, str):
            return task_id
    return ""


def _required_string(request: Mapping[str, Any], field: str) -> str | None:
    value = request.get(field)
    if isinstance(value, str) and value:
        return value
    return None


def _workspace_receipt_mismatch(request: Mapping[str, Any], workspace_receipt: Mapping[str, Any]) -> str | None:
    if request.get("task_id") != workspace_receipt.get("task_id"):
        return EXECUTOR_WORKSPACE_TRANSACTION_RECEIPT_MISMATCH
    if request.get("descriptor_hash") != workspace_receipt.get("descriptor_hash"):
        return EXECUTOR_WORKSPACE_TRANSACTION_RECEIPT_MISMATCH
    return None


def _artifact_receipt_mismatch(request: Mapping[str, Any], artifact_receipt: Mapping[str, Any]) -> str | None:
    checks = {
        "task_id": "task_id",
        "descriptor_hash": "descriptor_hash",
        "output_path": "artifact_name",
        "expected_content_hash": "content_hash",
    }
    for request_field, receipt_field in checks.items():
        if request.get(request_field) != artifact_receipt.get(receipt_field):
            return EXECUTOR_ARTIFACT_RECEIPT_MISMATCH

    workspace_receipt = request.get("workspace_transaction_receipt")
    if not _is_mapping(workspace_receipt):
        return EXECUTOR_ARTIFACT_RECEIPT_MISMATCH
    if artifact_receipt.get("workspace_transaction_receipt_hash") != workspace_receipt.get("transaction_hash"):
        return EXECUTOR_ARTIFACT_RECEIPT_MISMATCH
    if artifact_receipt.get("authority_receipt_hash") != workspace_receipt.get("authority_receipt_hash"):
        return EXECUTOR_ARTIFACT_RECEIPT_MISMATCH
    if artifact_receipt.get("artifact_type") != "text_artifact":
        return EXECUTOR_ARTIFACT_RECEIPT_MISMATCH
    if artifact_receipt.get("media_type") != "text/plain":
        return EXECUTOR_ARTIFACT_RECEIPT_MISMATCH
    return None


def _output_path_error(output_path: str, workspace_receipt: Mapping[str, Any]) -> str | None:
    path = PurePosixPath(output_path)
    if path.is_absolute():
        return EXECUTOR_OUTPUT_PATH_ABSOLUTE_REJECTED
    if _has_traversal(output_path):
        return EXECUTOR_OUTPUT_PATH_TRAVERSAL_REJECTED

    normalized_output = _normalize_path(output_path)
    denied = {_normalize_path(path) for path in workspace_receipt.get("denied_paths", []) if isinstance(path, str)}
    if normalized_output in denied:
        return EXECUTOR_DENIED_PATH_REJECTED

    allowed_roots = [root for root in workspace_receipt.get("allowed_roots", []) if isinstance(root, str)]
    if not any(_path_within_root(normalized_output, root) for root in allowed_roots):
        return EXECUTOR_OUTPUT_PATH_OUTSIDE_WORKSPACE

    requested_paths = {_normalize_path(path) for path in workspace_receipt.get("requested_paths", []) if isinstance(path, str)}
    if normalized_output not in requested_paths:
        return EXECUTOR_WORKSPACE_TRANSACTION_RECEIPT_MISMATCH
    return None


def _executor_receipt(request: Mapping[str, Any]) -> dict[str, Any]:
    workspace_receipt = request["workspace_transaction_receipt"]
    artifact_receipt = request["artifact_receipt"]
    receipt = {
        "schema_version": "executor_receipt.v1",
        "executor": "write_text_artifact_v0",
        "action": "write_text_artifact",
        "task_id": request["task_id"],
        "descriptor_hash": request["descriptor_hash"],
        "authority_packet_id": request["authority_packet"]["packet_id"],
        "authority_receipt_hash": workspace_receipt["authority_receipt_hash"],
        "workspace_transaction_receipt_hash": workspace_receipt["transaction_hash"],
        "artifact_receipt_hash": artifact_receipt["receipt_hash"],
        "output_path": request["output_path"],
        "content_hash": request["expected_content_hash"],
        "artifact_write_performed": True,
        "tool_invocation_performed": False,
        "llm_invocation_performed": False,
        "network_access_performed": False,
        "replay_engine_performed": False,
        "receipt_hash": "",
    }
    receipt["receipt_hash"] = canonical_hash(_receipt_hash_payload(receipt))
    return receipt


def verify_executor_receipt(receipt: Mapping[str, Any]) -> bool:
    """Verify a deterministic R117 executor receipt."""

    if not _is_mapping(receipt):
        return False
    provided = receipt.get("receipt_hash")
    return isinstance(provided, str) and provided.startswith("sha256:") and canonical_hash(
        _receipt_hash_payload(receipt)
    ) == provided


def execute_write_text_artifact(request: Any) -> dict[str, Any]:
    """Execute one bounded `write_text_artifact` request.

    The execution root is intentionally not included in the receipt so the
    receipt stays deterministic across isolated local test workspaces.
    """

    if not _is_mapping(request):
        return _reject(EXECUTOR_REQUEST_MALFORMED)
    request_map = dict(request)

    if FORBIDDEN_REQUEST_FIELDS & set(request_map):
        return _reject(EXECUTOR_FORBIDDEN_FIELD)
    if request_map.get("action") != "write_text_artifact":
        return _reject(EXECUTOR_ACTION_NOT_ALLOWED)

    descriptor_payload = request_map.get("descriptor_payload")
    if not _is_mapping(descriptor_payload):
        return _reject(EXECUTOR_REQUEST_MALFORMED)
    descriptor_hash = compute_descriptor_payload_hash(descriptor_payload)
    if request_map.get("descriptor_hash") != descriptor_hash:
        return _reject(EXECUTOR_DESCRIPTOR_HASH_MISMATCH)
    if request_map.get("task_id") != _task_id(descriptor_payload):
        return _reject(EXECUTOR_REQUEST_MALFORMED)

    authority_packet = request_map.get("authority_packet")
    if not _is_mapping(authority_packet):
        return _reject(EXECUTOR_AUTHORITY_PACKET_REQUIRED)
    authority_result = verify_authority_packet(authority_packet, descriptor_payload)
    if not authority_result.get("accepted", False):
        return _base_result(
            accepted=False,
            status="rejected",
            rejection_codes=list(authority_result.get("rejection_codes", [])) or [EXECUTOR_AUTHORITY_PACKET_REQUIRED],
        )

    workspace_receipt = request_map.get("workspace_transaction_receipt")
    if not _is_mapping(workspace_receipt):
        return _reject(EXECUTOR_WORKSPACE_TRANSACTION_RECEIPT_REQUIRED)
    if not verify_workspace_transaction_receipt(workspace_receipt):
        return _reject(EXECUTOR_WORKSPACE_TRANSACTION_RECEIPT_INVALID)
    workspace_mismatch = _workspace_receipt_mismatch(request_map, workspace_receipt)
    if workspace_mismatch:
        return _reject(workspace_mismatch)
    if workspace_receipt.get("authority_receipt_hash") != authority_packet.get("payload_hash"):
        return _reject(EXECUTOR_WORKSPACE_TRANSACTION_RECEIPT_MISMATCH)

    output_path = _required_string(request_map, "output_path")
    content = _required_string(request_map, "content")
    workspace_root = _required_string(request_map, "workspace_root")
    if output_path is None or content is None or workspace_root is None:
        return _reject(EXECUTOR_REQUEST_MALFORMED)

    path_error = _output_path_error(output_path, workspace_receipt)
    if path_error:
        return _reject(path_error)

    artifact_receipt = request_map.get("artifact_receipt")
    if not _is_mapping(artifact_receipt):
        return _reject(EXECUTOR_ARTIFACT_RECEIPT_REQUIRED)
    if not verify_artifact_receipt(artifact_receipt):
        return _reject(EXECUTOR_ARTIFACT_RECEIPT_INVALID)
    artifact_mismatch = _artifact_receipt_mismatch(request_map, artifact_receipt)
    if artifact_mismatch:
        return _reject(artifact_mismatch)

    expected_content_hash = _required_string(request_map, "expected_content_hash")
    if expected_content_hash is None or expected_content_hash != _sha256_text(content):
        return _reject(EXECUTOR_CONTENT_HASH_MISMATCH)

    root = Path(workspace_root)
    target = root / PurePosixPath(output_path)
    root_resolved = root.resolve(strict=False)
    target_parent = target.parent
    target_resolved = target.resolve(strict=False)
    if root_resolved != target_resolved and root_resolved not in target_resolved.parents:
        return _reject(EXECUTOR_OUTPUT_PATH_OUTSIDE_WORKSPACE)

    target_parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")

    receipt = _executor_receipt(request_map)
    return _base_result(
        accepted=True,
        status="executed",
        rejection_codes=[],
        receipt=receipt,
        artifact_write_performed=True,
    )
