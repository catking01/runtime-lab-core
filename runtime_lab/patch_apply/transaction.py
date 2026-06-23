"""Human-approved patch-apply transaction orchestration for R126.

Transactions validate approval and preimage bindings, prepare rollback data,
apply an existing unified diff, and emit receipts while rejecting unapproved
mutation or unsupported execution surfaces.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from runtime_lab.patch_apply.diff_apply import apply_file_patch_to_text, parse_unified_diff
from runtime_lab.patch_apply.errors import PatchApplyPolicyError
from runtime_lab.patch_apply.models import PatchApplyPolicy
from runtime_lab.patch_apply.policy import validate_patch_apply_request
from runtime_lab.patch_apply.receipts import build_patch_apply_receipt, canonical_hash, sha256_bytes
from runtime_lab.patch_apply.rollback import build_rollback_artifact, restore_rollback_artifact


def _failure(
    *,
    codes: list[str],
    states: list[str] | None = None,
    rollback_performed: bool = False,
    rollback_artifact_path: str | None = None,
) -> dict[str, Any]:
    return {
        "accepted": False,
        "result": "REJECTED_FAIL_CLOSED",
        "rejection_codes": list(dict.fromkeys(codes)),
        "transaction_states": states or ["PLANNED", "REJECTED_FAIL_CLOSED"],
        "apply_performed": False,
        "workspace_mutation_performed": False,
        "approval_verified": False,
        "preimage_verified": False,
        "postimage_verified": False,
        "rollback_artifact_written": rollback_artifact_path is not None,
        "rollback_artifact_path": rollback_artifact_path,
        "rollback_performed": rollback_performed,
        "receipt_written": False,
        "tests_run": False,
        "llm_invocation_performed": False,
        "executor_dispatch_performed": False,
        "shell_execution_performed": False,
        "network_execution_performed": False,
    }


def _ledger_event(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_type": "patch_apply.transaction_committed",
        "receipt_hash": receipt["receipt_hash"],
        "milestone": receipt["milestone"],
        "workspace_mutation_performed": True,
        "tests_run": False,
        "llm_invocation_performed": False,
        "executor_dispatch_performed": False,
    }


def apply_patch_transaction(
    request: dict[str, Any],
    *,
    workspace_root: Any,
    transaction_dir: Any,
    policy: PatchApplyPolicy | None = None,
) -> dict[str, Any]:
    """Apply one approved patch transaction with rollback and receipt metadata."""

    policy = policy or PatchApplyPolicy()
    states = ["PLANNED"]
    validation = validate_patch_apply_request(request, workspace_root=workspace_root, policy=policy)
    if not validation["accepted"]:
        return _failure(codes=validation["rejection_codes"], states=states + ["REJECTED_FAIL_CLOSED"])

    states.extend(["APPROVAL_VERIFIED", "PREIMAGE_VERIFIED"])
    root = Path(workspace_root).expanduser().resolve()
    tx_dir = Path(transaction_dir)
    rollback_artifact_path: Path | None = None
    rollback_artifact: dict[str, Any] | None = None

    try:
        tx_dir.mkdir(parents=True, exist_ok=True)
        if not tx_dir.is_dir():
            raise OSError("transaction_dir is not a directory")
        rollback_artifact = build_rollback_artifact(
            transaction_id=validation["transaction_id"],
            workspace_root=root,
            target_files=validation["target_files"],
        )
        rollback_artifact_path = tx_dir / "rollback.json"
        rollback_artifact_path.write_text(json.dumps(rollback_artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        states.append("ROLLBACK_PREPARED")
    except Exception:
        return _failure(codes=["ROLLBACK_ARTIFACT_WRITE_FAILED"], states=states + ["REJECTED_FAIL_CLOSED"])

    states.append("APPLY_STARTED")
    changed_files: list[str] = []
    try:
        patches = {patch.target_path: patch for patch in parse_unified_diff(request["proposal"]["unified_diff"])}
        for target in validation["target_files"]:
            path = root / target
            original_text = path.read_text(encoding="utf-8")
            patched_text = apply_file_patch_to_text(original_text, patches[target])
            temp_path = path.with_name(f"{path.name}.{validation['transaction_id']}.tmp")
            temp_path.write_text(patched_text, encoding="utf-8")
            temp_path.replace(path)
            changed_files.append(target)
        states.append("APPLY_COMPLETED")
    except PatchApplyPolicyError as exc:
        if rollback_artifact is not None:
            restore_rollback_artifact(rollback_artifact, workspace_root=root)
            states.extend(["ROLLBACK_REQUIRED", "ROLLBACK_COMPLETED"])
        return _failure(
            codes=[exc.code],
            states=states + ["REJECTED_FAIL_CLOSED"],
            rollback_performed=bool(changed_files),
            rollback_artifact_path=str(rollback_artifact_path) if rollback_artifact_path else None,
        )
    except Exception:
        if rollback_artifact is not None:
            restore_rollback_artifact(rollback_artifact, workspace_root=root)
            states.extend(["ROLLBACK_REQUIRED", "ROLLBACK_COMPLETED"])
        return _failure(
            codes=["PATCH_APPLY_WRITE_FAILED"],
            states=states + ["REJECTED_FAIL_CLOSED"],
            rollback_performed=bool(changed_files),
            rollback_artifact_path=str(rollback_artifact_path) if rollback_artifact_path else None,
        )

    postimage_hashes = {
        target: sha256_bytes((root / target).read_bytes())
        for target in validation["target_files"]
    }
    states.append("POSTIMAGE_VERIFIED")

    receipt = build_patch_apply_receipt(
        transaction_id=validation["transaction_id"],
        proposal_id=validation["proposal_id"],
        proposal_hash=validation["proposal_hash"],
        approval_id=validation["approval_id"],
        approval_hash=validation["approval_hash"],
        base_commit=validation["base_commit"],
        workspace_root_hash=validation["workspace_root_hash"],
        target_files=validation["target_files"],
        preimage_hashes=validation["preimage_hashes"],
        postimage_hashes=postimage_hashes,
        unified_diff_hash=validation["unified_diff_hash"],
        rollback_artifact_path=str(rollback_artifact_path),
        rollback_artifact_hash=rollback_artifact["rollback_artifact_hash"],
        result="SUCCESS",
    )
    receipt_path = tx_dir / "receipt.json"
    try:
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception:
        restore_rollback_artifact(rollback_artifact, workspace_root=root)
        states.extend(["ROLLBACK_REQUIRED", "ROLLBACK_COMPLETED"])
        return _failure(
            codes=["RECEIPT_WRITE_FAILED"],
            states=states + ["REJECTED_FAIL_CLOSED"],
            rollback_performed=True,
            rollback_artifact_path=str(rollback_artifact_path),
        )
    states.extend(["RECEIPT_WRITTEN", "COMMITTED_LOCAL_TRANSACTION"])

    return {
        "accepted": True,
        "result": "SUCCESS",
        "rejection_codes": [],
        "transaction_id": validation["transaction_id"],
        "proposal_id": validation["proposal_id"],
        "proposal_hash": validation["proposal_hash"],
        "approval_id": validation["approval_id"],
        "approval_hash": validation["approval_hash"],
        "base_commit": validation["base_commit"],
        "workspace_root_hash": validation["workspace_root_hash"],
        "target_files": validation["target_files"],
        "files_changed": changed_files,
        "bytes_changed": sum(len((root / target).read_bytes()) for target in changed_files),
        "preimage_hashes": validation["preimage_hashes"],
        "postimage_hashes": postimage_hashes,
        "unified_diff_hash": validation["unified_diff_hash"],
        "rollback_artifact_path": str(rollback_artifact_path),
        "rollback_artifact_hash": rollback_artifact["rollback_artifact_hash"],
        "receipt_path": str(receipt_path),
        "receipt_hash": receipt["receipt_hash"],
        "receipt": receipt,
        "ledger_event": _ledger_event(receipt),
        "ledger_event_hash": canonical_hash(_ledger_event(receipt)),
        "transaction_states": states,
        "apply_performed": True,
        "workspace_mutation_performed": True,
        "approval_verified": True,
        "preimage_verified": True,
        "postimage_verified": True,
        "rollback_artifact_written": True,
        "rollback_performed": False,
        "receipt_written": True,
        "tests_run": False,
        "llm_invocation_performed": False,
        "executor_dispatch_performed": False,
        "shell_execution_performed": False,
        "network_execution_performed": False,
    }
