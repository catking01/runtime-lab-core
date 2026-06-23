from __future__ import annotations

import copy
from pathlib import Path

from runtime_lab.patch_proposal.artifacts import create_patch_proposal_artifact
from runtime_lab.patch_proposal.receipts import verify_patch_proposal_receipt


def _request() -> dict:
    return {
        "proposal_id": "R125-PROP-001",
        "base_commit": "5fb1ee741bd986dadbb764622c03a0163168adc0",
        "target_files": ["docs/example.md"],
        "unified_diff": "--- a/docs/example.md\n+++ b/docs/example.md\n@@ -1 +1 @@\n-old\n+new\n",
        "risk_class": "LOW",
        "change_summary": "Update example text.",
        "validation_plan": ["review artifact"],
        "rollback_plan": "Do not apply proposal.",
        "human_approval_required": True,
        "apply_allowed": False,
        "apply_performed": False,
        "workspace_mutation_performed": False,
        "test_execution_allowed": False,
        "test_execution_performed": False,
    }


def test_patch_proposal_receipt_is_deterministic_and_tamper_sensitive(tmp_path: Path):
    workspace = tmp_path / "workspace"
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    workspace.mkdir()
    (workspace / "docs").mkdir()
    (workspace / "docs" / "example.md").write_text("old\n", encoding="utf-8")

    first = create_patch_proposal_artifact(copy.deepcopy(_request()), workspace_root=workspace, artifact_dir=first_dir)
    second = create_patch_proposal_artifact(copy.deepcopy(_request()), workspace_root=workspace, artifact_dir=second_dir)

    assert first["receipt"]["proposal_id"] == "R125-PROP-001"
    assert first["receipt"]["target_file_hashes_recorded"] is True
    assert first["receipt"]["unified_diff_hash"] == second["receipt"]["unified_diff_hash"]
    assert first["receipt"]["apply_allowed"] is False
    assert first["receipt"]["apply_performed"] is False
    assert first["receipt"]["workspace_mutation_performed"] is False
    assert first["receipt"]["test_execution_performed"] is False
    assert first["receipt"]["human_approval_required"] is True
    assert verify_patch_proposal_receipt(first["receipt"]) is True

    tampered = dict(first["receipt"])
    tampered["apply_performed"] = True
    assert verify_patch_proposal_receipt(tampered) is False
