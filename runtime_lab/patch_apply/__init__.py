from __future__ import annotations

from runtime_lab.patch_apply.approval import validate_approval_packet
from runtime_lab.patch_apply.diff_apply import apply_unified_diff_to_text, parse_unified_diff
from runtime_lab.patch_apply.models import PatchApplyApprovalPacket, PatchApplyPolicy, PatchApplyRequest, PatchApplyResult
from runtime_lab.patch_apply.policy import validate_patch_apply_request
from runtime_lab.patch_apply.receipts import verify_patch_apply_receipt, verify_rollback_artifact
from runtime_lab.patch_apply.rollback import build_rollback_artifact, restore_rollback_artifact
from runtime_lab.patch_apply.transaction import apply_patch_transaction

__all__ = [
    "PatchApplyApprovalPacket",
    "PatchApplyPolicy",
    "PatchApplyRequest",
    "PatchApplyResult",
    "apply_patch_transaction",
    "apply_unified_diff_to_text",
    "build_rollback_artifact",
    "parse_unified_diff",
    "restore_rollback_artifact",
    "validate_approval_packet",
    "validate_patch_apply_request",
    "verify_patch_apply_receipt",
    "verify_rollback_artifact",
]
