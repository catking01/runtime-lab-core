"""Patch proposal artifact creation for R125.

The artifact path records a proposed diff and validation plan without applying
the patch, running tests, invoking models, or mutating the target workspace.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from runtime_lab.patch_proposal.policy import PatchProposalPolicy, validate_patch_proposal_request
from runtime_lab.patch_proposal.receipts import build_patch_proposal_receipt, canonical_hash


SECRET_LIKE_RE = re.compile(r"(sk-[A-Za-z0-9_-]{20,}|gho_[A-Za-z0-9_]{20,}|Authorization:\s*Bearer\s+\S+)")


def _redact(value: str, enabled: bool) -> tuple[str, bool]:
    if not enabled:
        return value, False
    redacted = SECRET_LIKE_RE.sub("<REDACTED_SECRET_LIKE_VALUE>", value)
    return redacted, redacted != value


def _ledger_event(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_type": "patch_proposal.artifact_created",
        "receipt_hash": receipt["receipt_hash"],
        "artifact_only": True,
        "apply_performed": False,
        "workspace_mutation_performed": False,
    }


def create_patch_proposal_artifact(
    request: Mapping[str, Any],
    *,
    workspace_root: Any,
    artifact_dir: Any,
    policy: PatchProposalPolicy | None = None,
) -> dict[str, Any]:
    """Validate and write one receipt-bound patch proposal artifact."""

    policy = policy or PatchProposalPolicy()
    validation = validate_patch_proposal_request(request, workspace_root=workspace_root, policy=policy)
    if not validation["accepted"]:
        return validation

    artifact_root = Path(artifact_dir)
    artifact_root.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_root / f"{validation['proposal_id']}.json"
    redacted_diff, redaction_applied = _redact(str(request["unified_diff"]), policy.redact_secret_like_patterns)
    artifact = {
        "schema_version": "1.0",
        "proposal_version": "patch_proposal.v0",
        "milestone": "R125_PATCH_PROPOSAL_ARTIFACT_ONLY_LOCAL_VALIDATION",
        "proposal_id": validation["proposal_id"],
        "base_commit": validation["base_commit"],
        "workspace_root_hash": canonical_hash(str(Path(workspace_root).resolve())),
        "target_files": validation["target_files"],
        "target_file_hashes": validation["target_file_hashes"],
        "target_file_hashes_recorded": validation["target_file_hashes_recorded"],
        "unified_diff": redacted_diff,
        "unified_diff_hash": validation["unified_diff_hash"],
        "risk_class": request["risk_class"],
        "change_summary": request["change_summary"],
        "validation_plan": list(request["validation_plan"]),
        "rollback_plan": request["rollback_plan"],
        "artifact_only": True,
        "human_approval_required": True,
        "apply_allowed": False,
        "apply_performed": False,
        "workspace_mutation_performed": False,
        "test_execution_allowed": False,
        "test_execution_performed": False,
        "non_claim_boundary": {
            "patch_application": False,
            "workspace_mutation": False,
            "shell_execution": False,
            "network_execution": False,
            "test_execution": False,
            "llm_invocation": False,
            "model_driven_executor_dispatch": False,
            "agent_loop": False,
            "remote_sealed_pass": False,
        },
    }
    artifact_hash = canonical_hash(artifact)
    receipt = build_patch_proposal_receipt(
        proposal_id=validation["proposal_id"],
        base_commit=validation["base_commit"],
        workspace_root=str(Path(workspace_root).resolve()),
        target_files=validation["target_files"],
        target_file_hashes_recorded=validation["target_file_hashes_recorded"],
        unified_diff_hash=validation["unified_diff_hash"],
        artifact_path=str(artifact_path),
        artifact_hash=artifact_hash,
        redaction_applied=redaction_applied,
        result="SUCCESS",
    )
    artifact["receipt"] = receipt
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = dict(validation)
    result.update(
        {
            "artifact_path": str(artifact_path),
            "artifact_hash": artifact_hash,
            "receipt": receipt,
            "ledger_event": _ledger_event(receipt),
            "redaction_applied": redaction_applied,
        }
    )
    return result
