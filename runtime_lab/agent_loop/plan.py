from __future__ import annotations

from dataclasses import asdict
from typing import Any

from runtime_lab.agent_loop.models import AgentLoopRequest
from runtime_lab.agent_loop.receipts import canonical_hash


def create_deterministic_plan(request: AgentLoopRequest) -> dict[str, Any]:
    plan = {
        "plan_version": "agent_loop_plan.v0",
        "task_id": request.task_id,
        "run_id": request.run_id,
        "mode": request.mode.value,
        "target_files": list(request.target_files),
        "context_request_count": len(request.context_requests),
        "patch_proposal_requested": request.patch_proposal_request is not None,
        "test_command_id": request.test_command_id,
        "tool_calls": [],
        "model_generated": False,
        "planner_kind": "deterministic_local_policy",
    }
    plan["plan_hash"] = canonical_hash(plan)
    return plan


def policy_snapshot(value: Any) -> dict[str, Any]:
    snapshot = asdict(value)
    for key, item in list(snapshot.items()):
        if hasattr(item, "value"):
            snapshot[key] = item.value
    return snapshot
