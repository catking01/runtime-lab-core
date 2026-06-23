from __future__ import annotations

import json
from pathlib import Path

from runtime_lab.patch_apply.receipts import verify_patch_apply_receipt
from runtime_lab.patch_apply.transaction import apply_patch_transaction

from .conftest import make_approval, make_diff, make_proposal, make_request, make_workspace


def test_apply_patch_transaction_writes_rollback_before_mutating_target_and_receipt(tmp_path: Path):
    workspace = make_workspace(tmp_path)
    transaction_dir = tmp_path / "transactions" / "R126-TX-001"
    request = make_request(workspace)

    result = apply_patch_transaction(request, workspace_root=workspace, transaction_dir=transaction_dir)

    assert result["accepted"] is True
    assert result["result"] == "SUCCESS"
    assert (workspace / "docs" / "example.md").read_text(encoding="utf-8") == "new\n"
    assert result["apply_performed"] is True
    assert result["workspace_mutation_performed"] is True
    assert result["approval_verified"] is True
    assert result["preimage_verified"] is True
    assert result["postimage_verified"] is True
    assert result["rollback_artifact_written"] is True
    assert result["receipt_written"] is True
    assert result["tests_run"] is False
    assert result["llm_invocation_performed"] is False
    assert result["executor_dispatch_performed"] is False
    assert result["transaction_states"][:4] == [
        "PLANNED",
        "APPROVAL_VERIFIED",
        "PREIMAGE_VERIFIED",
        "ROLLBACK_PREPARED",
    ]
    assert result["transaction_states"][-1] == "COMMITTED_LOCAL_TRANSACTION"
    assert Path(result["rollback_artifact_path"]).is_file()
    assert Path(result["receipt_path"]).is_file()
    assert verify_patch_apply_receipt(result["receipt"]) is True
    rollback = json.loads(Path(result["rollback_artifact_path"]).read_text(encoding="utf-8"))
    assert rollback["preimage_hashes"]["docs/example.md"] == result["preimage_hashes"]["docs/example.md"]


def test_apply_patch_transaction_applies_multiple_files(tmp_path: Path):
    workspace = make_workspace(tmp_path, {"docs/a.md": "old a\n", "docs/b.md": "old b\n"})
    diff = (
        "--- a/docs/a.md\n+++ b/docs/a.md\n@@ -1 +1 @@\n-old a\n+new a\n"
        "--- a/docs/b.md\n+++ b/docs/b.md\n@@ -1 +1 @@\n-old b\n+new b\n"
    )
    proposal = make_proposal(workspace, target_files=["docs/a.md", "docs/b.md"], unified_diff=diff)
    request = make_request(workspace, proposal=proposal, approval=make_approval(workspace, proposal))

    result = apply_patch_transaction(request, workspace_root=workspace, transaction_dir=tmp_path / "tx")

    assert result["accepted"] is True
    assert (workspace / "docs" / "a.md").read_text(encoding="utf-8") == "new a\n"
    assert (workspace / "docs" / "b.md").read_text(encoding="utf-8") == "new b\n"
    assert result["files_changed"] == ["docs/a.md", "docs/b.md"]


def test_apply_patch_transaction_rolls_back_already_modified_files_on_partial_failure(tmp_path: Path):
    workspace = make_workspace(tmp_path, {"docs/a.md": "old a\n", "docs/b.md": "different b\n"})
    diff = (
        "--- a/docs/a.md\n+++ b/docs/a.md\n@@ -1 +1 @@\n-old a\n+new a\n"
        "--- a/docs/b.md\n+++ b/docs/b.md\n@@ -1 +1 @@\n-old b\n+new b\n"
    )
    proposal = make_proposal(workspace, target_files=["docs/a.md", "docs/b.md"], unified_diff=diff)
    request = make_request(workspace, proposal=proposal, approval=make_approval(workspace, proposal))

    result = apply_patch_transaction(request, workspace_root=workspace, transaction_dir=tmp_path / "tx")

    assert result["accepted"] is False
    assert "HUNK_CONTEXT_MISMATCH" in result["rejection_codes"]
    assert "ROLLBACK_COMPLETED" in result["transaction_states"]
    assert result["rollback_performed"] is True
    assert result["workspace_mutation_performed"] is False
    assert (workspace / "docs" / "a.md").read_text(encoding="utf-8") == "old a\n"
    assert (workspace / "docs" / "b.md").read_text(encoding="utf-8") == "different b\n"


def test_patch_apply_tests_mutate_only_tmp_workspace(tmp_path: Path):
    repo_marker = Path.cwd() / "R126_SHOULD_NOT_EXIST"
    assert not repo_marker.exists()
    workspace = make_workspace(tmp_path)

    result = apply_patch_transaction(make_request(workspace), workspace_root=workspace, transaction_dir=tmp_path / "tx")

    assert result["accepted"] is True
    assert not repo_marker.exists()
