from __future__ import annotations

from pathlib import Path

from runtime_lab.repo_context.executors import execute_repo_context, grep, read_file
from runtime_lab.repo_context.models import RepoContextAuthority
from runtime_lab.repo_context.policy import RepoContextPolicy


def test_execute_repo_context_rejects_unknown_executor_id(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    result = execute_repo_context(
        executor_id="run_shell",
        workspace_root=workspace,
        authority=RepoContextAuthority(task_id="r124-test", allowed_executors=("run_shell",)),
    )

    assert result["accepted"] is False
    assert result["rejection_codes"] == ["UNKNOWN_EXECUTOR_ID"]
    assert result["shell_execution_started"] is False
    assert result["workspace_mutation_started"] is False


def test_read_file_rejects_receipt_contract_disabled(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "note.txt").write_text("hello", encoding="utf-8")

    result = read_file(
        workspace_root=workspace,
        requested_path="note.txt",
        authority=RepoContextAuthority(task_id="r124-test", allowed_executors=("read_file",)),
        policy=RepoContextPolicy(receipt_required=False),
    )

    assert result["accepted"] is False
    assert result["rejection_codes"] == ["RECEIPT_CONTRACT_REQUIRED"]


def test_grep_rejects_network_url_path(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    result = grep(
        workspace_root=workspace,
        pattern="hello",
        authority=RepoContextAuthority(task_id="r124-test", allowed_executors=("grep",)),
        requested_path="https://example.com/repo",
    )

    assert result["accepted"] is False
    assert result["rejection_codes"] == ["NETWORK_URL_REJECTED"]
    assert result["network_execution_started"] is False


def test_grep_skips_binary_and_denied_paths(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "ok.txt").write_text("needle", encoding="utf-8")
    (workspace / ".env").write_text("needle", encoding="utf-8")
    (workspace / "binary.bin").write_bytes(b"\x00needle")

    result = grep(
        workspace_root=workspace,
        pattern="needle",
        authority=RepoContextAuthority(task_id="r124-test", allowed_executors=("grep",)),
    )

    assert result["accepted"] is True
    assert [match["path"] for match in result["matches"]] == ["ok.txt"]
    assert result["skipped_count"] >= 2
