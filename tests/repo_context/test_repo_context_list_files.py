from __future__ import annotations

from pathlib import Path

from runtime_lab.repo_context.executors import list_files
from runtime_lab.repo_context.models import RepoContextAuthority
from runtime_lab.repo_context.policy import RepoContextPolicy
from runtime_lab.repo_context.receipts import verify_repo_context_receipt


def test_list_files_returns_workspace_relative_files_and_receipt(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "README.md").write_text("readme", encoding="utf-8")
    (workspace / "docs").mkdir()
    (workspace / "docs" / "guide.md").write_text("guide", encoding="utf-8")
    (workspace / ".hidden").write_text("hidden", encoding="utf-8")

    result = list_files(
        workspace_root=workspace,
        authority=RepoContextAuthority(task_id="r124-test", allowed_executors=("list_files",)),
    )

    assert result["accepted"] is True
    assert result["files"] == ["README.md", "docs/guide.md"]
    assert result["read_only"] is True
    assert result["workspace_mutation_started"] is False
    assert result["shell_execution_started"] is False
    assert result["network_execution_started"] is False
    assert verify_repo_context_receipt(result["receipt"]) is True
    assert result["ledger_event"]["event_type"] == "repo_context.list_files"


def test_list_files_respects_max_files_and_marks_truncated(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    for index in range(5):
        (workspace / f"file_{index}.txt").write_text(str(index), encoding="utf-8")

    result = list_files(
        workspace_root=workspace,
        authority=RepoContextAuthority(task_id="r124-test", allowed_executors=("list_files",)),
        policy=RepoContextPolicy(max_files_returned=3),
    )

    assert result["accepted"] is True
    assert len(result["files"]) == 3
    assert result["truncated"] is True
    assert result["receipt"]["result"] == "SUCCESS_TRUNCATED"


def test_list_files_rejects_missing_authority(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    result = list_files(workspace_root=workspace, authority=None)

    assert result["accepted"] is False
    assert result["rejection_codes"] == ["AUTHORITY_MISSING"]
    assert result["transport_started"] is False
    assert result["workspace_mutation_started"] is False
