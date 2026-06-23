from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any


MILESTONE = "R124_READ_ONLY_REPO_CONTEXT_EXECUTOR_LOCAL_VALIDATION"


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_hash(value: Any) -> str:
    return sha256_text(stable_json(value))


def _receipt_hash_payload(receipt: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(receipt)
    payload.pop("receipt_hash", None)
    return payload


def build_repo_context_receipt(
    *,
    executor_id: str,
    workspace_root: str,
    requested_path: str | None,
    resolved_path_relative: str | None,
    path_allowed: bool,
    bytes_read: int = 0,
    content_hash: str | None = None,
    redaction_applied: bool = False,
    result: str,
    rejection_codes: list[str] | None = None,
) -> dict[str, Any]:
    receipt = {
        "schema_version": "repo_context_receipt.v1",
        "receipt_type": "READ_ONLY_REPO_CONTEXT_RECEIPT",
        "milestone": MILESTONE,
        "executor_id": executor_id,
        "workspace_root_hash": sha256_text(workspace_root),
        "requested_path": requested_path,
        "resolved_path_relative": resolved_path_relative,
        "path_allowed": path_allowed,
        "read_only": True,
        "bytes_read": int(bytes_read),
        "content_hash": content_hash or canonical_hash(None),
        "content_recorded": False,
        "redaction_applied": bool(redaction_applied),
        "result": result,
        "rejection_codes": rejection_codes or [],
        "non_claims": {
            "file_mutation": False,
            "shell_execution": False,
            "network_execution": False,
            "llm_invocation": False,
            "agent_loop": False,
            "remote_sealed_pass": False,
        },
        "receipt_hash": "",
    }
    receipt["receipt_hash"] = canonical_hash(_receipt_hash_payload(receipt))
    return receipt


def verify_repo_context_receipt(receipt: Mapping[str, Any]) -> bool:
    if not isinstance(receipt, Mapping):
        return False
    provided = receipt.get("receipt_hash")
    return isinstance(provided, str) and provided.startswith("sha256:") and canonical_hash(
        _receipt_hash_payload(receipt)
    ) == provided
