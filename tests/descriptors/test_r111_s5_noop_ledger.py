from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from runtime_lab.descriptors import noop_ledger


FIXTURE_ROOT = Path(__file__).parent / "fixtures"


def load_ledger_ready_descriptor() -> dict:
    payload = json.loads((FIXTURE_ROOT / "valid_minimal_descriptor.json").read_text(encoding="utf-8"))
    payload["executor_eligibility"] = {"executor_class": "validator_only", "requested": True}
    payload["governance_requirements"]["decision"] = "approved"
    payload["governance_requirements"]["decision_ref"] = "governance:r111-s5-local"
    payload["replay_binding"]["receipt_hash"] = "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
    payload["replay_binding"]["ledger_ref"] = "ledger:r111-s5-local"
    payload["replay_binding"]["receipt_ref"] = "receipt:r111-s5-local"
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


def test_valid_descriptor_produces_noop_ledger_receipt():
    result = noop_ledger.build_descriptor_spine_noop_ledger_binding(load_ledger_ready_descriptor())

    assert result["accepted"] is True
    assert result["rejection_codes"] == []
    assert result["noop_ledger_receipt"]["binding_kind"] == "noop_bridge_receipt_ledger_binding"


def test_noop_ledger_receipt_contains_hash_bindings():
    result = noop_ledger.build_descriptor_spine_noop_ledger_binding(load_ledger_ready_descriptor())

    receipt = result["noop_ledger_receipt"]
    assert receipt["hashes"]["receipt_hash"].startswith("sha256:")
    assert receipt["hashes"]["ledger_event_hash"].startswith("sha256:")
    assert receipt["hashes"]["ledger_chain_hash"].startswith("sha256:")


def test_noop_ledger_receipt_contains_chain_and_governance_bindings():
    result = noop_ledger.build_descriptor_spine_noop_ledger_binding(load_ledger_ready_descriptor())

    receipt = result["noop_ledger_receipt"]
    assert receipt["ledger"]["previous_event_hash"] == "GENESIS"
    assert receipt["ledger"]["event_kind"] == "noop_bridge_receipt_ledger_bound"
    assert receipt["governance"]["decision_ref"] == "governance:r111-s5-local"


def test_noop_ledger_marks_replay_as_intent_not_proof():
    result = noop_ledger.build_descriptor_spine_noop_ledger_binding(load_ledger_ready_descriptor())

    assert result["noop_ledger_receipt"]["replay"]["proof_status"] == "not_proven"
    assert result["noop_ledger_receipt"]["replay"]["receipt_binding_status"] == "intent_receipt_only"


def test_noop_ledger_output_is_deterministic():
    payload = load_ledger_ready_descriptor()

    first = noop_ledger.build_descriptor_spine_noop_ledger_binding(payload)
    second = noop_ledger.build_descriptor_spine_noop_ledger_binding(copy.deepcopy(payload))

    assert first == second


def test_noop_ledger_preserves_no_side_effect_probes():
    result = noop_ledger.build_descriptor_spine_noop_ledger_binding(load_ledger_ready_descriptor())

    assert result["noop_ledger_receipt"]["workspace_effects"]["mutated"] is False
    assert result["noop_ledger_receipt"]["tool_invocation"]["invoked"] is False
    assert result["noop_ledger_receipt"]["llm_invocation"]["invoked"] is False


def test_invalid_noop_bridge_result_rejected():
    result = noop_ledger.build_noop_ledger_binding({"accepted": True, "noop_bridge_receipt": {"bridge_kind": "wrong"}})

    assert result["accepted"] is False
    assert "NOOP_LEDGER_INVALID_NOOP_BRIDGE_RESULT" in result["rejection_codes"]
    assert result["noop_ledger_receipt"] is None
    assert result["workspace_probe"]["mutated"] is False


@pytest.mark.parametrize(
    ("test_name", "mutate", "expected_code"),
    [
        (
            "invalid_descriptor_rejected_before_ledger_binding",
            lambda payload: payload.pop("task_ref"),
            "SPINE_CONTRACT_REJECTED",
        ),
        (
            "missing_governance_reference_rejected",
            lambda payload: payload["governance_requirements"].pop("decision_ref"),
            "NOOP_LEDGER_GOVERNANCE_BINDING_MISSING",
        ),
        (
            "missing_replay_receipt_hash_rejected",
            lambda payload: payload["replay_binding"].pop("receipt_hash"),
            "NOOP_LEDGER_REPLAY_BINDING_MISSING",
        ),
        (
            "replay_proof_claim_rejected",
            lambda payload: payload["replay_binding"].update({"proof_status": "proven"}),
            "NOOP_LEDGER_REPLAY_PROOF_FORBIDDEN",
        ),
        (
            "workspace_mutation_requested_rejected",
            lambda payload: payload.update({"workspace_mutation": {"mutates": True}}),
            "NOOP_LEDGER_WORKSPACE_MUTATION_FORBIDDEN",
        ),
        (
            "tool_invocation_requested_rejected",
            lambda payload: payload.update({"tool_invocation": {"tool_name": "x"}}),
            "NOOP_LEDGER_TOOL_INVOCATION_FORBIDDEN",
        ),
        (
            "llm_invocation_requested_rejected",
            lambda payload: payload.update({"llm_invocation": {"model": "gpt-5.5"}}),
            "NOOP_LEDGER_LLM_INVOCATION_FORBIDDEN",
        ),
    ],
)
def test_negative_noop_ledger_cases_fail_closed(test_name, mutate, expected_code):
    payload = copy.deepcopy(load_ledger_ready_descriptor())
    mutate(payload)

    result = noop_ledger.build_descriptor_spine_noop_ledger_binding(payload)

    assert result["accepted"] is False, test_name
    assert expected_code in result["rejection_codes"], test_name
    assert result["noop_ledger_receipt"] is None, test_name
    assert result["workspace_probe"]["mutated"] is False, test_name
