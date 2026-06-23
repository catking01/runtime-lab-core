from __future__ import annotations

from pathlib import Path

import pytest

from runtime_lab.patch_apply.policy import PatchApplyPolicy, validate_patch_apply_request

from .conftest import make_approval, make_diff, make_proposal, make_request, make_workspace, sha256_bytes


def _absolute_outside_path() -> str:
    return "/" + "tmp/outside.txt"


def test_validate_patch_apply_request_accepts_bound_existing_text_file(tmp_path: Path):
    workspace = make_workspace(tmp_path)
    request = make_request(workspace)

    result = validate_patch_apply_request(request, workspace_root=workspace)

    assert result["accepted"] is True
    assert result["approval_verified"] is True
    assert result["preimage_verified"] is True
    assert result["apply_performed"] is False
    assert result["workspace_mutation_performed"] is False
    assert result["tests_run"] is False
    assert result["llm_invocation_performed"] is False
    assert result["executor_dispatch_performed"] is False
    assert result["target_files"] == ["docs/example.md"]


def test_validate_patch_apply_request_rejects_preimage_hash_mismatch(tmp_path: Path):
    workspace = make_workspace(tmp_path)
    proposal = make_proposal(workspace)
    proposal["target_file_hashes"]["docs/example.md"] = "sha256:not-current"
    request = make_request(workspace, proposal=proposal, approval=make_approval(workspace, proposal))

    result = validate_patch_apply_request(request, workspace_root=workspace)

    assert result["accepted"] is False
    assert "PREIMAGE_HASH_MISMATCH" in result["rejection_codes"]
    assert result["workspace_mutation_performed"] is False


@pytest.mark.parametrize(
    ("target", "code"),
    [
        (_absolute_outside_path(), "ABSOLUTE_PATH_REJECTED"),
        ("../outside.txt", "PATH_TRAVERSAL_REJECTED"),
        (".git/config", "DENIED_PATH_PATTERN"),
        (".codex/sessions/log.jsonl", "DENIED_PATH_PATTERN"),
        (".env", "DENIED_PATH_PATTERN"),
        ("keys/id_rsa", "DENIED_PATH_PATTERN"),
    ],
)
def test_validate_patch_apply_request_rejects_unsafe_targets(tmp_path: Path, target: str, code: str):
    workspace = make_workspace(tmp_path)
    diff_path = target.lstrip("/")
    proposal = make_proposal(workspace, target_files=[target], unified_diff=make_diff(diff_path))
    request = make_request(workspace, proposal=proposal, approval=make_approval(workspace, proposal))

    result = validate_patch_apply_request(request, workspace_root=workspace)

    assert result["accepted"] is False
    assert code in result["rejection_codes"]


def test_validate_patch_apply_request_rejects_symlink_target(tmp_path: Path):
    workspace = make_workspace(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("old\n", encoding="utf-8")
    (workspace / "docs" / "link.md").symlink_to(outside / "secret.txt")
    proposal = make_proposal(
        workspace,
        target_files=["docs/link.md"],
        unified_diff=make_diff("docs/link.md"),
    )
    request = make_request(workspace, proposal=proposal, approval=make_approval(workspace, proposal))

    result = validate_patch_apply_request(request, workspace_root=workspace)

    assert result["accepted"] is False
    assert "SYMLINK_TARGET_REJECTED" in result["rejection_codes"]


def test_validate_patch_apply_request_rejects_binary_and_oversized_targets(tmp_path: Path):
    workspace = make_workspace(tmp_path, {"docs/example.md": "old\n", "docs/blob.bin": "old\n"})
    (workspace / "docs" / "blob.bin").write_bytes(b"old\x00binary")
    binary_proposal = make_proposal(
        workspace,
        target_files=["docs/blob.bin"],
        unified_diff=make_diff("docs/blob.bin"),
    )
    binary_request = make_request(workspace, proposal=binary_proposal, approval=make_approval(workspace, binary_proposal))

    binary_result = validate_patch_apply_request(binary_request, workspace_root=workspace)

    assert binary_result["accepted"] is False
    assert "BINARY_TARGET_REJECTED" in binary_result["rejection_codes"]

    text_hash = sha256_bytes((workspace / "docs" / "example.md").read_bytes())
    oversized_proposal = make_proposal(workspace)
    oversized_proposal["target_file_hashes"]["docs/example.md"] = text_hash
    oversized_request = make_request(workspace, proposal=oversized_proposal, approval=make_approval(workspace, oversized_proposal))

    oversized_result = validate_patch_apply_request(
        oversized_request,
        workspace_root=workspace,
        policy=PatchApplyPolicy(max_target_file_bytes=2),
    )

    assert oversized_result["accepted"] is False
    assert "TARGET_SIZE_LIMIT_EXCEEDED" in oversized_result["rejection_codes"]
