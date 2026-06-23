from __future__ import annotations

from pathlib import Path

import pytest

from runtime_lab.repo_context.errors import RepoContextPolicyError
from runtime_lab.repo_context.path_policy import resolve_workspace_path
from runtime_lab.repo_context.policy import RepoContextPolicy


def _absolute_outside_path() -> str:
    return "/" + "tmp/outside.txt"


def test_resolve_workspace_path_accepts_relative_path_inside_workspace(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "docs" / "note.md"
    target.parent.mkdir()
    target.write_text("hello", encoding="utf-8")

    resolved = resolve_workspace_path(
        workspace_root=workspace,
        requested_path="docs/note.md",
        policy=RepoContextPolicy(),
    )

    assert resolved.relative_path == "docs/note.md"
    assert resolved.path == target.resolve()
    assert resolved.path_allowed is True


@pytest.mark.parametrize(
    ("requested_path", "code"),
    [
        ("../outside.txt", "PATH_TRAVERSAL_REJECTED"),
        (_absolute_outside_path(), "ABSOLUTE_PATH_REJECTED"),
        ("https://example.com/repo.txt", "NETWORK_URL_REJECTED"),
        (".git/config", "DENIED_PATH_PATTERN"),
        (".env", "DENIED_PATH_PATTERN"),
        ("secrets/id_rsa", "DENIED_PATH_PATTERN"),
        ("keychain-dump.txt", "DENIED_PATH_PATTERN"),
        (".codex/sessions/session.jsonl", "DENIED_PATH_PATTERN"),
    ],
)
def test_resolve_workspace_path_rejects_forbidden_paths(tmp_path: Path, requested_path: str, code: str):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with pytest.raises(RepoContextPolicyError) as exc:
        resolve_workspace_path(
            workspace_root=workspace,
            requested_path=requested_path,
            policy=RepoContextPolicy(),
        )

    assert exc.value.code == code
    assert exc.value.read_only is True
    assert exc.value.workspace_mutation_started is False


def test_resolve_workspace_path_rejects_symlink_escape(tmp_path: Path):
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("outside", encoding="utf-8")
    (workspace / "escape.txt").symlink_to(outside / "secret.txt")

    with pytest.raises(RepoContextPolicyError) as exc:
        resolve_workspace_path(
            workspace_root=workspace,
            requested_path="escape.txt",
            policy=RepoContextPolicy(),
        )

    assert exc.value.code == "SYMLINK_ESCAPE_REJECTED"


def test_resolve_workspace_path_rejects_missing_workspace_root():
    with pytest.raises(RepoContextPolicyError) as exc:
        resolve_workspace_path(
            workspace_root=None,
            requested_path="README.md",
            policy=RepoContextPolicy(),
        )

    assert exc.value.code == "WORKSPACE_ROOT_MISSING"
