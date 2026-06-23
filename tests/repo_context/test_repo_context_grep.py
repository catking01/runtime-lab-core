from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from runtime_lab.repo_context.executors import grep
from runtime_lab.repo_context.models import RepoContextAuthority
from runtime_lab.repo_context.policy import RepoContextPolicy
from runtime_lab.repo_context.receipts import verify_repo_context_receipt


def _authority() -> RepoContextAuthority:
    return RepoContextAuthority(task_id="r124-test", allowed_executors=("grep",))


def test_grep_finds_matches_without_shell_or_subprocess(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "a.txt").write_text("alpha\nbeta\n", encoding="utf-8")
    (workspace / "b.txt").write_text("gamma\nalpha\n", encoding="utf-8")

    def fail_subprocess(*args, **kwargs):  # pragma: no cover - executed only if implementation leaks subprocess
        raise AssertionError("grep must not use subprocess")

    monkeypatch.setattr(subprocess, "run", fail_subprocess)
    monkeypatch.setattr(subprocess, "Popen", fail_subprocess)

    result = grep(workspace_root=workspace, pattern="alpha", authority=_authority())

    assert result["accepted"] is True
    assert [(m["path"], m["line_number"], m["line"]) for m in result["matches"]] == [
        ("a.txt", 1, "alpha"),
        ("b.txt", 2, "alpha"),
    ]
    assert result["shell_execution_started"] is False
    assert result["network_execution_started"] is False
    assert verify_repo_context_receipt(result["receipt"]) is True


def test_grep_caps_matches_and_marks_truncated(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "a.txt").write_text("needle\nneedle\nneedle\n", encoding="utf-8")

    result = grep(
        workspace_root=workspace,
        pattern="needle",
        authority=_authority(),
        policy=RepoContextPolicy(max_grep_matches=2),
    )

    assert result["accepted"] is True
    assert len(result["matches"]) == 2
    assert result["truncated"] is True
    assert result["receipt"]["result"] == "SUCCESS_TRUNCATED"


@pytest.mark.parametrize("pattern", ["needle; rm -rf /", "needle && cat .env", "$(cat .env)", "`cat .env`"])
def test_grep_rejects_shell_command_disguised_as_pattern(tmp_path: Path, pattern: str):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "a.txt").write_text("needle", encoding="utf-8")

    result = grep(workspace_root=workspace, pattern=pattern, authority=_authority())

    assert result["accepted"] is False
    assert result["rejection_codes"] == ["SHELL_PATTERN_REJECTED"]
    assert result["shell_execution_started"] is False


def test_grep_rejects_unknown_executor_dispatch(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    result = grep(
        workspace_root=workspace,
        pattern="needle",
        authority=RepoContextAuthority(task_id="r124-test", allowed_executors=("unknown",)),
    )

    assert result["accepted"] is False
    assert result["rejection_codes"] == ["EXECUTOR_NOT_AUTHORIZED"]


def test_grep_rejects_invalid_regex_with_receipt(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "a.txt").write_text("needle", encoding="utf-8")

    result = grep(workspace_root=workspace, pattern="[", authority=_authority())

    assert result["accepted"] is False
    assert result["rejection_codes"] == ["INVALID_GREP_PATTERN"]
    assert result["shell_execution_started"] is False
    assert verify_repo_context_receipt(result["receipt"]) is True
