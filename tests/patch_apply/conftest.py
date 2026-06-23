from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


BASE_COMMIT = "96c186c1f6128239e73bba4610e1a8885eba6e6a"
VALID_CONFIRMATION = "I approve proposal R125-PROP-001 for this bounded patch apply transaction."


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def stable_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def make_workspace(tmp_path: Path, files: dict[str, str] | None = None) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    for relative_path, text in (files or {"docs/example.md": "old\n"}).items():
        path = workspace / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return workspace


def make_diff(path: str = "docs/example.md", old: str = "old", new: str = "new") -> str:
    return f"--- a/{path}\n+++ b/{path}\n@@ -1 +1 @@\n-{old}\n+{new}\n"


def make_proposal(
    workspace: Path,
    *,
    proposal_id: str = "R125-PROP-001",
    target_files: list[str] | None = None,
    unified_diff: str | None = None,
    base_commit: str = BASE_COMMIT,
    **updates: Any,
) -> dict[str, Any]:
    targets = target_files or ["docs/example.md"]
    diff = unified_diff or make_diff(targets[0])
    proposal = {
        "schema_version": "1.0",
        "proposal_version": "patch_proposal.v0",
        "milestone": "R125_PATCH_PROPOSAL_ARTIFACT_ONLY_LOCAL_VALIDATION",
        "proposal_id": proposal_id,
        "base_commit": base_commit,
        "workspace_root_hash": stable_hash(str(workspace.resolve())),
        "target_files": targets,
        "target_file_hashes": {
            target: sha256_bytes((workspace / target).read_bytes())
            for target in targets
            if (workspace / target).exists()
        },
        "target_file_hashes_recorded": True,
        "unified_diff": diff,
        "unified_diff_hash": stable_hash(diff),
        "risk_class": "LOW",
        "change_summary": "Update example text.",
        "validation_plan": ["review patch apply receipt"],
        "rollback_plan": "Restore preimage from rollback artifact.",
        "artifact_only": True,
        "human_approval_required": True,
        "apply_allowed": False,
        "apply_performed": False,
        "workspace_mutation_performed": False,
        "test_execution_allowed": False,
        "test_execution_performed": False,
        "llm_invocation_requested": False,
        "executor_dispatch_requested": False,
    }
    proposal.update(updates)
    return proposal


def make_approval(workspace: Path, proposal: dict[str, Any], **updates: Any) -> dict[str, Any]:
    approval = {
        "approval_id": "R126-APPROVAL-001",
        "approval_version": "patch_apply_approval.v1",
        "approved_by_actor_id": "human:catking",
        "approval_created_at_utc": "2026-06-20T12:00:00Z",
        "approval_expires_at_utc": "2999-01-01T00:00:00Z",
        "proposal_id": proposal["proposal_id"],
        "proposal_hash": stable_hash(proposal),
        "base_commit": proposal["base_commit"],
        "approved_target_files": list(proposal["target_files"]),
        "approved_unified_diff_hash": proposal["unified_diff_hash"],
        "approved_risk_class": proposal["risk_class"],
        "authority_scope": "single_patch_apply_transaction",
        "workspace_root_hash": stable_hash(str(workspace.resolve())),
        "max_files_allowed": len(proposal["target_files"]),
        "max_bytes_allowed": 200_000,
        "rollback_required": True,
        "human_confirmation_text": VALID_CONFIRMATION,
        "approval_nonce": "r126-nonce-001",
        "approval_signature_or_local_attestation": "local-human-attestation",
    }
    approval.update(updates)
    return approval


def make_request(
    workspace: Path,
    *,
    proposal: dict[str, Any] | None = None,
    approval: dict[str, Any] | None = None,
    transaction_id: str = "R126-TX-001",
    **updates: Any,
) -> dict[str, Any]:
    proposal = proposal or make_proposal(workspace)
    approval = approval or make_approval(workspace, proposal)
    request = {
        "transaction_id": transaction_id,
        "base_commit": BASE_COMMIT,
        "proposal": proposal,
        "approval_packet": approval,
        "receipt_required": True,
        "ledger_event_required": True,
        "tests_run": False,
        "llm_invocation_requested": False,
        "executor_dispatch_requested": False,
        "shell_execution_requested": False,
        "network_execution_requested": False,
    }
    request.update(updates)
    return request
