"""Supervised local agent-loop orchestration for R128.

The supervisor coordinates bounded context reads, patch proposal artifacts,
human-approved patch application, allowlisted tests, ledger events, replay
manifests, and final receipts while preserving explicit non-claim boundaries.
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from runtime_lab.agent_loop.authority import evaluate_authority
from runtime_lab.agent_loop.ledger import build_ledger_events, verify_ledger_events
from runtime_lab.agent_loop.models import AgentLoopAuthority, AgentLoopMode, AgentLoopPolicy, AgentLoopRequest
from runtime_lab.agent_loop.plan import create_deterministic_plan, policy_snapshot
from runtime_lab.agent_loop.policy import validate_agent_loop_request
from runtime_lab.agent_loop.receipts import build_agent_loop_receipt, canonical_hash
from runtime_lab.agent_loop.replay import build_replay_manifest
from runtime_lab.agent_loop.state_machine import build_transition_log, verify_transition_log
from runtime_lab.patch_apply import PatchApplyPolicy, apply_patch_transaction
from runtime_lab.patch_proposal import create_patch_proposal_artifact
from runtime_lab.repo_context import RepoContextAuthority, execute_repo_context
from runtime_lab.test_runner import TestRunRequest, run_allowlisted_test


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, value: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return canonical_hash(value)


def _failure(request: AgentLoopRequest, codes: list[str], *, authority_hash: str | None = None) -> dict[str, Any]:
    return {
        "accepted": False,
        "rejection_codes": list(dict.fromkeys(codes)),
        "task_id": request.task_id,
        "run_id": request.run_id,
        "mode": request.mode.value,
        "authority_decision_hash": authority_hash,
        "patch_apply_performed": False,
        "test_execution_performed": False,
        "autonomous_operation_performed": False,
        "model_driven_executor_dispatch_performed": False,
        "shell_execution_performed": False,
        "network_execution_performed": False,
        "context_receipts": [],
        "patch_proposal_receipt": None,
        "patch_apply_receipt": None,
        "test_runner_receipts": [],
        "ledger_events": [],
        "replay_manifest": None,
        "agent_loop_receipt": None,
    }


def _transition_pairs(mode: AgentLoopMode, *, test_requested: bool) -> list[tuple[str, str]]:
    pairs = [
        ("TASK_RECEIVED", "check_authority"),
        ("AUTHORITY_CHECKED", "create_plan"),
        ("PLAN_CREATED", "read_context"),
        ("CONTEXT_READ", "create_patch_proposal"),
    ]
    if mode == AgentLoopMode.DRY_RUN:
        pairs.append(("PATCH_PROPOSAL_CREATED", "write_final_artifact"))
    else:
        pairs.extend(
            [
                ("PATCH_PROPOSAL_CREATED", "require_human_approval"),
                ("HUMAN_APPROVAL_REQUIRED", "verify_human_approval"),
                ("HUMAN_APPROVAL_VERIFIED", "start_patch_apply"),
                ("PATCH_APPLY_TRANSACTION_STARTED", "complete_patch_apply"),
            ]
        )
        if test_requested:
            pairs.extend(
                [
                    ("PATCH_APPLY_TRANSACTION_COMPLETED", "request_tests"),
                    ("ALLOWLISTED_TESTS_REQUESTED", "complete_tests"),
                    ("ALLOWLISTED_TESTS_COMPLETED", "write_final_artifact"),
                ]
            )
        else:
            pairs.append(("PATCH_APPLY_TRANSACTION_COMPLETED", "request_tests"))
            pairs.append(("ALLOWLISTED_TESTS_REQUESTED", "complete_tests"))
            pairs.append(("ALLOWLISTED_TESTS_COMPLETED", "write_final_artifact"))
    pairs.extend(
        [
            ("FINAL_ARTIFACT_WRITTEN", "verify_receipts"),
            ("RECEIPTS_VERIFIED", "seal_ledger"),
            ("LEDGER_SEALED_LOCALLY", "done"),
        ]
    )
    return pairs


def _run_context_requests(request: AgentLoopRequest) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    authority = RepoContextAuthority(task_id=request.task_id, allowed_executors=("list_files", "read_file", "grep"))
    results: list[dict[str, Any]] = []
    receipts: list[dict[str, Any]] = []
    for context_request in request.context_requests:
        executor_id = str(context_request["executor_id"])
        kwargs = {key: value for key, value in context_request.items() if key != "executor_id"}
        result = execute_repo_context(
            executor_id=executor_id,
            workspace_root=request.workspace_root,
            authority=authority,
            **kwargs,
        )
        results.append(result)
        if not result.get("accepted"):
            continue
        receipts.append(result["receipt"])
    return results, receipts


def _proposal_artifact_path(request: AgentLoopRequest) -> Path | None:
    if not request.patch_proposal_request:
        return None
    proposal_id = str(request.patch_proposal_request.get("proposal_id", "proposal-1"))
    return request.run_artifact_dir / "patch_proposals" / f"{proposal_id}.json"


def _create_or_load_proposal(request: AgentLoopRequest) -> dict[str, Any]:
    artifact_path = _proposal_artifact_path(request)
    approved_hash = None
    if request.approval_packet:
        approved_hash = request.approval_packet.get("proposal_hash")
    if artifact_path is not None and artifact_path.exists():
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        if not approved_hash or canonical_hash(artifact) == approved_hash:
            return {
                "accepted": True,
                "artifact_path": str(artifact_path),
                "artifact_hash": canonical_hash(artifact),
                "receipt": artifact["receipt"],
                "ledger_event": {
                    "event_type": "patch_proposal.artifact_reused",
                    "receipt_hash": artifact["receipt"]["receipt_hash"],
                    "artifact_only": True,
                },
            }
    if approved_hash and request.patch_proposal_request:
        proposal_id = str(request.patch_proposal_request.get("proposal_id", "proposal-1"))
        for candidate_path in sorted(request.run_artifact_dir.parent.glob(f"*/patch_proposals/{proposal_id}.json")):
            artifact = json.loads(candidate_path.read_text(encoding="utf-8"))
            if canonical_hash(artifact) != approved_hash:
                continue
            return {
                "accepted": True,
                "artifact_path": str(candidate_path),
                "artifact_hash": canonical_hash(artifact),
                "receipt": artifact["receipt"],
                "ledger_event": {
                    "event_type": "patch_proposal.approved_artifact_loaded",
                    "receipt_hash": artifact["receipt"]["receipt_hash"],
                    "artifact_only": True,
                },
            }
    if artifact_path is not None and artifact_path.exists():
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        return {
            "accepted": True,
            "artifact_path": str(artifact_path),
            "artifact_hash": canonical_hash(artifact),
            "receipt": artifact["receipt"],
            "ledger_event": {
                "event_type": "patch_proposal.artifact_reused",
                "receipt_hash": artifact["receipt"]["receipt_hash"],
                "artifact_only": True,
            },
        }
    if not request.patch_proposal_request:
        return {"accepted": False, "rejection_codes": ["REJECTED_PATCH_PROPOSAL_REQUIRED"]}
    return create_patch_proposal_artifact(
        request.patch_proposal_request,
        workspace_root=request.workspace_root,
        artifact_dir=request.run_artifact_dir / "patch_proposals",
    )


def _run_patch_apply(request: AgentLoopRequest, proposal_artifact_path: str) -> dict[str, Any]:
    proposal = json.loads(Path(proposal_artifact_path).read_text(encoding="utf-8"))
    return apply_patch_transaction(
        {
            "transaction_id": f"{request.run_id}-patch-apply",
            "proposal": proposal,
            "approval_packet": request.approval_packet,
            "base_commit": request.base_commit,
        },
        workspace_root=request.workspace_root,
        transaction_dir=request.run_artifact_dir / "patch_apply",
        policy=PatchApplyPolicy(),
    )


def _run_test(request: AgentLoopRequest) -> dict[str, Any] | None:
    if not request.test_command_id:
        return None
    test_request = TestRunRequest(
        command_id=request.test_command_id,
        workspace_root=request.workspace_root,
        cwd_relative=".",
        timeout_seconds=120,
        max_stdout_bytes=200_000,
        max_stderr_bytes=200_000,
        max_total_output_bytes=400_000,
    )
    return run_allowlisted_test(test_request, executor=request.test_runner_executor)


def run_agent_loop(
    request: AgentLoopRequest,
    *,
    authority: AgentLoopAuthority | None,
    policy: AgentLoopPolicy | None = None,
) -> dict[str, Any]:
    """Run one bounded supervised or dry-run local agent-loop request."""

    policy = policy or AgentLoopPolicy()
    validation = validate_agent_loop_request(request=request, authority=authority, policy=policy)
    if not validation["accepted"]:
        return _failure(request, validation["rejection_codes"], authority_hash=validation["authority_decision_hash"])

    request.run_artifact_dir.mkdir(parents=True, exist_ok=True)
    authority_result = evaluate_authority(request=request, authority=authority, policy=policy)
    plan = request.planner_output or create_deterministic_plan(request)
    if plan.get("tool_calls"):
        return _failure(request, ["REJECTED_MODEL_TOOL_CALL"], authority_hash=authority_result["authority_decision_hash"])

    transition_log = build_transition_log(
        transitions=_transition_pairs(request.mode, test_requested=bool(request.test_command_id)),
        run_id=request.run_id,
    )
    if not verify_transition_log(transition_log):
        return _failure(request, ["REJECTED_TRANSITION_HASH_MISMATCH"], authority_hash=authority_result["authority_decision_hash"])
    state_transition_hash = transition_log[-1]["transition_hash"]

    context_results, context_receipts = _run_context_requests(request)
    if any(not result.get("accepted") for result in context_results):
        codes = [code for result in context_results for code in result.get("rejection_codes", [])]
        return _failure(request, codes or ["REJECTED_CONTEXT_READ"], authority_hash=authority_result["authority_decision_hash"])

    proposal_result = _create_or_load_proposal(request)
    if not proposal_result.get("accepted"):
        return _failure(
            request,
            list(proposal_result.get("rejection_codes", ["REJECTED_PATCH_PROPOSAL_REQUIRED"])),
            authority_hash=authority_result["authority_decision_hash"],
        )

    patch_apply_result: dict[str, Any] | None = None
    test_result: dict[str, Any] | None = None
    if request.mode == AgentLoopMode.SUPERVISED_APPLY:
        patch_apply_result = _run_patch_apply(request, proposal_result["artifact_path"])
        if not patch_apply_result.get("accepted"):
            return _failure(
                request,
                list(patch_apply_result.get("rejection_codes", ["REJECTED_UNAPPROVED_MUTATION"])),
                authority_hash=authority_result["authority_decision_hash"],
            )
        test_result = _run_test(request)
        if test_result is not None and not test_result.get("accepted"):
            return _failure(
                request,
                list(test_result.get("rejection_codes", ["REJECTED_TEST_RUNNER_RECEIPT"])),
                authority_hash=authority_result["authority_decision_hash"],
            )

    executor_receipt_hashes = [receipt["receipt_hash"] for receipt in context_receipts]
    executor_receipt_hashes.append(proposal_result["receipt"]["receipt_hash"])
    if patch_apply_result is not None:
        executor_receipt_hashes.append(patch_apply_result["receipt"]["receipt_hash"])
    test_runner_receipts: list[dict[str, Any]] = []
    if test_result is not None:
        test_runner_receipts.append(test_result["receipt"])
        executor_receipt_hashes.append(test_result["receipt"]["receipt_hash"])

    artifact_hashes = {"patch_proposal": proposal_result["artifact_hash"]}
    ledger_events = build_ledger_events(run_id=request.run_id, receipt_hashes=executor_receipt_hashes)
    if not verify_ledger_events(ledger_events):
        return _failure(request, ["REJECTED_LEDGER_HASH_MISMATCH"], authority_hash=authority_result["authority_decision_hash"])
    ledger_hash = ledger_events[-1]["event_hash"] if ledger_events else "GENESIS"

    replay_manifest = build_replay_manifest(
        run_id=request.run_id,
        base_commit=request.base_commit,
        state_transition_hash=state_transition_hash,
        inputs={
            "task_id": request.task_id,
            "mode": request.mode.value,
            "target_files": list(request.target_files),
            "context_request_count": len(request.context_requests),
            "patch_proposal_artifact_path": proposal_result["artifact_path"],
        },
        artifact_hashes=artifact_hashes,
        receipt_hashes=executor_receipt_hashes,
        ledger_tail_hash=ledger_hash,
    )
    replay_path = request.run_artifact_dir / "replay_manifest.json"
    artifact_hashes["replay_manifest"] = _write_json(replay_path, replay_manifest)

    final_report = {
        "schema_version": "1.0",
        "report_version": "agent_loop_final_report.v0",
        "milestone": "R128_SUPERVISED_LOCAL_AGENT_LOOP_V0_LOCAL_VALIDATION",
        "task_id": request.task_id,
        "run_id": request.run_id,
        "mode": request.mode.value,
        "base_commit": request.base_commit,
        "final_result": "SUCCESS",
        "created_at_utc": _utc_now(),
        "plan": plan,
        "transition_log": transition_log,
        "context_receipt_hashes": [receipt["receipt_hash"] for receipt in context_receipts],
        "patch_proposal_receipt_hash": proposal_result["receipt"]["receipt_hash"],
        "patch_apply_receipt_hash": patch_apply_result["receipt"]["receipt_hash"] if patch_apply_result else None,
        "test_runner_receipt_hashes": [receipt["receipt_hash"] for receipt in test_runner_receipts],
        "ledger_hash": ledger_hash,
        "replay_hash": replay_manifest["replay_manifest_hash"],
        "non_claims": policy.non_claims,
    }
    final_report_path = request.run_artifact_dir / "final_report.json"
    artifact_hashes["final_report"] = _write_json(final_report_path, final_report)

    policy_hash = canonical_hash(policy_snapshot(policy))
    agent_loop_receipt = build_agent_loop_receipt(
        task_id=request.task_id,
        run_id=request.run_id,
        mode=request.mode.value,
        base_commit=request.base_commit,
        workspace_root_hash=canonical_hash(str(request.workspace_root.resolve())),
        policy_hash=policy_hash,
        authority_decision_hash=authority_result["authority_decision_hash"],
        state_transition_hash_chain=state_transition_hash,
        executor_receipt_hashes=executor_receipt_hashes,
        artifact_hashes=artifact_hashes,
        final_result="SUCCESS",
        non_claims=policy.non_claims,
    )
    receipt_path = request.run_artifact_dir / "agent_loop_receipt.json"
    _write_json(receipt_path, agent_loop_receipt)

    ledger_events = build_ledger_events(
        run_id=request.run_id,
        receipt_hashes=executor_receipt_hashes + [agent_loop_receipt["receipt_hash"]],
    )

    return {
        "accepted": True,
        "rejection_codes": [],
        "task_id": request.task_id,
        "run_id": request.run_id,
        "mode": request.mode.value,
        "patch_apply_performed": bool(patch_apply_result and patch_apply_result.get("apply_performed")),
        "test_execution_performed": bool(test_result and test_result.get("test_execution_started")),
        "autonomous_operation_performed": False,
        "model_driven_executor_dispatch_performed": False,
        "shell_execution_performed": False,
        "network_execution_performed": False,
        "context_receipts": context_receipts,
        "patch_proposal_receipt": proposal_result["receipt"],
        "patch_proposal_artifact_path": proposal_result["artifact_path"],
        "patch_apply_receipt": patch_apply_result["receipt"] if patch_apply_result else None,
        "test_runner_receipts": test_runner_receipts,
        "agent_loop_receipt": agent_loop_receipt,
        "ledger_events": ledger_events,
        "replay_manifest": replay_manifest,
        "final_report_path": str(final_report_path),
        "replay_manifest_path": str(replay_path),
        "policy_hash": policy_hash,
        "authority_decision_hash": authority_result["authority_decision_hash"],
    }
