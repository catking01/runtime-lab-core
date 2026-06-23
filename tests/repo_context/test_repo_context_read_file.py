from __future__ import annotations

from pathlib import Path

from runtime_lab.repo_context.executors import read_file
from runtime_lab.repo_context.models import RepoContextAuthority
from runtime_lab.repo_context.policy import RepoContextPolicy
from runtime_lab.repo_context.receipts import verify_repo_context_receipt


def _authority() -> RepoContextAuthority:
    return RepoContextAuthority(task_id="r124-test", allowed_executors=("read_file",))


def test_read_file_returns_content_and_hash_bound_receipt_without_recording_content(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "docs").mkdir()
    (workspace / "docs" / "note.md").write_text("hello runtime lab", encoding="utf-8")

    result = read_file(workspace_root=workspace, requested_path="docs/note.md", authority=_authority())

    assert result["accepted"] is True
    assert result["content"] == "hello runtime lab"
    assert result["receipt"]["content_recorded"] is False
    assert result["receipt"]["content_hash"].startswith("sha256:")
    assert "hello runtime lab" not in repr(result["receipt"])
    assert verify_repo_context_receipt(result["receipt"]) is True
    assert result["ledger_event"]["event_type"] == "repo_context.read_file"


def test_read_file_redacts_secret_like_content_by_default(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    token = "sk-" + ("x" * 24)
    (workspace / "note.txt").write_text(f"token={token}", encoding="utf-8")

    result = read_file(workspace_root=workspace, requested_path="note.txt", authority=_authority())

    assert result["accepted"] is True
    assert token not in result["content"]
    assert "<REDACTED_SECRET_LIKE_VALUE>" in result["content"]
    assert result["receipt"]["redaction_applied"] is True


def test_read_file_rejects_binary_and_oversized_files(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "binary.bin").write_bytes(b"\x00\x01binary")
    (workspace / "large.txt").write_text("x" * 11, encoding="utf-8")
    policy = RepoContextPolicy(max_file_size_bytes=10)

    binary = read_file(workspace_root=workspace, requested_path="binary.bin", authority=_authority(), policy=policy)
    oversized = read_file(workspace_root=workspace, requested_path="large.txt", authority=_authority(), policy=policy)

    assert binary["accepted"] is False
    assert binary["rejection_codes"] == ["BINARY_FILE_REJECTED"]
    assert oversized["accepted"] is False
    assert oversized["rejection_codes"] == ["FILE_TOO_LARGE"]


def test_read_file_rejects_write_attempt_and_wrong_executor_authority(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "note.txt").write_text("hello", encoding="utf-8")

    write_attempt = read_file(
        workspace_root=workspace,
        requested_path="note.txt",
        authority=_authority(),
        write_intent=True,
    )
    wrong_authority = read_file(
        workspace_root=workspace,
        requested_path="note.txt",
        authority=RepoContextAuthority(task_id="r124-test", allowed_executors=("list_files",)),
    )

    assert write_attempt["accepted"] is False
    assert write_attempt["rejection_codes"] == ["WRITE_INTENT_REJECTED"]
    assert wrong_authority["accepted"] is False
    assert wrong_authority["rejection_codes"] == ["EXECUTOR_NOT_AUTHORIZED"]
