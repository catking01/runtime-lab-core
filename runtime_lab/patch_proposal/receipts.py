from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any


MILESTONE = "R125_PATCH_PROPOSAL_ARTIFACT_ONLY_LOCAL_VALIDATION"


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def canonical_hash(value: Any) -> str:
    return sha256_text(stable_json(value))


def _receipt_hash_payload(receipt: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(receipt)
    payload.pop("receipt_hash", None)
    return payload


def build_patch_proposal_receipt(
    *,
    proposal_id: str,
    base_commit: str,
    workspace_root: str,
    target_files: list[str],
    target_file_hashes_recorded: bool,
    unified_diff_hash: str,
    artifact_path: str,
    artifact_hash: str,
    redaction_applied: bool,
    result: str,
    rejection_codes: list[str] | None = None,
) -> dict[str, Any]:
    receipt = {
        "schema_version": "patch_proposal_receipt.v1",
        "receipt_type": "PATCH_PROPOSAL_ARTIFACT_RECEIPT",
        "milestone": MILESTONE,
        "proposal_id": proposal_id,
        "base_commit": base_commit,
        "workspace_root_hash": sha256_text(workspace_root),
        "target_files": target_files,
        "target_file_hashes_recorded": target_file_hashes_recorded,
        "unified_diff_hash": unified_diff_hash,
        "artifact_path": artifact_path,
        "artifact_hash": artifact_hash,
        "redaction_applied": redaction_applied,
        "apply_allowed": False,
        "apply_performed": False,
        "workspace_mutation_performed": False,
        "test_execution_performed": False,
        "human_approval_required": True,
        "result": result,
        "rejection_codes": rejection_codes or [],
        "non_claims": {
            "patch_application": False,
            "workspace_mutation": False,
            "shell_execution": False,
            "test_execution": False,
            "llm_invocation": False,
            "agent_loop": False,
            "remote_sealed_pass": False,
        },
        "receipt_hash": "",
    }
    receipt["receipt_hash"] = canonical_hash(_receipt_hash_payload(receipt))
    return receipt


def verify_patch_proposal_receipt(receipt: Mapping[str, Any]) -> bool:
    if not isinstance(receipt, Mapping):
        return False
    provided = receipt.get("receipt_hash")
    return isinstance(provided, str) and provided.startswith("sha256:") and canonical_hash(
        _receipt_hash_payload(receipt)
    ) == provided
