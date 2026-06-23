"""Workspace transaction planning for R115.

R115 prepares deterministic workspace transaction receipts. It intentionally
does not write artifacts, execute tools, invoke LLMs, or implement an artifact
store.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Any

from runtime_lab.authority.packet import compute_descriptor_payload_hash
from runtime_lab.authority.verify import verify_authority_packet
from runtime_lab.authority.canonical import canonical_hash

WORKSPACE_AUTHORITY_PACKET_REQUIRED = "WORKSPACE_AUTHORITY_PACKET_REQUIRED"
WORKSPACE_TRANSACTION_REQUEST_MALFORMED = "WORKSPACE_TRANSACTION_REQUEST_MALFORMED"
WORKSPACE_DESCRIPTOR_HASH_MISMATCH = "WORKSPACE_DESCRIPTOR_HASH_MISMATCH"
WORKSPACE_TASK_BINDING_MISMATCH = "WORKSPACE_TASK_BINDING_MISMATCH"
WORKSPACE_SCOPE_MISMATCH = "WORKSPACE_SCOPE_MISMATCH"
WORKSPACE_EMPTY_REQUEST_REJECTED = "WORKSPACE_EMPTY_REQUEST_REJECTED"
WORKSPACE_ABSOLUTE_PATH_REJECTED = "WORKSPACE_ABSOLUTE_PATH_REJECTED"
WORKSPACE_PATH_TRAVERSAL_REJECTED = "WORKSPACE_PATH_TRAVERSAL_REJECTED"
WORKSPACE_PATH_OUTSIDE_ALLOWED_ROOT = "WORKSPACE_PATH_OUTSIDE_ALLOWED_ROOT"
WORKSPACE_DENIED_PATH_REJECTED = "WORKSPACE_DENIED_PATH_REJECTED"
WORKSPACE_SYMLINK_ESCAPE_UNSUPPORTED = "WORKSPACE_SYMLINK_ESCAPE_UNSUPPORTED"


def _is_mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _strict_string_list(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    if not all(isinstance(item, str) for item in value):
        return None
    return list(value)


def _task_id(payload: Mapping[str, Any]) -> str:
    task_ref = payload.get("task_ref")
    if _is_mapping(task_ref):
        task_id = task_ref.get("task_id")
        if isinstance(task_id, str):
            return task_id
    return ""


def _packet_roots(packet: Mapping[str, Any]) -> list[str]:
    workspace = packet.get("workspace_binding")
    if _is_mapping(workspace):
        return sorted(_as_string_list(workspace.get("allowed_roots")))
    return []


def _normalize_path(path: str) -> str:
    return str(PurePosixPath(path))


def _has_traversal(path: str) -> bool:
    return any(part == ".." for part in PurePosixPath(path).parts)


def _path_within_root(path: str, root: str) -> bool:
    normalized_path = _normalize_path(path)
    normalized_root = _normalize_path(root)
    return normalized_path == normalized_root or normalized_path.startswith(f"{normalized_root}/")


def _workspace_scope_hash(allowed_roots: list[str], denied_paths: list[str]) -> str:
    return canonical_hash(
        {
            "allowed_roots": sorted(allowed_roots),
            "denied_paths": sorted(denied_paths),
        }
    )


def _receipt_hash_payload(receipt: Mapping[str, Any]) -> dict[str, Any]:
    candidate = dict(receipt)
    candidate.pop("transaction_hash", None)
    return candidate


def _make_receipt(
    *,
    request: Mapping[str, Any],
    payload: Mapping[str, Any],
    packet: Mapping[str, Any],
    requested_paths: list[str],
    allowed_roots: list[str],
    denied_paths: list[str],
    accepted: bool,
    status: str,
    rejection_codes: list[str],
) -> dict[str, Any]:
    receipt = {
        "schema_version": "workspace_transaction_receipt.v1",
        "transaction_id": request.get("transaction_id") if isinstance(request.get("transaction_id"), str) else "",
        "task_id": _task_id(payload),
        "descriptor_hash": compute_descriptor_payload_hash(payload),
        "authority_packet_id": packet.get("packet_id") if isinstance(packet.get("packet_id"), str) else None,
        "authority_packet_hash": packet.get("payload_hash") if isinstance(packet.get("payload_hash"), str) else None,
        "authority_receipt_hash": packet.get("payload_hash") if isinstance(packet.get("payload_hash"), str) else None,
        "workspace_scope_hash": _workspace_scope_hash(allowed_roots, denied_paths),
        "requested_paths": sorted(requested_paths),
        "allowed_roots": sorted(allowed_roots),
        "denied_paths": sorted(denied_paths),
        "accepted": bool(accepted),
        "status": status,
        "rejection_codes": list(dict.fromkeys(rejection_codes)),
        "artifact_write_performed": False,
        "tool_invocation_performed": False,
        "llm_invocation_performed": False,
        "transaction_hash": "",
    }
    receipt["transaction_hash"] = canonical_hash(_receipt_hash_payload(receipt))
    return receipt


def verify_workspace_transaction_receipt(receipt: Mapping[str, Any]) -> bool:
    """Verify a workspace transaction receipt hash deterministically."""

    if not _is_mapping(receipt):
        return False
    provided = receipt.get("transaction_hash")
    return isinstance(provided, str) and provided.startswith("sha256:") and canonical_hash(
        _receipt_hash_payload(receipt)
    ) == provided


def _result(
    *,
    request: Mapping[str, Any],
    payload: Mapping[str, Any],
    packet: Mapping[str, Any],
    requested_paths: list[str],
    allowed_roots: list[str],
    denied_paths: list[str],
    accepted: bool,
    status: str,
    rejection_codes: list[str],
) -> dict[str, Any]:
    receipt = _make_receipt(
        request=request,
        payload=payload,
        packet=packet,
        requested_paths=requested_paths,
        allowed_roots=allowed_roots,
        denied_paths=denied_paths,
        accepted=accepted,
        status=status,
        rejection_codes=rejection_codes,
    )
    return {
        "accepted": accepted,
        "status": status,
        "rejection_codes": receipt["rejection_codes"],
        "receipt": receipt,
        "artifact_write_performed": False,
        "tool_invocation_performed": False,
        "llm_invocation_performed": False,
    }


def _reject_without_receipt(code: str) -> dict[str, Any]:
    return {
        "accepted": False,
        "status": "rejected",
        "rejection_codes": [code],
        "receipt": None,
        "artifact_write_performed": False,
        "tool_invocation_performed": False,
        "llm_invocation_performed": False,
    }


def begin_workspace_transaction(request: Any, descriptor_payload: Mapping[str, Any], authority_packet: Any) -> dict[str, Any]:
    """Prepare a deterministic workspace transaction, fail-closed.

    This is a planning and receipt layer only. It never writes artifacts.
    """

    if not _is_mapping(request):
        return _reject_without_receipt(WORKSPACE_TRANSACTION_REQUEST_MALFORMED)
    if not _is_mapping(descriptor_payload):
        return _reject_without_receipt(WORKSPACE_TRANSACTION_REQUEST_MALFORMED)
    if authority_packet is None:
        return _reject_without_receipt(WORKSPACE_AUTHORITY_PACKET_REQUIRED)
    if not _is_mapping(authority_packet):
        return _reject_without_receipt(WORKSPACE_AUTHORITY_PACKET_REQUIRED)

    payload = dict(descriptor_payload)
    packet = dict(authority_packet)
    request_map = dict(request)
    requested_paths = _strict_string_list(request_map.get("requested_paths"))
    requested_roots = _strict_string_list(request_map.get("allowed_roots"))
    denied_paths = _strict_string_list(request_map.get("denied_paths"))
    if requested_paths is None or requested_roots is None or denied_paths is None:
        return _reject_without_receipt(WORKSPACE_TRANSACTION_REQUEST_MALFORMED)

    requested_roots = sorted(requested_roots)
    denied_paths = sorted(denied_paths)
    packet_roots = _packet_roots(packet)

    authority_result = verify_authority_packet(packet, payload)
    if not authority_result.get("accepted", False):
        return _result(
            request=request_map,
            payload=payload,
            packet=packet,
            requested_paths=requested_paths,
            allowed_roots=packet_roots,
            denied_paths=denied_paths,
            accepted=False,
            status="rejected",
            rejection_codes=list(authority_result.get("rejection_codes", [])),
        )

    descriptor_hash = compute_descriptor_payload_hash(payload)
    if request_map.get("descriptor_hash") != descriptor_hash:
        return _result(
            request=request_map,
            payload=payload,
            packet=packet,
            requested_paths=requested_paths,
            allowed_roots=packet_roots,
            denied_paths=denied_paths,
            accepted=False,
            status="rejected",
            rejection_codes=[WORKSPACE_DESCRIPTOR_HASH_MISMATCH],
        )

    if request_map.get("task_id") != _task_id(payload):
        return _result(
            request=request_map,
            payload=payload,
            packet=packet,
            requested_paths=requested_paths,
            allowed_roots=packet_roots,
            denied_paths=denied_paths,
            accepted=False,
            status="rejected",
            rejection_codes=[WORKSPACE_TASK_BINDING_MISMATCH],
        )

    if requested_roots != packet_roots:
        return _result(
            request=request_map,
            payload=payload,
            packet=packet,
            requested_paths=requested_paths,
            allowed_roots=packet_roots,
            denied_paths=denied_paths,
            accepted=False,
            status="rejected",
            rejection_codes=[WORKSPACE_SCOPE_MISMATCH],
        )

    if request_map.get("symlink_policy", "reject") != "reject":
        return _result(
            request=request_map,
            payload=payload,
            packet=packet,
            requested_paths=requested_paths,
            allowed_roots=packet_roots,
            denied_paths=denied_paths,
            accepted=False,
            status="rejected",
            rejection_codes=[WORKSPACE_SYMLINK_ESCAPE_UNSUPPORTED],
        )

    if not requested_paths:
        return _result(
            request=request_map,
            payload=payload,
            packet=packet,
            requested_paths=requested_paths,
            allowed_roots=packet_roots,
            denied_paths=denied_paths,
            accepted=False,
            status="rejected",
            rejection_codes=[WORKSPACE_EMPTY_REQUEST_REJECTED],
        )

    normalized_denied = {_normalize_path(path) for path in denied_paths}
    for path in requested_paths:
        if PurePosixPath(path).is_absolute():
            code = WORKSPACE_ABSOLUTE_PATH_REJECTED
        elif _has_traversal(path):
            code = WORKSPACE_PATH_TRAVERSAL_REJECTED
        elif _normalize_path(path) in normalized_denied:
            code = WORKSPACE_DENIED_PATH_REJECTED
        elif not any(_path_within_root(path, root) for root in packet_roots):
            code = WORKSPACE_PATH_OUTSIDE_ALLOWED_ROOT
        else:
            continue

        return _result(
            request=request_map,
            payload=payload,
            packet=packet,
            requested_paths=requested_paths,
            allowed_roots=packet_roots,
            denied_paths=denied_paths,
            accepted=False,
            status="rejected",
            rejection_codes=[code],
        )

    return _result(
        request=request_map,
        payload=payload,
        packet=packet,
        requested_paths=requested_paths,
        allowed_roots=packet_roots,
        denied_paths=denied_paths,
        accepted=True,
        status="prepared",
        rejection_codes=[],
    )
