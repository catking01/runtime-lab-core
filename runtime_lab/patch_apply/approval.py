from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from runtime_lab.patch_apply.receipts import canonical_hash


REQUIRED_APPROVAL_FIELDS = (
    "approval_id",
    "approval_version",
    "approved_by_actor_id",
    "approval_created_at_utc",
    "approval_expires_at_utc",
    "proposal_id",
    "proposal_hash",
    "base_commit",
    "approved_target_files",
    "approved_unified_diff_hash",
    "approved_risk_class",
    "authority_scope",
    "workspace_root_hash",
    "max_files_allowed",
    "max_bytes_allowed",
    "human_confirmation_text",
    "approval_nonce",
    "approval_signature_or_local_attestation",
)

WEAK_CONFIRMATIONS = {"yes", "approved", "apply all", "let the model decide"}


def _base_result(*, accepted: bool, rejection_codes: list[str] | None = None) -> dict[str, Any]:
    return {
        "accepted": accepted,
        "rejection_codes": list(dict.fromkeys(rejection_codes or [])),
        "approval_verified": accepted,
        "apply_performed": False,
        "workspace_mutation_performed": False,
        "tests_run": False,
        "llm_invocation_performed": False,
        "executor_dispatch_performed": False,
    }


def _parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _string_list(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    if not all(isinstance(item, str) and item for item in value):
        return None
    return list(value)


def validate_approval_packet(
    approval_packet: Any,
    *,
    proposal: Mapping[str, Any],
    workspace_root: Any,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    if not isinstance(approval_packet, Mapping):
        return _base_result(accepted=False, rejection_codes=["APPROVAL_PACKET_REQUIRED"])
    if not isinstance(proposal, Mapping):
        return _base_result(accepted=False, rejection_codes=["PROPOSAL_REQUIRED"])

    approval = dict(approval_packet)
    errors: list[str] = []
    for field in REQUIRED_APPROVAL_FIELDS:
        if field not in approval:
            errors.append("APPROVAL_REQUIRED_FIELD_MISSING")

    proposal_hash = canonical_hash(dict(proposal))
    approval_hash = canonical_hash(approval)
    proposal_id = proposal.get("proposal_id")
    target_files = list(proposal.get("target_files", [])) if isinstance(proposal.get("target_files"), list) else []
    workspace_hash = canonical_hash(str(Path(workspace_root).expanduser().resolve()))

    expires_at = _parse_utc(approval.get("approval_expires_at_utc"))
    if expires_at is None:
        errors.append("APPROVAL_EXPIRATION_REQUIRED")
    elif expires_at <= (now_utc or datetime.now(UTC)):
        errors.append("APPROVAL_EXPIRED")

    if not approval.get("approved_by_actor_id"):
        errors.append("APPROVAL_ACTOR_REQUIRED")
    if approval.get("proposal_id") != proposal_id:
        errors.append("APPROVAL_PROPOSAL_ID_MISMATCH")
    if approval.get("proposal_hash") != proposal_hash:
        errors.append("APPROVAL_PROPOSAL_HASH_MISMATCH")
    if approval.get("approved_unified_diff_hash") != proposal.get("unified_diff_hash"):
        errors.append("APPROVAL_DIFF_HASH_MISMATCH")
    if approval.get("base_commit") != proposal.get("base_commit"):
        errors.append("APPROVAL_BASE_COMMIT_MISMATCH")
    if approval.get("approved_risk_class") != proposal.get("risk_class"):
        errors.append("APPROVAL_RISK_CLASS_MISMATCH")
    if approval.get("workspace_root_hash") != workspace_hash:
        errors.append("APPROVAL_WORKSPACE_HASH_MISMATCH")

    approved_targets = _string_list(approval.get("approved_target_files"))
    if not approved_targets:
        errors.append("APPROVAL_TARGET_FILES_REQUIRED")
        approved_targets = []
    if any("*" in target for target in approved_targets):
        errors.append("APPROVAL_WILDCARD_TARGET_REJECTED")
    if approved_targets != target_files:
        errors.append("APPROVAL_TARGET_FILES_MISMATCH")

    authority_scope = approval.get("authority_scope")
    if authority_scope != "single_patch_apply_transaction" or approval.get("apply_any_patch"):
        errors.append("APPROVAL_SCOPE_TOO_BROAD")
    if approval.get("rollback_required") is not True:
        errors.append("APPROVAL_ROLLBACK_REQUIRED")
    if not isinstance(approval.get("max_files_allowed"), int) or approval.get("max_files_allowed", 0) < len(target_files):
        errors.append("APPROVAL_MAX_FILES_EXCEEDED")
    if not isinstance(approval.get("max_bytes_allowed"), int) or approval.get("max_bytes_allowed", 0) <= 0:
        errors.append("APPROVAL_MAX_BYTES_REQUIRED")

    confirmation = str(approval.get("human_confirmation_text", "")).strip()
    if confirmation.lower() in WEAK_CONFIRMATIONS or str(proposal_id) not in confirmation:
        errors.append("APPROVAL_CONFIRMATION_TEXT_REJECTED")
    if not approval.get("approval_nonce"):
        errors.append("APPROVAL_NONCE_REQUIRED")
    if not approval.get("approval_signature_or_local_attestation"):
        errors.append("APPROVAL_ATTESTATION_REQUIRED")

    if errors:
        return _base_result(accepted=False, rejection_codes=errors)

    result = _base_result(accepted=True)
    result.update(
        {
            "approval_id": approval["approval_id"],
            "approval_hash": approval_hash,
            "proposal_hash": proposal_hash,
            "approved_target_files": approved_targets,
            "workspace_root_hash": workspace_hash,
        }
    )
    return result
