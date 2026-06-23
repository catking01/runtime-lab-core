from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from runtime_lab.agent_loop.models import AgentLoopAuthority, AgentLoopMode, AgentLoopPolicy, AgentLoopRequest
from runtime_lab.agent_loop.supervisor import run_agent_loop


def _request(tmp_path: Path, **overrides):
    values = {
        "task_id": "task-1",
        "run_id": "run-1",
        "mode": AgentLoopMode.DRY_RUN,
        "base_commit": "abc123",
        "workspace_root": tmp_path,
        "run_artifact_dir": tmp_path / "run",
        "task_text": "Create a supervised local proposal.",
        "target_files": ("a.txt",),
    }
    values.update(overrides)
    return AgentLoopRequest(**values)


NEGATIVE_CASES = [
    ("missing_authority", {}, None, AgentLoopPolicy(), "REJECTED_MISSING_AUTHORITY"),
    ("unknown_state", {"requested_initial_state": "SURPRISE"}, AgentLoopAuthority("task-1", "human-1"), AgentLoopPolicy(), "REJECTED_UNKNOWN_STATE"),
    ("unknown_transition", {"requested_transition": "launch_shell"}, AgentLoopAuthority("task-1", "human-1"), AgentLoopPolicy(), "REJECTED_UNKNOWN_TRANSITION"),
    ("missing_receipt", {}, AgentLoopAuthority("task-1", "human-1"), AgentLoopPolicy(require_receipts=False), "REJECTED_MISSING_RECEIPT"),
    ("missing_ledger_event", {}, AgentLoopAuthority("task-1", "human-1"), AgentLoopPolicy(require_ledger_events=False), "REJECTED_MISSING_LEDGER"),
    ("missing_replay_manifest", {}, AgentLoopAuthority("task-1", "human-1"), AgentLoopPolicy(require_replay_bundle=False), "REJECTED_MISSING_REPLAY_MANIFEST"),
    ("iteration_limit_exceeded", {"requested_iterations": 4}, AgentLoopAuthority("task-1", "human-1"), AgentLoopPolicy(max_iterations=3), "REJECTED_ITERATION_LIMIT"),
    ("context_read_limit_exceeded", {"context_requests": tuple({"executor_id": "list_files"} for _ in range(21))}, AgentLoopAuthority("task-1", "human-1"), AgentLoopPolicy(max_context_reads=20), "REJECTED_CONTEXT_READ_LIMIT"),
    ("patch_proposal_limit_exceeded", {"patch_proposal_count": 2}, AgentLoopAuthority("task-1", "human-1"), AgentLoopPolicy(max_patch_proposals=1), "REJECTED_PATCH_PROPOSAL_LIMIT"),
    ("patch_apply_without_approval", {"mode": AgentLoopMode.SUPERVISED_APPLY, "approval_packet": None}, AgentLoopAuthority("task-1", "human-1"), AgentLoopPolicy(), "REJECTED_MISSING_HUMAN_APPROVAL"),
    ("stale_approval", {"mode": AgentLoopMode.SUPERVISED_APPLY, "approval_packet": {"approval_expires_at_utc": "2000-01-01T00:00:00Z"}}, AgentLoopAuthority("task-1", "human-1"), AgentLoopPolicy(), "REJECTED_MISSING_HUMAN_APPROVAL"),
    ("proposal_hash_mismatch", {"mode": AgentLoopMode.SUPERVISED_APPLY, "approval_packet": {"proposal_hash": "sha256:bad"}}, AgentLoopAuthority("task-1", "human-1"), AgentLoopPolicy(), "REJECTED_MISSING_HUMAN_APPROVAL"),
    ("outside_r126_mutation", {"workspace_mutation_requested": True}, AgentLoopAuthority("task-1", "human-1"), AgentLoopPolicy(), "REJECTED_UNAPPROVED_MUTATION"),
    ("disallowed_test_command", {"test_command_id": "not_allowlisted"}, AgentLoopAuthority("task-1", "human-1"), AgentLoopPolicy(), "REJECTED_DISALLOWED_TEST_COMMAND"),
    ("missing_r127_receipt", {"test_run_result": {"accepted": True}}, AgentLoopAuthority("task-1", "human-1"), AgentLoopPolicy(), "REJECTED_TEST_RUNNER_RECEIPT"),
    ("model_tool_call", {"planner_output": {"tool_calls": [{"name": "write_file"}]}}, AgentLoopAuthority("task-1", "human-1"), AgentLoopPolicy(), "REJECTED_MODEL_TOOL_CALL"),
    ("model_requests_shell", {"planner_output": {"text": "run shell command"}}, AgentLoopAuthority("task-1", "human-1"), AgentLoopPolicy(), "REJECTED_MODEL_TOOL_CALL"),
    ("model_requests_network", {"planner_output": {"text": "fetch https://example.com"}}, AgentLoopAuthority("task-1", "human-1"), AgentLoopPolicy(), "REJECTED_MODEL_TOOL_CALL"),
    ("model_requests_arbitrary_file_write", {"planner_output": {"text": "write arbitrary file"}}, AgentLoopAuthority("task-1", "human-1"), AgentLoopPolicy(), "REJECTED_MODEL_TOOL_CALL"),
    ("direct_executor_dispatch", {"model_driven_executor_dispatch_requested": True}, AgentLoopAuthority("task-1", "human-1"), AgentLoopPolicy(), "REJECTED_MODEL_TOOL_CALL"),
    ("live_deepseek_no_gates", {"allow_live_llm_provider": True}, AgentLoopAuthority("task-1", "human-1"), AgentLoopPolicy(), "REJECTED_LIVE_LLM_PROVIDER_BY_DEFAULT"),
    ("secret_like_task", {}, AgentLoopAuthority("task-1", "human-1"), AgentLoopPolicy(), "REJECTED_SECRET_RISK"),
    ("raw_api_key_task", {}, AgentLoopAuthority("task-1", "human-1"), AgentLoopPolicy(), "REJECTED_SECRET_RISK"),
    ("arbitrary_command_string", {"raw_command": "pytest tests"}, AgentLoopAuthority("task-1", "human-1"), AgentLoopPolicy(), "REJECTED_ARBITRARY_COMMAND"),
    ("unbounded_task", {"task_text": "Keep going forever."}, AgentLoopAuthority("task-1", "human-1"), AgentLoopPolicy(), "REJECTED_UNBOUNDED_TASK"),
    ("production_claim", {"task_text": "Make this production ready."}, AgentLoopAuthority("task-1", "human-1"), AgentLoopPolicy(), "REJECTED_SCOPE_ESCALATION"),
    ("codex_equivalence_claim", {"task_text": "Become Codex equivalent."}, AgentLoopAuthority("task-1", "human-1"), AgentLoopPolicy(), "REJECTED_SCOPE_ESCALATION"),
    ("autonomous_mode_claim", {"task_text": "Run autonomously."}, AgentLoopAuthority("task-1", "human-1"), AgentLoopPolicy(), "REJECTED_SCOPE_ESCALATION"),
    ("missing_final_report", {}, AgentLoopAuthority("task-1", "human-1"), AgentLoopPolicy(require_final_report=False), "REJECTED_MISSING_FINAL_REPORT"),
    ("ledger_hash_mismatch", {"force_ledger_hash_mismatch": True}, AgentLoopAuthority("task-1", "human-1"), AgentLoopPolicy(), "REJECTED_LEDGER_HASH_MISMATCH"),
    ("replay_hash_mismatch", {"force_replay_hash_mismatch": True}, AgentLoopAuthority("task-1", "human-1"), AgentLoopPolicy(), "REJECTED_REPLAY_HASH_MISMATCH"),
    ("rollback_required_without_rollback", {"force_rollback_required": True}, AgentLoopAuthority("task-1", "human-1"), AgentLoopPolicy(), "ROLLBACK_REQUIRED"),
    ("autonomous_authority", {}, AgentLoopAuthority("task-1", "human-1", allow_autonomous_mode=True), AgentLoopPolicy(), "REJECTED_AUTONOMOUS_MODE"),
    ("patch_apply_disabled", {"mode": AgentLoopMode.SUPERVISED_APPLY}, AgentLoopAuthority("task-1", "human-1"), AgentLoopPolicy(allow_patch_apply=False), "REJECTED_UNAPPROVED_MUTATION"),
    ("test_runner_disabled", {"test_command_id": "test_runner"}, AgentLoopAuthority("task-1", "human-1"), AgentLoopPolicy(allow_test_runner=False), "REJECTED_TEST_RUNNER_BYPASS"),
]


def _fresh_approval_stub():
    return {
        "approval_expires_at_utc": (datetime.now(UTC) + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
    }


def _secret_like_task_text() -> str:
    return "Use " + "Authorization: " + "Bearer " + "abc.def"


def _raw_api_key_task_text() -> str:
    return "Use " + "sk-" + "abcdefghijklmnopqrstuvwxyz"


@pytest.mark.parametrize(("case_id", "overrides", "authority", "policy", "expected_code"), NEGATIVE_CASES)
def test_negative_cases_fail_closed(tmp_path: Path, case_id: str, overrides: dict, authority, policy: AgentLoopPolicy, expected_code: str):
    if case_id == "stale_approval":
        overrides = dict(overrides)
    if case_id == "proposal_hash_mismatch":
        overrides = dict(overrides)
        overrides["approval_packet"] = {**_fresh_approval_stub(), "proposal_hash": "sha256:bad"}
    if case_id == "secret_like_task":
        overrides = dict(overrides)
        overrides["task_text"] = _secret_like_task_text()
    if case_id == "raw_api_key_task":
        overrides = dict(overrides)
        overrides["task_text"] = _raw_api_key_task_text()

    result = run_agent_loop(_request(tmp_path, **overrides), authority=authority, policy=policy)

    assert result["accepted"] is False
    assert expected_code in result["rejection_codes"]
    assert result["autonomous_operation_performed"] is False
    assert result["model_driven_executor_dispatch_performed"] is False
    assert result["shell_execution_performed"] is False
    assert result["network_execution_performed"] is False
