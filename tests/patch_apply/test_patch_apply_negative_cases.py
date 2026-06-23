from __future__ import annotations

from pathlib import Path

import pytest

from runtime_lab.patch_apply.policy import PatchApplyPolicy, validate_patch_apply_request
from runtime_lab.patch_apply.transaction import apply_patch_transaction

from .conftest import make_approval, make_diff, make_proposal, make_request, make_workspace


def _absolute_outside_path() -> str:
    return "/" + "tmp/outside.txt"


def _mutated_request(tmp_path: Path, case_id: str) -> tuple[Path, dict, str]:
    workspace = make_workspace(tmp_path)
    proposal = make_proposal(workspace)
    approval = make_approval(workspace, proposal)
    request = make_request(workspace, proposal=proposal, approval=approval)

    if case_id == "missing_approval":
        request.pop("approval_packet")
        return workspace, request, "APPROVAL_PACKET_REQUIRED"
    if case_id == "expired_approval":
        request["approval_packet"] = make_approval(workspace, proposal, approval_expires_at_utc="2000-01-01T00:00:00Z")
        return workspace, request, "APPROVAL_EXPIRED"
    if case_id == "approval_proposal_hash_mismatch":
        request["approval_packet"]["proposal_hash"] = "sha256:mismatch"
        return workspace, request, "APPROVAL_PROPOSAL_HASH_MISMATCH"
    if case_id == "approval_diff_hash_mismatch":
        request["approval_packet"]["approved_unified_diff_hash"] = "sha256:mismatch"
        return workspace, request, "APPROVAL_DIFF_HASH_MISMATCH"
    if case_id == "approval_base_commit_mismatch":
        request["approval_packet"]["base_commit"] = "5fb1ee741bd986dadbb764622c03a0163168adc0"
        return workspace, request, "APPROVAL_BASE_COMMIT_MISMATCH"
    if case_id == "approval_target_files_mismatch":
        request["approval_packet"]["approved_target_files"] = ["docs/other.md"]
        return workspace, request, "APPROVAL_TARGET_FILES_MISMATCH"
    if case_id == "approval_wildcard_target":
        request["approval_packet"]["approved_target_files"] = ["*"]
        return workspace, request, "APPROVAL_WILDCARD_TARGET_REJECTED"
    if case_id == "approval_actor_missing":
        request["approval_packet"]["approved_by_actor_id"] = ""
        return workspace, request, "APPROVAL_ACTOR_REQUIRED"
    if case_id == "approval_scope_too_broad":
        request["approval_packet"]["authority_scope"] = "apply_any_patch"
        return workspace, request, "APPROVAL_SCOPE_TOO_BROAD"
    if case_id == "approval_apply_any_patch":
        request["approval_packet"]["apply_any_patch"] = True
        return workspace, request, "APPROVAL_SCOPE_TOO_BROAD"
    if case_id == "approval_rollback_missing":
        request["approval_packet"]["rollback_required"] = False
        return workspace, request, "APPROVAL_ROLLBACK_REQUIRED"
    if case_id == "approval_confirmation_too_weak":
        request["approval_packet"]["human_confirmation_text"] = "yes"
        return workspace, request, "APPROVAL_CONFIRMATION_TEXT_REJECTED"
    if case_id == "proposal_missing":
        request.pop("proposal")
        return workspace, request, "PROPOSAL_REQUIRED"
    if case_id == "proposal_claims_apply":
        request["proposal"]["apply_performed"] = True
        request["approval_packet"] = make_approval(workspace, request["proposal"])
        return workspace, request, "PROPOSAL_APPLICATION_CLAIM_REJECTED"
    if case_id == "proposal_hash_mismatch":
        request["approval_packet"]["proposal_hash"] = "sha256:not-current"
        return workspace, request, "APPROVAL_PROPOSAL_HASH_MISMATCH"
    if case_id == "base_commit_mismatch":
        request["base_commit"] = "5fb1ee741bd986dadbb764622c03a0163168adc0"
        return workspace, request, "BASE_COMMIT_MISMATCH"
    if case_id == "preimage_hash_mismatch":
        request["proposal"]["target_file_hashes"]["docs/example.md"] = "sha256:not-current"
        request["approval_packet"] = make_approval(workspace, request["proposal"])
        return workspace, request, "PREIMAGE_HASH_MISMATCH"
    if case_id == "absolute_target":
        proposal = make_proposal(workspace, target_files=[_absolute_outside_path()], unified_diff=make_diff("tmp/outside.txt"))
        return workspace, make_request(workspace, proposal=proposal, approval=make_approval(workspace, proposal)), "ABSOLUTE_PATH_REJECTED"
    if case_id == "path_traversal_target":
        proposal = make_proposal(workspace, target_files=["../outside.txt"], unified_diff=make_diff("../outside.txt"))
        return workspace, make_request(workspace, proposal=proposal, approval=make_approval(workspace, proposal)), "PATH_TRAVERSAL_REJECTED"
    if case_id == "symlink_target":
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "secret.txt").write_text("old\n", encoding="utf-8")
        (workspace / "docs" / "link.md").symlink_to(outside / "secret.txt")
        proposal = make_proposal(workspace, target_files=["docs/link.md"], unified_diff=make_diff("docs/link.md"))
        return workspace, make_request(workspace, proposal=proposal, approval=make_approval(workspace, proposal)), "SYMLINK_TARGET_REJECTED"
    if case_id == "git_target":
        proposal = make_proposal(workspace, target_files=[".git/config"], unified_diff=make_diff(".git/config"))
        return workspace, make_request(workspace, proposal=proposal, approval=make_approval(workspace, proposal)), "DENIED_PATH_PATTERN"
    if case_id == "codex_sessions_target":
        proposal = make_proposal(workspace, target_files=[".codex/sessions/log.jsonl"], unified_diff=make_diff(".codex/sessions/log.jsonl"))
        return workspace, make_request(workspace, proposal=proposal, approval=make_approval(workspace, proposal)), "DENIED_PATH_PATTERN"
    if case_id == "env_target":
        proposal = make_proposal(workspace, target_files=[".env"], unified_diff=make_diff(".env"))
        return workspace, make_request(workspace, proposal=proposal, approval=make_approval(workspace, proposal)), "DENIED_PATH_PATTERN"
    if case_id == "private_key_target":
        proposal = make_proposal(workspace, target_files=["keys/id_ed25519"], unified_diff=make_diff("keys/id_ed25519"))
        return workspace, make_request(workspace, proposal=proposal, approval=make_approval(workspace, proposal)), "DENIED_PATH_PATTERN"
    if case_id == "binary_target":
        (workspace / "docs" / "blob.bin").write_bytes(b"old\x00binary")
        proposal = make_proposal(workspace, target_files=["docs/blob.bin"], unified_diff=make_diff("docs/blob.bin"))
        return workspace, make_request(workspace, proposal=proposal, approval=make_approval(workspace, proposal)), "BINARY_TARGET_REJECTED"
    if case_id == "malformed_diff":
        proposal = make_proposal(workspace, unified_diff="--- a/docs/example.md\n@@ -1 +1 @@\n-old\n+new\n")
        return workspace, make_request(workspace, proposal=proposal, approval=make_approval(workspace, proposal)), "MALFORMED_UNIFIED_DIFF"
    if case_id == "mode_change":
        proposal = make_proposal(workspace, unified_diff="old mode 100644\nnew mode 100755\n")
        return workspace, make_request(workspace, proposal=proposal, approval=make_approval(workspace, proposal)), "MODE_CHANGE_REJECTED"
    if case_id == "rename":
        proposal = make_proposal(workspace, unified_diff="rename from docs/example.md\nrename to docs/other.md\n")
        return workspace, make_request(workspace, proposal=proposal, approval=make_approval(workspace, proposal)), "RENAME_OR_COPY_REJECTED"
    if case_id == "copy":
        proposal = make_proposal(workspace, unified_diff="copy from docs/example.md\ncopy to docs/other.md\n")
        return workspace, make_request(workspace, proposal=proposal, approval=make_approval(workspace, proposal)), "RENAME_OR_COPY_REJECTED"
    if case_id == "delete":
        proposal = make_proposal(workspace, unified_diff="--- a/docs/example.md\n+++ /dev/null\n@@ -1 +0,0 @@\n-old\n")
        return workspace, make_request(workspace, proposal=proposal, approval=make_approval(workspace, proposal)), "DELETE_FILE_REJECTED"
    if case_id == "new_file":
        proposal = make_proposal(workspace, target_files=["docs/new.md"], unified_diff="--- /dev/null\n+++ b/docs/new.md\n@@ -0,0 +1 @@\n+new\n")
        return workspace, make_request(workspace, proposal=proposal, approval=make_approval(workspace, proposal)), "NEW_FILE_REJECTED"
    if case_id == "shell_command_payload":
        request["shell_command"] = "git apply proposal.patch"
        return workspace, request, "SHELL_EXECUTION_REQUEST_REJECTED"
    if case_id == "network_instruction":
        request["network_instruction"] = "curl https://example.com/patch"
        return workspace, request, "NETWORK_EXECUTION_REQUEST_REJECTED"
    if case_id == "llm_invocation_request":
        request["llm_invocation_requested"] = True
        return workspace, request, "LLM_INVOCATION_REQUEST_REJECTED"
    if case_id == "executor_dispatch_request":
        request["executor_dispatch_requested"] = True
        return workspace, request, "EXECUTOR_DISPATCH_REQUEST_REJECTED"
    if case_id == "test_execution_request":
        request["tests_run"] = True
        return workspace, request, "TEST_EXECUTION_REQUEST_REJECTED"

    raise AssertionError(f"unhandled case {case_id}")


@pytest.mark.parametrize(
    "case_id",
    [
        "missing_approval",
        "expired_approval",
        "approval_proposal_hash_mismatch",
        "approval_diff_hash_mismatch",
        "approval_base_commit_mismatch",
        "approval_target_files_mismatch",
        "approval_wildcard_target",
        "approval_actor_missing",
        "approval_scope_too_broad",
        "approval_apply_any_patch",
        "approval_rollback_missing",
        "approval_confirmation_too_weak",
        "proposal_missing",
        "proposal_claims_apply",
        "proposal_hash_mismatch",
        "base_commit_mismatch",
        "preimage_hash_mismatch",
        "absolute_target",
        "path_traversal_target",
        "symlink_target",
        "git_target",
        "codex_sessions_target",
        "env_target",
        "private_key_target",
        "binary_target",
        "malformed_diff",
        "mode_change",
        "rename",
        "copy",
        "delete",
        "new_file",
        "shell_command_payload",
        "network_instruction",
        "llm_invocation_request",
        "executor_dispatch_request",
        "test_execution_request",
    ],
)
def test_patch_apply_negative_cases_fail_closed(tmp_path: Path, case_id: str):
    workspace, request, code = _mutated_request(tmp_path, case_id)

    result = validate_patch_apply_request(request, workspace_root=workspace)

    assert result["accepted"] is False
    assert code in result["rejection_codes"]
    assert result["apply_performed"] is False
    assert result["workspace_mutation_performed"] is False
    assert result["tests_run"] is False
    assert result["llm_invocation_performed"] is False
    assert result["executor_dispatch_performed"] is False


def test_patch_apply_rejects_oversized_target(tmp_path: Path):
    workspace = make_workspace(tmp_path)
    request = make_request(workspace)

    result = validate_patch_apply_request(
        request,
        workspace_root=workspace,
        policy=PatchApplyPolicy(max_target_file_bytes=2),
    )

    assert result["accepted"] is False
    assert "TARGET_SIZE_LIMIT_EXCEEDED" in result["rejection_codes"]


def test_patch_apply_rejects_rollback_artifact_write_failure(tmp_path: Path):
    workspace = make_workspace(tmp_path)
    blocking_file = tmp_path / "not-a-directory"
    blocking_file.write_text("blocks transaction dir\n", encoding="utf-8")

    result = apply_patch_transaction(make_request(workspace), workspace_root=workspace, transaction_dir=blocking_file)

    assert result["accepted"] is False
    assert "ROLLBACK_ARTIFACT_WRITE_FAILED" in result["rejection_codes"]
    assert result["workspace_mutation_performed"] is False
    assert (workspace / "docs" / "example.md").read_text(encoding="utf-8") == "old\n"
