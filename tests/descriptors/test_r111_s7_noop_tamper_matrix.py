from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from runtime_lab.descriptors import noop_tamper_matrix


FIXTURE_ROOT = Path(__file__).parent / "fixtures"


def load_matrix_ready_descriptor() -> dict:
    payload = json.loads((FIXTURE_ROOT / "valid_minimal_descriptor.json").read_text(encoding="utf-8"))
    payload["executor_eligibility"] = {"executor_class": "validator_only", "requested": True}
    payload["governance_requirements"]["decision"] = "approved"
    payload["governance_requirements"]["decision_ref"] = "governance:r111-s7-local"
    payload["replay_binding"]["receipt_hash"] = "sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
    payload["replay_binding"]["ledger_ref"] = "ledger:r111-s7-local"
    payload["replay_binding"]["receipt_ref"] = "receipt:r111-s7-local"
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


def test_valid_descriptor_produces_tamper_matrix_receipt():
    result = noop_tamper_matrix.build_noop_ledger_tamper_matrix(load_matrix_ready_descriptor())

    assert result["accepted"] is True
    assert result["rejection_codes"] == []
    assert result["tamper_matrix_receipt"]["matrix_kind"] == "noop_ledger_tamper_replay_matrix"


def test_tamper_matrix_contains_required_cases():
    result = noop_tamper_matrix.build_noop_ledger_tamper_matrix(load_matrix_ready_descriptor())

    assert [case["case_id"] for case in result["tamper_matrix_receipt"]["cases"]] == [
        "tamper_receipt_hash",
        "tamper_governance_hash",
        "tamper_governance_decision_ref",
        "tamper_replay_hash",
        "tamper_replay_receipt_ref",
        "tamper_replay_ledger_ref",
        "tamper_ledger_event_hash",
        "tamper_ledger_chain_hash",
        "tamper_ledger_previous_event_hash",
        "tamper_workspace_effects_mutated_true",
        "tamper_tool_invocation_true",
        "tamper_llm_invocation_true",
        "tamper_replay_proof_status_proven",
    ]


def test_tamper_matrix_rejects_all_cases():
    result = noop_tamper_matrix.build_noop_ledger_tamper_matrix(load_matrix_ready_descriptor())

    receipt = result["tamper_matrix_receipt"]
    assert receipt["case_count"] == 13
    assert receipt["passed_case_count"] == 13
    assert receipt["failed_case_count"] == 0
    assert all(case["accepted"] is False for case in receipt["cases"])


def test_tamper_matrix_records_expected_rejection_codes():
    result = noop_tamper_matrix.build_noop_ledger_tamper_matrix(load_matrix_ready_descriptor())

    codes = {case["case_id"]: case["expected_code"] for case in result["tamper_matrix_receipt"]["cases"]}
    assert codes == {
        "tamper_receipt_hash": "NOOP_REPLAY_AUDIT_RECEIPT_HASH_MISMATCH",
        "tamper_governance_hash": "NOOP_REPLAY_AUDIT_GOVERNANCE_HASH_MISMATCH",
        "tamper_governance_decision_ref": "NOOP_REPLAY_AUDIT_GOVERNANCE_HASH_MISMATCH",
        "tamper_replay_hash": "NOOP_REPLAY_AUDIT_REPLAY_HASH_MISMATCH",
        "tamper_replay_receipt_ref": "NOOP_REPLAY_AUDIT_REPLAY_HASH_MISMATCH",
        "tamper_replay_ledger_ref": "NOOP_REPLAY_AUDIT_REPLAY_HASH_MISMATCH",
        "tamper_ledger_event_hash": "NOOP_REPLAY_AUDIT_LEDGER_EVENT_HASH_MISMATCH",
        "tamper_ledger_chain_hash": "NOOP_REPLAY_AUDIT_LEDGER_CHAIN_HASH_MISMATCH",
        "tamper_ledger_previous_event_hash": "NOOP_REPLAY_AUDIT_LEDGER_EVENT_HASH_MISMATCH",
        "tamper_workspace_effects_mutated_true": "NOOP_REPLAY_AUDIT_WORKSPACE_MUTATION_FORBIDDEN",
        "tamper_tool_invocation_true": "NOOP_REPLAY_AUDIT_TOOL_INVOCATION_FORBIDDEN",
        "tamper_llm_invocation_true": "NOOP_REPLAY_AUDIT_LLM_INVOCATION_FORBIDDEN",
        "tamper_replay_proof_status_proven": "NOOP_REPLAY_AUDIT_REPLAY_PROOF_FORBIDDEN",
    }


def test_tamper_matrix_output_is_deterministic():
    payload = load_matrix_ready_descriptor()

    first = noop_tamper_matrix.build_noop_ledger_tamper_matrix(payload)
    second = noop_tamper_matrix.build_noop_ledger_tamper_matrix(copy.deepcopy(payload))

    assert first == second


def test_tamper_matrix_marks_scope_as_negative_matrix_not_replay_engine():
    result = noop_tamper_matrix.build_noop_ledger_tamper_matrix(load_matrix_ready_descriptor())

    receipt = result["tamper_matrix_receipt"]
    assert receipt["replay_scope"] == "negative_replay_matrix_only_not_engine_proof"
    assert receipt["proof_status"] == "not_proven"


def test_tamper_matrix_preserves_no_workspace_mutation():
    result = noop_tamper_matrix.build_noop_ledger_tamper_matrix(load_matrix_ready_descriptor())

    assert result["tamper_matrix_receipt"]["workspace_effects"]["mutated"] is False
    assert result["workspace_probe"]["mutated"] is False


def test_tamper_matrix_preserves_no_tool_or_llm_invocation():
    result = noop_tamper_matrix.build_noop_ledger_tamper_matrix(load_matrix_ready_descriptor())

    assert result["tamper_matrix_receipt"]["tool_invocation"]["invoked"] is False
    assert result["tamper_matrix_receipt"]["llm_invocation"]["invoked"] is False


def build_valid_replay_audit_result() -> dict:
    return noop_tamper_matrix.build_descriptor_spine_noop_ledger_replay_audit(load_matrix_ready_descriptor())


def test_invalid_descriptor_rejected_before_tamper_matrix():
    payload = load_matrix_ready_descriptor()
    payload.pop("task_ref")

    result = noop_tamper_matrix.build_noop_ledger_tamper_matrix(payload)

    assert result["accepted"] is False
    assert "SPINE_CONTRACT_REJECTED" in result["rejection_codes"]
    assert result["tamper_matrix_receipt"] is None
    assert result["workspace_probe"]["mutated"] is False


def test_baseline_replay_audit_rejection_stops_matrix():
    replay_audit_result = build_valid_replay_audit_result()
    replay_audit_result["accepted"] = False
    replay_audit_result["rejection_codes"] = ["NOOP_REPLAY_AUDIT_RECEIPT_HASH_MISMATCH"]
    replay_audit_result["replay_audit_receipt"] = None

    result = noop_tamper_matrix.build_noop_ledger_tamper_matrix_from_replay_audit(replay_audit_result)

    assert result["accepted"] is False
    assert "NOOP_TAMPER_MATRIX_REPLAY_AUDIT_REJECTED" in result["rejection_codes"]
    assert result["tamper_matrix_receipt"] is None
    assert result["workspace_probe"]["mutated"] is False


def test_missing_required_tamper_case_rejected():
    replay_audit_result = build_valid_replay_audit_result()
    tamper_cases = noop_tamper_matrix.default_tamper_cases()[:-1]

    result = noop_tamper_matrix.build_noop_ledger_tamper_matrix_from_replay_audit(
        replay_audit_result,
        tamper_cases=tamper_cases,
    )

    assert result["accepted"] is False
    assert "NOOP_TAMPER_MATRIX_REQUIRED_CASE_MISSING" in result["rejection_codes"]
    assert result["tamper_matrix_receipt"] is None
    assert result["workspace_probe"]["mutated"] is False


def test_unexpected_tamper_acceptance_rejected():
    replay_audit_result = build_valid_replay_audit_result()
    tamper_cases = copy.deepcopy(noop_tamper_matrix.default_tamper_cases())
    tamper_cases[0]["mutate"] = lambda result: None

    result = noop_tamper_matrix.build_noop_ledger_tamper_matrix_from_replay_audit(
        replay_audit_result,
        tamper_cases=tamper_cases,
    )

    assert result["accepted"] is False
    assert "NOOP_TAMPER_MATRIX_EXPECTED_REJECTION_MISSING" in result["rejection_codes"]
    assert result["tamper_matrix_receipt"] is None
    assert result["workspace_probe"]["mutated"] is False


def test_wrong_expected_code_rejected():
    replay_audit_result = build_valid_replay_audit_result()
    tamper_cases = copy.deepcopy(noop_tamper_matrix.default_tamper_cases())
    tamper_cases[0]["expected_code"] = "NOOP_REPLAY_AUDIT_GOVERNANCE_HASH_MISMATCH"

    result = noop_tamper_matrix.build_noop_ledger_tamper_matrix_from_replay_audit(
        replay_audit_result,
        tamper_cases=tamper_cases,
    )

    assert result["accepted"] is False
    assert "NOOP_TAMPER_MATRIX_WRONG_EXPECTED_CODE" in result["rejection_codes"]
    assert result["tamper_matrix_receipt"] is None
    assert result["workspace_probe"]["mutated"] is False


@pytest.mark.parametrize(
    ("test_name", "case_id", "expected_code"),
    [
        (
            "tamper_matrix_replay_proof_claim_rejected",
            "tamper_replay_proof_status_proven",
            "NOOP_REPLAY_AUDIT_REPLAY_PROOF_FORBIDDEN",
        ),
        (
            "tamper_matrix_workspace_mutation_rejected",
            "tamper_workspace_effects_mutated_true",
            "NOOP_REPLAY_AUDIT_WORKSPACE_MUTATION_FORBIDDEN",
        ),
        (
            "tamper_matrix_tool_invocation_rejected",
            "tamper_tool_invocation_true",
            "NOOP_REPLAY_AUDIT_TOOL_INVOCATION_FORBIDDEN",
        ),
        (
            "tamper_matrix_llm_invocation_rejected",
            "tamper_llm_invocation_true",
            "NOOP_REPLAY_AUDIT_LLM_INVOCATION_FORBIDDEN",
        ),
    ],
)
def test_tamper_matrix_boundary_cases_rejected(test_name, case_id, expected_code):
    result = noop_tamper_matrix.build_noop_ledger_tamper_matrix(load_matrix_ready_descriptor())

    matrix_case = next(case for case in result["tamper_matrix_receipt"]["cases"] if case["case_id"] == case_id)
    assert matrix_case["accepted"] is False, test_name
    assert expected_code in matrix_case["actual_rejection_codes"], test_name
