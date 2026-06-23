from __future__ import annotations

from pathlib import Path

from runtime_lab.agent_loop.models import AgentLoopAuthority, AgentLoopMode, AgentLoopPolicy, AgentLoopRequest


def test_policy_defaults_are_supervised_and_bounded():
    policy = AgentLoopPolicy()

    assert policy.max_iterations == 3
    assert policy.max_context_reads == 20
    assert policy.max_patch_proposals == 1
    assert policy.max_patch_apply_transactions == 1
    assert policy.max_test_runs == 2
    assert policy.allow_live_llm_provider is False
    assert policy.allow_patch_apply is True
    assert policy.allow_test_runner is True
    assert policy.require_human_approval_for_apply is True
    assert policy.require_receipts is True
    assert policy.require_ledger_events is True
    assert policy.require_replay_bundle is True
    assert policy.default_decision == "REJECT_FAIL_CLOSED"


def test_authority_is_narrow_by_default():
    authority = AgentLoopAuthority(task_id="task-1", actor_id="human-1")

    assert authority.supervision_required is True
    assert authority.allow_autonomous_mode is False
    assert authority.allow_model_driven_executor_dispatch is False
    assert authority.allows_mode(AgentLoopMode.DRY_RUN) is True
    assert authority.allows_mode(AgentLoopMode.SUPERVISED_APPLY) is True


def test_request_normalizes_paths_and_targets(tmp_path: Path):
    request = AgentLoopRequest(
        task_id="task-1",
        run_id="run-1",
        mode=AgentLoopMode.DRY_RUN,
        base_commit="abc123",
        workspace_root=tmp_path,
        run_artifact_dir=tmp_path / "artifacts",
        task_text="Change one file under supervision.",
        target_files=["a.txt"],
        context_requests=[{"executor_id": "read_file", "requested_path": "a.txt"}],
    )

    assert request.workspace_root == tmp_path
    assert request.run_artifact_dir == tmp_path / "artifacts"
    assert request.target_files == ("a.txt",)
    assert request.context_requests == ({"executor_id": "read_file", "requested_path": "a.txt"},)


def test_non_claims_are_explicitly_false():
    policy = AgentLoopPolicy()

    assert policy.non_claims["autonomous_agent"] is False
    assert policy.non_claims["general_coding_agent"] is False
    assert policy.non_claims["codex_equivalent"] is False
    assert policy.non_claims["claude_code_equivalent"] is False
    assert policy.non_claims["remote_sealed_pass"] is False
