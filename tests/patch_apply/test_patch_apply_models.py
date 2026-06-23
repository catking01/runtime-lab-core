from __future__ import annotations

from runtime_lab.patch_apply.models import (
    PatchApplyApprovalPacket,
    PatchApplyPolicy,
    PatchApplyRequest,
    PatchApplyResult,
)


def test_patch_apply_models_preserve_r126_non_claim_flags():
    approval = PatchApplyApprovalPacket(
        approval_id="R126-APPROVAL-001",
        proposal_id="R125-PROP-001",
        proposal_hash="sha256:proposal",
        approved_unified_diff_hash="sha256:diff",
        base_commit="96c186c1f6128239e73bba4610e1a8885eba6e6a",
        approved_target_files=("docs/example.md",),
        approved_by_actor_id="human:catking",
        approval_expires_at_utc="2999-01-01T00:00:00Z",
        authority_scope="single_patch_apply_transaction",
        workspace_root_hash="sha256:workspace",
        max_files_allowed=1,
        max_bytes_allowed=200_000,
        rollback_required=True,
        human_confirmation_text="I approve proposal R125-PROP-001 for this bounded patch apply transaction.",
        approval_nonce="nonce",
        approval_signature_or_local_attestation="local-attestation",
    )
    request = PatchApplyRequest(
        transaction_id="R126-TX-001",
        proposal_id="R125-PROP-001",
        base_commit="96c186c1f6128239e73bba4610e1a8885eba6e6a",
        target_files=("docs/example.md",),
    )
    result = PatchApplyResult()
    policy = PatchApplyPolicy(max_files_allowed=1, max_bytes_allowed=200_000)

    assert approval.rollback_required is True
    assert request.tests_run is False
    assert result.apply_performed is False
    assert result.workspace_mutation_performed is False
    assert result.tests_run is False
    assert result.llm_invocation_performed is False
    assert result.executor_dispatch_performed is False
    assert policy.allow_new_files is False
    assert policy.allow_delete_files is False
