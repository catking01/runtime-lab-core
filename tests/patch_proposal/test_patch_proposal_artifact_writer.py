from __future__ import annotations

import json
from pathlib import Path

from runtime_lab.patch_proposal.artifacts import create_patch_proposal_artifact
from runtime_lab.patch_proposal.receipts import verify_patch_proposal_receipt


def _request(diff: str | None = None) -> dict:
    return {
        "proposal_id": "R125-PROP-001",
        "base_commit": "5fb1ee741bd986dadbb764622c03a0163168adc0",
        "target_files": ["docs/example.md"],
        "unified_diff": diff
        or "--- a/docs/example.md\n+++ b/docs/example.md\n@@ -1 +1 @@\n-old\n+new\n",
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


def test_create_patch_proposal_artifact_writes_artifact_only_and_preserves_target(tmp_path: Path):
    workspace = tmp_path / "workspace"
    artifact_dir = tmp_path / "artifacts"
    workspace.mkdir()
    (workspace / "docs").mkdir()
    target = workspace / "docs" / "example.md"
    target.write_text("old\n", encoding="utf-8")

    result = create_patch_proposal_artifact(
        _request(),
        workspace_root=workspace,
        artifact_dir=artifact_dir,
    )

    assert result["accepted"] is True
    assert result["artifact_path"] == str(artifact_dir / "R125-PROP-001.json")
    assert target.read_text(encoding="utf-8") == "old\n"
    assert result["apply_performed"] is False
    assert result["workspace_mutation_performed"] is False
    assert result["test_execution_performed"] is False
    assert verify_patch_proposal_receipt(result["receipt"]) is True

    artifact = json.loads((artifact_dir / "R125-PROP-001.json").read_text(encoding="utf-8"))
    assert artifact["proposal_id"] == "R125-PROP-001"
    assert artifact["target_files"] == ["docs/example.md"]
    assert artifact["target_file_hashes_recorded"] is True
    assert artifact["unified_diff_hash"].startswith("sha256:")
    assert artifact["artifact_only"] is True
    assert artifact["apply_allowed"] is False
    assert artifact["human_approval_required"] is True
    assert artifact["receipt"]["receipt_hash"] == result["receipt"]["receipt_hash"]


def test_create_patch_proposal_artifact_redacts_secret_like_diff_lines(tmp_path: Path):
    workspace = tmp_path / "workspace"
    artifact_dir = tmp_path / "artifacts"
    workspace.mkdir()
    (workspace / "docs").mkdir()
    (workspace / "docs" / "example.md").write_text("old\n", encoding="utf-8")
    secret = "sk-" + ("x" * 24)
    diff = f"--- a/docs/example.md\n+++ b/docs/example.md\n@@ -1 +1 @@\n-old\n+token={secret}\n"

    result = create_patch_proposal_artifact(_request(diff), workspace_root=workspace, artifact_dir=artifact_dir)

    artifact_text = (artifact_dir / "R125-PROP-001.json").read_text(encoding="utf-8")
    assert result["accepted"] is True
    assert secret not in artifact_text
    assert "<REDACTED_SECRET_LIKE_VALUE>" in artifact_text
    assert result["receipt"]["redaction_applied"] is True
