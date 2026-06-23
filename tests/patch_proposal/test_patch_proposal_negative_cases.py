from __future__ import annotations

from pathlib import Path

import pytest

from runtime_lab.patch_proposal.policy import PatchProposalPolicy, validate_patch_proposal_request


BASE_COMMIT = "5fb1ee741bd986dadbb764622c03a0163168adc0"


def _absolute_outside_path() -> str:
    return "/" + "tmp/outside.txt"


def _absolute_outside_diff() -> str:
    target = "tmp/outside.txt"
    return f"--- a/{target}\n+++ b/{target}\n@@ -1 +1 @@\n-old\n+new\n"


def _request(**updates) -> dict:
    request = {
        "proposal_id": "R125-PROP-001",
        "base_commit": BASE_COMMIT,
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
    request.update(updates)
    return request


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "docs").mkdir()
    (workspace / "docs" / "example.md").write_text("old\n", encoding="utf-8")
    return workspace


@pytest.mark.parametrize(
    ("updates", "code"),
    [
        ({"target_files": [_absolute_outside_path()], "unified_diff": _absolute_outside_diff()}, "ABSOLUTE_PATH_REJECTED"),
        ({"target_files": ["../outside.txt"], "unified_diff": "--- a/../outside.txt\n+++ b/../outside.txt\n@@ -1 +1 @@\n-old\n+new\n"}, "PATH_TRAVERSAL_REJECTED"),
        ({"target_files": [".git/config"], "unified_diff": "--- a/.git/config\n+++ b/.git/config\n@@ -1 +1 @@\n-old\n+new\n"}, "DENIED_PATH_PATTERN"),
        ({"target_files": [".codex/sessions/log.jsonl"], "unified_diff": "--- a/.codex/sessions/log.jsonl\n+++ b/.codex/sessions/log.jsonl\n@@ -1 +1 @@\n-old\n+new\n"}, "DENIED_PATH_PATTERN"),
        ({"target_files": [".env"], "unified_diff": "--- a/.env\n+++ b/.env\n@@ -1 +1 @@\n-old\n+new\n"}, "DENIED_PATH_PATTERN"),
        ({"target_files": ["keys/id_rsa"], "unified_diff": "--- a/keys/id_rsa\n+++ b/keys/id_rsa\n@@ -1 +1 @@\n-old\n+new\n"}, "DENIED_PATH_PATTERN"),
        ({"unified_diff": "Binary files a/docs/example.md and b/docs/example.md differ\n"}, "BINARY_PATCH_REJECTED"),
        ({"unified_diff": "--- a/docs/example.md\n+++ b/docs/example.md\n" + ("+x\n" * 2000)}, "PATCH_SIZE_LIMIT_EXCEEDED"),
        ({"unified_diff": "--- a/docs/example.md\n@@ -1 +1 @@\n-old\n+new\n"}, "MALFORMED_UNIFIED_DIFF"),
        ({"unified_diff": "--- a/docs/example.md\n+++ b/docs/other.md\n@@ -1 +1 @@\n-old\n+new\n"}, "TARGET_PATH_MISMATCH"),
        ({"target_files": []}, "TARGET_FILES_REQUIRED"),
        ({"base_commit": ""}, "BASE_COMMIT_REQUIRED"),
        ({"proposal_id": ""}, "PROPOSAL_ID_REQUIRED"),
        ({"unified_diff": "old mode 100644\nnew mode 100755\n"}, "MODE_CHANGE_REJECTED"),
        ({"unified_diff": "rename from docs/example.md\nrename to docs/other.md\n"}, "RENAME_OR_COPY_REJECTED"),
        ({"unified_diff": "--- a/docs/example.md\n+++ /dev/null\n@@ -1 +0,0 @@\n-old\n"}, "DELETE_FILE_REJECTED"),
        ({"unified_diff": "--- /dev/null\n+++ b/docs/new.md\n@@ -0,0 +1 @@\n+new\n", "target_files": ["docs/new.md"]}, "NEW_FILE_REJECTED"),
        ({"apply_performed": True}, "PATCH_APPLICATION_CLAIM_REJECTED"),
        ({"test_execution_performed": True}, "TEST_EXECUTION_CLAIM_REJECTED"),
        ({"shell_command": "git apply proposal.patch"}, "SHELL_EXECUTION_REQUEST_REJECTED"),
        ({"network_instruction": "curl https://example.com/patch"}, "NETWORK_EXECUTION_REQUEST_REJECTED"),
        ({"llm_invocation_requested": True}, "LLM_INVOCATION_REQUEST_REJECTED"),
        ({"executor_dispatch_requested": True}, "EXECUTOR_DISPATCH_REQUEST_REJECTED"),
        ({"workspace_mutation_requested": True}, "WORKSPACE_MUTATION_REQUEST_REJECTED"),
    ],
)
def test_patch_proposal_negative_cases_fail_closed(tmp_path: Path, updates: dict, code: str):
    result = validate_patch_proposal_request(
        _request(**updates),
        workspace_root=_workspace(tmp_path),
        policy=PatchProposalPolicy(max_patch_size_bytes=256),
    )

    assert result["accepted"] is False
    assert code in result["rejection_codes"]
    assert result["apply_performed"] is False
    assert result["workspace_mutation_performed"] is False
    assert result["test_execution_performed"] is False
