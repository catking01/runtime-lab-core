from __future__ import annotations

from pathlib import Path

from runtime_lab.agent_loop.models import AgentLoopAuthority, AgentLoopMode, AgentLoopPolicy, AgentLoopRequest
from runtime_lab.agent_loop.supervisor import run_agent_loop


def test_dry_run_requires_final_report_when_policy_requires_it(tmp_path: Path):
    (tmp_path / "a.txt").write_text("hello\n", encoding="utf-8")
    request = AgentLoopRequest(
        task_id="task-1",
        run_id="run-1",
        mode=AgentLoopMode.DRY_RUN,
        base_commit="abc123",
        workspace_root=tmp_path,
        run_artifact_dir=tmp_path / "run",
        task_text="Create a supervised proposal.",
        target_files=("a.txt",),
        patch_proposal_request={
            "proposal_id": "proposal-1",
            "base_commit": "abc123",
            "target_files": ["a.txt"],
            "unified_diff": "--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n-hello\n+hello r128\n",
            "risk_class": "low",
            "change_summary": "Update a.txt",
            "validation_plan": ["agent_loop dry run"],
            "rollback_plan": "Restore a.txt",
            "human_approval_required": True,
            "apply_allowed": False,
            "apply_performed": False,
            "workspace_mutation_performed": False,
            "test_execution_allowed": False,
            "test_execution_performed": False,
        },
    )

    result = run_agent_loop(request, authority=AgentLoopAuthority("task-1", "human-1"), policy=AgentLoopPolicy(require_final_report=False))

    assert result["accepted"] is False
    assert result["rejection_codes"] == ["REJECTED_MISSING_FINAL_REPORT"]


def test_model_tool_call_is_rejected_before_execution(tmp_path: Path):
    request = AgentLoopRequest(
        task_id="task-1",
        run_id="run-1",
        mode=AgentLoopMode.DRY_RUN,
        base_commit="abc123",
        workspace_root=tmp_path,
        run_artifact_dir=tmp_path / "run",
        task_text="Create a supervised proposal.",
        planner_output={"text": "plan", "tool_calls": [{"name": "shell", "arguments": "ls"}]},
    )

    result = run_agent_loop(request, authority=AgentLoopAuthority("task-1", "human-1"), policy=AgentLoopPolicy())

    assert result["accepted"] is False
    assert result["rejection_codes"] == ["REJECTED_MODEL_TOOL_CALL"]
    assert result["model_driven_executor_dispatch_performed"] is False
