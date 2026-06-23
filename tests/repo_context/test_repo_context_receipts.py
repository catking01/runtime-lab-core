from __future__ import annotations

from pathlib import Path

from runtime_lab.repo_context.executors import read_file
from runtime_lab.repo_context.models import RepoContextAuthority
from runtime_lab.repo_context.receipts import verify_repo_context_receipt


def test_receipt_is_tamper_sensitive_and_preserves_non_execution_flags(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "note.txt").write_text("hello", encoding="utf-8")

    result = read_file(
        workspace_root=workspace,
        requested_path="note.txt",
        authority=RepoContextAuthority(task_id="r124-test", allowed_executors=("read_file",)),
    )
    receipt = result["receipt"]

    assert verify_repo_context_receipt(receipt) is True
    assert receipt["read_only"] is True
    assert receipt["content_recorded"] is False
    assert receipt["non_claims"] == {
        "file_mutation": False,
        "shell_execution": False,
        "network_execution": False,
        "llm_invocation": False,
        "agent_loop": False,
        "remote_sealed_pass": False,
    }

    tampered = dict(receipt)
    tampered["bytes_read"] = receipt["bytes_read"] + 1
    assert verify_repo_context_receipt(tampered) is False


def test_rejected_receipt_is_generated_for_policy_failure(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    result = read_file(
        workspace_root=workspace,
        requested_path="../outside.txt",
        authority=RepoContextAuthority(task_id="r124-test", allowed_executors=("read_file",)),
    )

    assert result["accepted"] is False
    assert result["receipt"]["result"] == "REJECT_FAIL_CLOSED"
    assert result["receipt"]["path_allowed"] is False
    assert verify_repo_context_receipt(result["receipt"]) is True
