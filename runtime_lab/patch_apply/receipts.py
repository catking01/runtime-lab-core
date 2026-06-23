from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any


MILESTONE = "R126_HUMAN_APPROVED_PATCH_APPLY_TRANSACTION_LOCAL_VALIDATION"


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def canonical_hash(value: Any) -> str:
    return sha256_text(stable_json(value))


def _hash_payload(value: Mapping[str, Any], hash_field: str) -> dict[str, Any]:
    payload = dict(value)
    payload.pop(hash_field, None)
    return payload


def build_patch_apply_receipt(
    *,
    transaction_id: str,
    proposal_id: str,
    proposal_hash: str,
    approval_id: str,
    approval_hash: str,
    base_commit: str,
    workspace_root_hash: str,
    target_files: list[str],
    preimage_hashes: dict[str, str],
    postimage_hashes: dict[str, str],
    unified_diff_hash: str,
    rollback_artifact_path: str,
    rollback_artifact_hash: str,
    result: str,
) -> dict[str, Any]:
    receipt = {
        "schema_version": "1.0",
        "receipt_type": "HUMAN_APPROVED_PATCH_APPLY_TRANSACTION_RECEIPT",
        "milestone": MILESTONE,
        "transaction_id": transaction_id,
        "proposal_id": proposal_id,
        "proposal_hash": proposal_hash,
        "approval_id": approval_id,
        "approval_hash": approval_hash,
        "base_commit": base_commit,
        "workspace_root_hash": workspace_root_hash,
        "target_files": target_files,
        "preimage_hashes": preimage_hashes,
        "postimage_hashes": postimage_hashes,
        "unified_diff_hash": unified_diff_hash,
        "rollback_artifact_path": rollback_artifact_path,
        "rollback_artifact_hash": rollback_artifact_hash,
        "apply_performed": True,
        "workspace_mutation_performed": True,
        "human_approval_required": True,
        "human_approval_verified": True,
        "tests_run": False,
        "llm_invocation_performed": False,
        "executor_dispatch_performed": False,
        "shell_execution_performed": False,
        "network_execution_performed": False,
        "result": result,
        "non_claims": {
            "autonomous_patching": False,
            "test_execution": False,
            "llm_runtime": False,
            "agent_loop": False,
            "production_ready": False,
            "remote_sealed_pass": False,
        },
        "receipt_hash": "",
    }
    receipt["receipt_hash"] = canonical_hash(_hash_payload(receipt, "receipt_hash"))
    return receipt


def verify_patch_apply_receipt(receipt: Mapping[str, Any]) -> bool:
    if not isinstance(receipt, Mapping):
        return False
    provided = receipt.get("receipt_hash")
    return isinstance(provided, str) and provided.startswith("sha256:") and canonical_hash(
        _hash_payload(receipt, "receipt_hash")
    ) == provided


def seal_rollback_artifact(artifact: Mapping[str, Any]) -> dict[str, Any]:
    sealed = dict(artifact)
    sealed["rollback_artifact_hash"] = ""
    sealed["rollback_artifact_hash"] = canonical_hash(_hash_payload(sealed, "rollback_artifact_hash"))
    return sealed


def verify_rollback_artifact(artifact: Mapping[str, Any]) -> bool:
    if not isinstance(artifact, Mapping):
        return False
    provided = artifact.get("rollback_artifact_hash")
    return isinstance(provided, str) and provided.startswith("sha256:") and canonical_hash(
        _hash_payload(artifact, "rollback_artifact_hash")
    ) == provided
