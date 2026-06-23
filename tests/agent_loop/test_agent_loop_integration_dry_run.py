from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
import json

from runtime_lab.agent_loop.models import AgentLoopAuthority, AgentLoopMode, AgentLoopPolicy, AgentLoopRequest
from runtime_lab.agent_loop.supervisor import run_agent_loop
from runtime_lab.patch_apply.receipts import canonical_hash
from runtime_lab.test_runner.models import CompletedTestProcess


def _proposal_request(base_commit: str):
    return {
        "proposal_id": "proposal-1",
        "base_commit": base_commit,
        "target_files": ["a.txt"],
        "unified_diff": "--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n-hello\n+hello r128\n",
        "risk_class": "low",
        "change_summary": "Update a.txt",
        "validation_plan": ["run allowlisted test_runner"],
        "rollback_plan": "Restore a.txt",
        "human_approval_required": True,
        "apply_allowed": False,
        "apply_performed": False,
        "workspace_mutation_performed": False,
        "test_execution_allowed": False,
        "test_execution_performed": False,
    }


def _approval_for(proposal: dict, workspace_root: Path):
    return {
        "approval_id": "approval-1",
        "approval_version": "patch_apply_approval.v1",
        "approved_by_actor_id": "human-1",
        "approval_created_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "approval_expires_at_utc": (datetime.now(UTC) + timedelta(minutes=5)).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "proposal_id": proposal["proposal_id"],
        "proposal_hash": canonical_hash(proposal),
        "base_commit": proposal["base_commit"],
        "approved_target_files": proposal["target_files"],
        "approved_unified_diff_hash": proposal["unified_diff_hash"],
        "approved_risk_class": proposal["risk_class"],
        "authority_scope": "single_patch_apply_transaction",
        "workspace_root_hash": canonical_hash(str(workspace_root.resolve())),
        "max_files_allowed": 1,
        "max_bytes_allowed": 200_000,
        "rollback_required": True,
        "human_confirmation_text": f"I approve proposal {proposal['proposal_id']} for one local transaction.",
        "approval_nonce": "nonce-1",
        "approval_signature_or_local_attestation": "local-human-attestation",
    }


def test_dry_run_loop_creates_proposal_receipt_final_report_ledger_and_replay(tmp_path: Path):
    (tmp_path / "a.txt").write_text("hello\n", encoding="utf-8")
    request = AgentLoopRequest(
        task_id="task-1",
        run_id="run-1",
        mode=AgentLoopMode.DRY_RUN,
        base_commit="abc123",
        workspace_root=tmp_path,
        run_artifact_dir=tmp_path / "run",
        task_text="Create a supervised local patch proposal.",
        target_files=("a.txt",),
        context_requests=({"executor_id": "read_file", "requested_path": "a.txt"},),
        patch_proposal_request=_proposal_request("abc123"),
    )

    result = run_agent_loop(request, authority=AgentLoopAuthority("task-1", "human-1"), policy=AgentLoopPolicy())

    assert result["accepted"] is True
    assert result["mode"] == "DRY_RUN"
    assert result["patch_apply_performed"] is False
    assert result["test_execution_performed"] is False
    assert result["context_receipts"]
    assert result["patch_proposal_receipt"]["receipt_hash"].startswith("sha256:")
    assert result["agent_loop_receipt"]["receipt_hash"].startswith("sha256:")
    assert result["ledger_events"][-1]["event_hash"].startswith("sha256:")
    assert result["replay_manifest"]["replay_manifest_hash"].startswith("sha256:")
    assert Path(result["final_report_path"]).is_file()
    assert Path(result["replay_manifest_path"]).is_file()


def test_supervised_apply_loop_uses_r126_apply_and_r127_test_runner(tmp_path: Path):
    (tmp_path / "a.txt").write_text("hello\n", encoding="utf-8")
    proposal_request = _proposal_request("abc123")
    test_results = []

    def fake_test_executor(invocation):
        test_results.append(invocation)
        return CompletedTestProcess(exit_code=0, stdout=b"ok\n", stderr=b"")

    dry_run = run_agent_loop(
        AgentLoopRequest(
            task_id="task-1",
            run_id="run-prepare",
            mode=AgentLoopMode.DRY_RUN,
            base_commit="abc123",
            workspace_root=tmp_path,
            run_artifact_dir=tmp_path / "prepare",
            task_text="Create a supervised local patch proposal.",
            target_files=("a.txt",),
            patch_proposal_request=proposal_request,
        ),
        authority=AgentLoopAuthority("task-1", "human-1"),
        policy=AgentLoopPolicy(),
    )
    proposal = json.loads(Path(dry_run["patch_proposal_artifact_path"]).read_text(encoding="utf-8"))
    approval = _approval_for(proposal, tmp_path)

    result = run_agent_loop(
        AgentLoopRequest(
            task_id="task-1",
            run_id="run-apply",
            mode=AgentLoopMode.SUPERVISED_APPLY,
            base_commit="abc123",
            workspace_root=tmp_path,
            run_artifact_dir=tmp_path / "apply",
            task_text="Apply one human-approved local patch and run allowlisted tests.",
            target_files=("a.txt",),
            patch_proposal_request=proposal_request,
            approval_packet=approval,
            test_command_id="test_runner",
            test_runner_executor=fake_test_executor,
        ),
        authority=AgentLoopAuthority("task-1", "human-1"),
        policy=AgentLoopPolicy(),
    )

    assert result["accepted"] is True
    assert result["mode"] == "SUPERVISED_APPLY"
    assert result["patch_apply_performed"] is True
    assert result["patch_apply_receipt"]["receipt_hash"].startswith("sha256:")
    assert result["test_execution_performed"] is True
    assert result["test_runner_receipts"][0]["receipt_hash"].startswith("sha256:")
    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "hello r128\n"
    assert test_results and test_results[0]["shell"] is False
