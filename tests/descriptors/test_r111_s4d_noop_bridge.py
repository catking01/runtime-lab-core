from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from runtime_lab.descriptors import noop_bridge


FIXTURE_ROOT = Path(__file__).parent / "fixtures"


def load_bridge_ready_descriptor() -> dict:
    payload = json.loads((FIXTURE_ROOT / "valid_minimal_descriptor.json").read_text(encoding="utf-8"))
    payload["executor_eligibility"] = {"executor_class": "validator_only", "requested": True}
    payload["governance_requirements"]["decision"] = "approved"
    payload["governance_requirements"]["decision_ref"] = "governance:r111-s4d-local"
    payload["replay_binding"]["receipt_hash"] = "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
    payload["replay_binding"]["ledger_ref"] = "ledger:r111-s4d-local"
    payload["replay_binding"]["receipt_ref"] = "receipt:r111-s4d-local"
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


def test_valid_descriptor_produces_noop_bridge_receipt():
    result = noop_bridge.build_descriptor_spine_noop_bridge(load_bridge_ready_descriptor())

    assert result["accepted"] is True
    assert result["rejection_codes"] == []
    assert result["noop_bridge_receipt"]["bridge_kind"] == "descriptor_to_spine_noop_execution_bridge"


def test_noop_bridge_receipt_contains_task_identity():
    result = noop_bridge.build_descriptor_spine_noop_bridge(load_bridge_ready_descriptor())

    assert result["noop_bridge_receipt"]["task"]["task_id"] == "task-001"
    assert result["noop_bridge_receipt"]["task"]["descriptor_id"] == result["descriptor"]["descriptor_id"]


def test_noop_bridge_receipt_contains_state_transition_audit():
    result = noop_bridge.build_descriptor_spine_noop_bridge(load_bridge_ready_descriptor())

    assert result["noop_bridge_receipt"]["state"]["state_id"] == "state-001"
    assert result["noop_bridge_receipt"]["transition"]["execution_mode"] == "noop_only"
    assert result["noop_bridge_receipt"]["audit"]["required_audit_trail"] == ["descriptor_acceptance"]


def test_noop_bridge_receipt_contains_governance_reference():
    result = noop_bridge.build_descriptor_spine_noop_bridge(load_bridge_ready_descriptor())

    assert result["noop_bridge_receipt"]["governance"]["decision"] == "approved"
    assert result["noop_bridge_receipt"]["governance"]["decision_ref"] == "governance:r111-s4d-local"


def test_noop_bridge_receipt_contains_artifact_validation_binding():
    result = noop_bridge.build_descriptor_spine_noop_bridge(load_bridge_ready_descriptor())

    assert result["noop_bridge_receipt"]["validation"]["artifact_validation_bindings"] == ["artifact_expectation"]
    assert result["noop_bridge_receipt"]["artifacts"][0]["logical_path"] == "artifacts/output.txt"


def test_noop_bridge_marks_replay_as_intent_not_proof():
    result = noop_bridge.build_descriptor_spine_noop_bridge(load_bridge_ready_descriptor())

    assert result["noop_bridge_receipt"]["replay"]["status"] == "intent_only"
    assert result["noop_bridge_receipt"]["replay"]["proof_status"] == "not_proven"


def test_noop_bridge_output_is_deterministic():
    payload = load_bridge_ready_descriptor()

    first = noop_bridge.build_descriptor_spine_noop_bridge(payload)
    second = noop_bridge.build_descriptor_spine_noop_bridge(copy.deepcopy(payload))

    assert first == second


def test_noop_bridge_does_not_mutate_workspace_probe():
    result = noop_bridge.build_descriptor_spine_noop_bridge(load_bridge_ready_descriptor())

    assert result["noop_bridge_receipt"]["workspace_effects"]["mutated"] is False
    assert result["noop_bridge_receipt"]["workspace_effects"]["touched_paths"] == []


def test_noop_bridge_does_not_invoke_tool_or_llm():
    result = noop_bridge.build_descriptor_spine_noop_bridge(load_bridge_ready_descriptor())

    assert result["noop_bridge_receipt"]["tool_invocation"]["invoked"] is False
    assert result["noop_bridge_receipt"]["llm_invocation"]["invoked"] is False


def test_invalid_dry_run_plan_rejected():
    result = noop_bridge.build_noop_bridge_receipt(
        {
            "accepted": True,
            "rejection_codes": [],
            "dry_run_plan": {"plan_kind": "wrong_kind"},
        }
    )

    assert result["accepted"] is False
    assert "NOOP_BRIDGE_INVALID_DRY_RUN_PLAN" in result["rejection_codes"]
    assert result["noop_bridge_receipt"] is None
    assert result["workspace_probe"]["mutated"] is False


@pytest.mark.parametrize(
    ("test_name", "mutate", "expected_code"),
    [
        (
            "invalid_descriptor_rejected_before_noop_bridge",
            lambda payload: payload.pop("task_ref"),
            "SPINE_CONTRACT_REJECTED",
        ),
        (
            "execution_requested_descriptor_rejected",
            lambda payload: payload.update({"execution_request": {"mode": "execute"}}),
            "NOOP_BRIDGE_EXECUTION_REQUESTED",
        ),
        (
            "workspace_mutation_requested_rejected",
            lambda payload: payload.update({"workspace_mutation": {"mutates": True}}),
            "NOOP_BRIDGE_WORKSPACE_MUTATION_FORBIDDEN",
        ),
        (
            "tool_invocation_requested_rejected",
            lambda payload: payload.update({"tool_invocation": {"tool_name": "local_file_writer"}}),
            "NOOP_BRIDGE_TOOL_INVOCATION_FORBIDDEN",
        ),
        (
            "llm_invocation_requested_rejected",
            lambda payload: payload.update({"llm_invocation": {"model": "gpt-5.5"}}),
            "NOOP_BRIDGE_LLM_INVOCATION_FORBIDDEN",
        ),
        (
            "missing_governance_decision_rejected",
            lambda payload: payload["governance_requirements"].pop("decision"),
            "NOOP_BRIDGE_GOVERNANCE_DECISION_MISSING",
        ),
        (
            "missing_transition_audit_binding_rejected",
            lambda payload: payload.pop("audit_binding"),
            "NOOP_BRIDGE_TRANSITION_AUDIT_BINDING_MISSING",
        ),
        (
            "artifact_without_validation_binding_rejected",
            lambda payload: payload["validation_requirements"].pop("artifact_validation_bindings"),
            "NOOP_BRIDGE_ARTIFACT_VALIDATION_BINDING_MISSING",
        ),
        (
            "replay_proof_claim_rejected",
            lambda payload: payload["replay_binding"].update({"proof_status": "proven"}),
            "NOOP_BRIDGE_REPLAY_PROOF_FORBIDDEN",
        ),
    ],
)
def test_negative_noop_bridge_cases_fail_closed(test_name, mutate, expected_code):
    payload = copy.deepcopy(load_bridge_ready_descriptor())
    mutate(payload)

    result = noop_bridge.build_descriptor_spine_noop_bridge(payload)

    assert result["accepted"] is False, test_name
    assert expected_code in result["rejection_codes"], test_name
    assert result["noop_bridge_receipt"] is None, test_name
    assert result["workspace_probe"]["mutated"] is False, test_name
