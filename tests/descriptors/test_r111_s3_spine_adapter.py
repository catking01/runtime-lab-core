from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from runtime_lab.descriptors import spine_adapter


FIXTURE_ROOT = Path(__file__).parent / "fixtures"


def load_adapter_ready_descriptor() -> dict:
    payload = json.loads((FIXTURE_ROOT / "valid_minimal_descriptor.json").read_text(encoding="utf-8"))
    payload["executor_eligibility"] = {"executor_class": "validator_only", "requested": True}
    payload["governance_requirements"]["decision"] = "approved"
    payload["governance_requirements"]["decision_ref"] = "governance:r111-s3-local"
    payload["replay_binding"]["receipt_hash"] = "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    payload["replay_binding"]["ledger_ref"] = "ledger:r111-s3-local"
    payload["replay_binding"]["receipt_ref"] = "receipt:r111-s3-local"
    payload["validation_requirements"]["artifact_validation_bindings"] = ["artifact_expectation"]
    payload["kernel_binding"] = {
        "kernel": "Kernel 20",
        "coverage": [
            "Task",
            "Identity",
            "Authority",
            "State",
            "Transition",
            "Audit",
            "Executor",
            "Workspace",
            "Artifact",
            "Validation",
            "Governance",
            "Replay",
        ],
    }
    payload["minimal_spine_binding"] = {
        "fields": [
            "task_ref",
            "identity_binding",
            "authority_binding",
            "state_ref",
            "transition_intent",
            "audit_binding",
            "executor_eligibility",
            "workspace_boundary",
            "artifact_expectation",
            "validation_requirements",
            "governance_requirements",
            "replay_binding",
        ],
    }
    return payload


def test_valid_descriptor_produces_dry_run_spine_plan():
    result = spine_adapter.build_descriptor_spine_dry_run(load_adapter_ready_descriptor())

    assert result["accepted"] is True
    assert result["rejection_codes"] == []
    assert result["dry_run_plan"]["plan_kind"] == "descriptor_to_spine_dry_run"
    assert result["dry_run_plan"]["execution_mode"] == "dry_run_only"


def test_invalid_descriptor_is_rejected_before_adapter_output():
    payload = load_adapter_ready_descriptor()
    payload.pop("task_ref")

    result = spine_adapter.build_descriptor_spine_dry_run(payload)

    assert result["accepted"] is False
    assert "SPINE_CONTRACT_REJECTED" in result["rejection_codes"]
    assert result["dry_run_plan"] is None


def test_dry_run_plan_contains_task_identity():
    result = spine_adapter.build_descriptor_spine_dry_run(load_adapter_ready_descriptor())

    assert result["dry_run_plan"]["task"]["task_id"] == "task-001"
    assert result["dry_run_plan"]["task"]["descriptor_id"] == result["descriptor"]["descriptor_id"]
    assert result["dry_run_plan"]["task"]["descriptor_hash"] == result["descriptor"]["descriptor_hash"]


def test_dry_run_plan_contains_state_transition_audit_binding():
    result = spine_adapter.build_descriptor_spine_dry_run(load_adapter_ready_descriptor())

    assert result["dry_run_plan"]["state"]["state_id"] == "state-001"
    assert result["dry_run_plan"]["transition"]["type"] == "declare_output"
    assert result["dry_run_plan"]["transition"]["audit_binding_ref"] == "audit_binding"
    assert result["dry_run_plan"]["audit"]["required_audit_trail"] == ["descriptor_acceptance"]


def test_dry_run_plan_contains_governance_before_execution():
    result = spine_adapter.build_descriptor_spine_dry_run(load_adapter_ready_descriptor())
    admission_order = result["dry_run_plan"]["admission_order"]

    assert result["dry_run_plan"]["governance"]["decision"] == "approved"
    assert result["dry_run_plan"]["governance"]["decision_ref"] == "governance:r111-s3-local"
    assert result["dry_run_plan"]["governance"]["gate"] == "before_execution"
    assert admission_order.index("governance") < admission_order.index("executor")


def test_dry_run_plan_contains_executor_workspace_boundary():
    result = spine_adapter.build_descriptor_spine_dry_run(load_adapter_ready_descriptor())

    assert result["dry_run_plan"]["executor"]["requested"] is True
    assert result["dry_run_plan"]["executor"]["executor_class"] == "validator_only"
    assert result["dry_run_plan"]["workspace"]["mode"] == "single_root"
    assert result["dry_run_plan"]["workspace"]["allowed_roots"] == ["artifacts/"]


def test_dry_run_plan_contains_artifact_validation_binding():
    result = spine_adapter.build_descriptor_spine_dry_run(load_adapter_ready_descriptor())

    assert result["dry_run_plan"]["artifacts"][0]["logical_path"] == "artifacts/output.txt"
    assert result["dry_run_plan"]["validation"]["artifact_validation_bindings"] == ["artifact_expectation"]
    assert result["dry_run_plan"]["validation"]["required_validators"] == [
        "schema_shape",
        "canonicalization",
        "governance_presence",
    ]


def test_dry_run_plan_marks_replay_as_intent_not_proof():
    result = spine_adapter.build_descriptor_spine_dry_run(load_adapter_ready_descriptor())

    assert result["dry_run_plan"]["replay"]["status"] == "intent_only"
    assert result["dry_run_plan"]["replay"]["proof_status"] == "not_proven"
    assert result["dry_run_plan"]["replay"]["receipt_ref"] == "receipt:r111-s3-local"


@pytest.mark.parametrize(
    ("test_name", "mutate", "expected_code"),
    [
        (
            "adapter_rejects_execution_requested_descriptor",
            lambda payload: payload.update({"execution_request": {"mode": "execute"}}),
            "DRY_RUN_EXECUTION_REQUESTED",
        ),
        (
            "adapter_rejects_workspace_mutation_attempt",
            lambda payload: payload.update({"workspace_mutation": {"mutates": True}}),
            "DRY_RUN_WORKSPACE_MUTATION_FORBIDDEN",
        ),
        (
            "adapter_rejects_tool_invocation_attempt",
            lambda payload: payload.update({"tool_invocation": {"tool_name": "local_file_writer"}}),
            "DRY_RUN_TOOL_INVOCATION_FORBIDDEN",
        ),
        (
            "adapter_rejects_llm_invocation_attempt",
            lambda payload: payload.update({"llm_invocation": {"model": "gpt-5.5"}}),
            "DRY_RUN_LLM_INVOCATION_FORBIDDEN",
        ),
        (
            "adapter_rejects_missing_governance_decision",
            lambda payload: payload["governance_requirements"].pop("decision"),
            "DRY_RUN_GOVERNANCE_DECISION_MISSING",
        ),
        (
            "adapter_rejects_missing_transition_audit_binding",
            lambda payload: payload.pop("audit_binding"),
            "DRY_RUN_TRANSITION_AUDIT_BINDING_MISSING",
        ),
        (
            "adapter_rejects_missing_artifact_validation_binding",
            lambda payload: payload["validation_requirements"].pop("artifact_validation_bindings"),
            "DRY_RUN_ARTIFACT_VALIDATION_BINDING_MISSING",
        ),
        (
            "adapter_rejects_replay_claimed_as_proof",
            lambda payload: payload["replay_binding"].update({"proof_status": "proven"}),
            "DRY_RUN_REPLAY_PROOF_FORBIDDEN",
        ),
    ],
)
def test_negative_adapter_cases_fail_closed(test_name, mutate, expected_code):
    payload = copy.deepcopy(load_adapter_ready_descriptor())
    mutate(payload)

    result = spine_adapter.build_descriptor_spine_dry_run(payload)

    assert result["accepted"] is False, test_name
    assert expected_code in result["rejection_codes"], test_name
    assert result["dry_run_plan"] is None, test_name


def test_adapter_output_is_deterministic():
    payload = load_adapter_ready_descriptor()

    first = spine_adapter.build_descriptor_spine_dry_run(payload)
    second = spine_adapter.build_descriptor_spine_dry_run(copy.deepcopy(payload))

    assert first == second
