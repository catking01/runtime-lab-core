from __future__ import annotations

from runtime_lab.patch_proposal.models import PatchProposalRequest


def test_patch_proposal_request_preserves_artifact_only_flags():
    request = PatchProposalRequest(
        proposal_id="R125-PROP-001",
        base_commit="5fb1ee741bd986dadbb764622c03a0163168adc0",
        target_files=("docs/example.md",),
        unified_diff="--- a/docs/example.md\n+++ b/docs/example.md\n@@ -1 +1 @@\n-old\n+new\n",
        risk_class="LOW",
        change_summary="Update example text.",
        validation_plan=("review artifact",),
        rollback_plan="Do not apply this proposal.",
    )

    assert request.human_approval_required is True
    assert request.apply_allowed is False
    assert request.apply_performed is False
    assert request.workspace_mutation_performed is False
    assert request.test_execution_allowed is False
    assert request.test_execution_performed is False
