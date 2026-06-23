from __future__ import annotations

from pathlib import Path

import pytest

from runtime_lab.patch_proposal.errors import PatchProposalPolicyError
from runtime_lab.patch_proposal.path_policy import resolve_patch_target_path
from runtime_lab.patch_proposal.policy import PatchProposalPolicy, validate_patch_proposal_request


def _absolute_outside_path() -> str:
    return "/" + "tmp/outside.txt"


def _valid_request() -> dict:
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


def test_validate_patch_proposal_request_accepts_artifact_only_request(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "docs").mkdir()
    (workspace / "docs" / "example.md").write_text("old\n", encoding="utf-8")

    result = validate_patch_proposal_request(_valid_request(), workspace_root=workspace)

    assert result["accepted"] is True
    assert result["target_files"] == ["docs/example.md"]
    assert result["apply_allowed"] is False
    assert result["apply_performed"] is False
    assert result["workspace_mutation_performed"] is False
    assert result["test_execution_performed"] is False


@pytest.mark.parametrize(
    ("target", "code"),
    [
        (_absolute_outside_path(), "ABSOLUTE_PATH_REJECTED"),
        ("../outside.txt", "PATH_TRAVERSAL_REJECTED"),
        (".git/config", "DENIED_PATH_PATTERN"),
        (".codex/sessions/log.jsonl", "DENIED_PATH_PATTERN"),
        (".codex/archived_sessions/log.jsonl", "DENIED_PATH_PATTERN"),
        (".env", "DENIED_PATH_PATTERN"),
        ("keys/deploy.pem", "DENIED_PATH_PATTERN"),
    ],
)
def test_resolve_patch_target_path_rejects_unsafe_targets(tmp_path: Path, target: str, code: str):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with pytest.raises(PatchProposalPolicyError) as exc:
        resolve_patch_target_path(workspace_root=workspace, target_path=target)

    assert exc.value.code == code


def test_resolve_patch_target_path_rejects_symlink_escape(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "target.txt").write_text("outside\n", encoding="utf-8")
    (workspace / "link.txt").symlink_to(outside / "target.txt")

    with pytest.raises(PatchProposalPolicyError) as exc:
        resolve_patch_target_path(workspace_root=workspace, target_path="link.txt")

    assert exc.value.code == "SYMLINK_ESCAPE_REJECTED"


def test_validate_patch_proposal_rejects_claimed_apply_and_test_execution(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "docs").mkdir()
    (workspace / "docs" / "example.md").write_text("old\n", encoding="utf-8")
    request = _valid_request()
    request["apply_performed"] = True
    request["test_execution_performed"] = True

    result = validate_patch_proposal_request(request, workspace_root=workspace)

    assert result["accepted"] is False
    assert "PATCH_APPLICATION_CLAIM_REJECTED" in result["rejection_codes"]
    assert "TEST_EXECUTION_CLAIM_REJECTED" in result["rejection_codes"]


def test_validate_patch_proposal_rejects_missing_receipt_contract(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "docs").mkdir()
    (workspace / "docs" / "example.md").write_text("old\n", encoding="utf-8")

    result = validate_patch_proposal_request(
        _valid_request(),
        workspace_root=workspace,
        policy=PatchProposalPolicy(receipt_required=False),
    )

    assert result["accepted"] is False
    assert result["rejection_codes"] == ["RECEIPT_CONTRACT_REQUIRED"]
