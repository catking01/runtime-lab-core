from __future__ import annotations

from pathlib import Path

from runtime_lab.agent_loop.authority import evaluate_authority
from runtime_lab.agent_loop.models import AgentLoopAuthority, AgentLoopMode, AgentLoopPolicy, AgentLoopRequest


def _request(tmp_path: Path, mode=AgentLoopMode.SUPERVISED_APPLY):
    return AgentLoopRequest(
        task_id="task-1",
        run_id="run-1",
        mode=mode,
        base_commit="abc123",
        workspace_root=tmp_path,
        run_artifact_dir=tmp_path / "run",
        task_text="Apply one approved patch.",
        target_files=("a.txt",),
    )


def test_authority_decision_accepts_matching_task_and_mode(tmp_path: Path):
    decision = evaluate_authority(_request(tmp_path), authority=AgentLoopAuthority("task-1", "human-1"), policy=AgentLoopPolicy())

    assert decision["accepted"] is True
    assert decision["authority_decision_hash"].startswith("sha256:")
    assert decision["supervision_required"] is True


def test_authority_decision_rejects_task_mismatch(tmp_path: Path):
    decision = evaluate_authority(_request(tmp_path), authority=AgentLoopAuthority("other", "human-1"), policy=AgentLoopPolicy())

    assert decision["accepted"] is False
    assert decision["rejection_codes"] == ["REJECTED_MISSING_AUTHORITY"]


def test_authority_decision_rejects_unallowed_mode(tmp_path: Path):
    authority = AgentLoopAuthority("task-1", "human-1", allowed_modes=(AgentLoopMode.DRY_RUN,))

    decision = evaluate_authority(_request(tmp_path, mode=AgentLoopMode.SUPERVISED_APPLY), authority=authority, policy=AgentLoopPolicy())

    assert decision["accepted"] is False
    assert decision["rejection_codes"] == ["REJECTED_SCOPE_ESCALATION"]
