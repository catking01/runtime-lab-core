from __future__ import annotations

from pathlib import Path

import pytest

from runtime_lab.patch_apply.approval import validate_approval_packet

from .conftest import make_approval, make_proposal, make_workspace, stable_hash


def test_validate_approval_packet_accepts_bound_human_approval(tmp_path: Path):
    workspace = make_workspace(tmp_path)
    proposal = make_proposal(workspace)
    approval = make_approval(workspace, proposal)

    result = validate_approval_packet(approval, proposal=proposal, workspace_root=workspace)

    assert result["accepted"] is True
    assert result["approval_verified"] is True
    assert result["proposal_hash"] == stable_hash(proposal)
    assert result["approval_hash"].startswith("sha256:")


@pytest.mark.parametrize(
    ("updates", "code"),
    [
        ({"approval_expires_at_utc": "2000-01-01T00:00:00Z"}, "APPROVAL_EXPIRED"),
        ({"proposal_hash": "sha256:not-the-proposal"}, "APPROVAL_PROPOSAL_HASH_MISMATCH"),
        ({"approved_unified_diff_hash": "sha256:not-the-diff"}, "APPROVAL_DIFF_HASH_MISMATCH"),
        ({"base_commit": "5fb1ee741bd986dadbb764622c03a0163168adc0"}, "APPROVAL_BASE_COMMIT_MISMATCH"),
        ({"approved_target_files": ["docs/other.md"]}, "APPROVAL_TARGET_FILES_MISMATCH"),
        ({"approved_target_files": ["*"]}, "APPROVAL_WILDCARD_TARGET_REJECTED"),
        ({"approved_by_actor_id": ""}, "APPROVAL_ACTOR_REQUIRED"),
        ({"authority_scope": "apply_any_patch"}, "APPROVAL_SCOPE_TOO_BROAD"),
        ({"apply_any_patch": True}, "APPROVAL_SCOPE_TOO_BROAD"),
        ({"rollback_required": False}, "APPROVAL_ROLLBACK_REQUIRED"),
        ({"human_confirmation_text": "approved"}, "APPROVAL_CONFIRMATION_TEXT_REJECTED"),
        ({"approval_nonce": ""}, "APPROVAL_NONCE_REQUIRED"),
        ({"approval_signature_or_local_attestation": ""}, "APPROVAL_ATTESTATION_REQUIRED"),
    ],
)
def test_validate_approval_packet_rejects_unbound_or_broad_approval(
    tmp_path: Path,
    updates: dict,
    code: str,
):
    workspace = make_workspace(tmp_path)
    proposal = make_proposal(workspace)
    approval = make_approval(workspace, proposal, **updates)

    result = validate_approval_packet(approval, proposal=proposal, workspace_root=workspace)

    assert result["accepted"] is False
    assert code in result["rejection_codes"]
    assert result["approval_verified"] is False
