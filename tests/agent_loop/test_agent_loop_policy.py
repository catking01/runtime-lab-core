from __future__ import annotations

from pathlib import Path

from runtime_lab.agent_loop.models import AgentLoopAuthority, AgentLoopMode, AgentLoopPolicy, AgentLoopRequest
from runtime_lab.agent_loop.policy import validate_agent_loop_request


def _request(tmp_path: Path, **overrides):
    values = {
        "task_id": "task-1",
        "run_id": "run-1",
        "mode": AgentLoopMode.DRY_RUN,
        "base_commit": "abc123",
        "workspace_root": tmp_path,
        "run_artifact_dir": tmp_path / "run",
        "task_text": "Make a supervised local patch proposal.",
        "target_files": ("a.txt",),
        "context_requests": (),
    }
    values.update(overrides)
    return AgentLoopRequest(**values)


def test_valid_request_is_accepted(tmp_path: Path):
    result = validate_agent_loop_request(_request(tmp_path), authority=AgentLoopAuthority("task-1", "human-1"), policy=AgentLoopPolicy())

    assert result["accepted"] is True
    assert result["rejection_codes"] == []


def test_missing_authority_rejected(tmp_path: Path):
    result = validate_agent_loop_request(_request(tmp_path), authority=None, policy=AgentLoopPolicy())

    assert result["accepted"] is False
    assert result["rejection_codes"] == ["REJECTED_MISSING_AUTHORITY"]


def test_unbounded_task_rejected(tmp_path: Path):
    request = _request(tmp_path, task_text="Keep iterating forever until everything is perfect.")

    result = validate_agent_loop_request(request, authority=AgentLoopAuthority("task-1", "human-1"), policy=AgentLoopPolicy())

    assert result["accepted"] is False
    assert result["rejection_codes"] == ["REJECTED_UNBOUNDED_TASK"]


def test_autonomous_claim_rejected(tmp_path: Path):
    request = _request(tmp_path, task_text="Run as an autonomous coding agent.")

    result = validate_agent_loop_request(request, authority=AgentLoopAuthority("task-1", "human-1"), policy=AgentLoopPolicy())

    assert result["accepted"] is False
    assert result["rejection_codes"] == ["REJECTED_SCOPE_ESCALATION"]


def test_policy_rejects_live_provider_by_default_override(tmp_path: Path):
    request = _request(tmp_path, allow_live_llm_provider=True)

    result = validate_agent_loop_request(request, authority=AgentLoopAuthority("task-1", "human-1"), policy=AgentLoopPolicy())

    assert result["accepted"] is False
    assert result["rejection_codes"] == ["REJECTED_LIVE_LLM_PROVIDER_BY_DEFAULT"]


def test_policy_requires_iteration_limit(tmp_path: Path):
    result = validate_agent_loop_request(_request(tmp_path), authority=AgentLoopAuthority("task-1", "human-1"), policy=AgentLoopPolicy(max_iterations=0))

    assert result["accepted"] is False
    assert result["rejection_codes"] == ["REJECTED_ITERATION_LIMIT"]
