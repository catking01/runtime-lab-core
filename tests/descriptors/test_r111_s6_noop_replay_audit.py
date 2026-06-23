from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from runtime_lab.descriptors import noop_replay_audit


FIXTURE_ROOT = Path(__file__).parent / "fixtures"


def load_replay_ready_descriptor() -> dict:
    payload = json.loads((FIXTURE_ROOT / "valid_minimal_descriptor.json").read_text(encoding="utf-8"))
    payload["executor_eligibility"] = {"executor_class": "validator_only", "requested": True}
    payload["governance_requirements"]["decision"] = "approved"
    payload["governance_requirements"]["decision_ref"] = "governance:r111-s6-local"
    payload["replay_binding"]["receipt_hash"] = "sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
    payload["replay_binding"]["ledger_ref"] = "ledger:r111-s6-local"
    payload["replay_binding"]["receipt_ref"] = "receipt:r111-s6-local"
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


def test_valid_descriptor_produces_replay_audit_receipt():
    result = noop_replay_audit.build_descriptor_spine_noop_ledger_replay_audit(load_replay_ready_descriptor())

    assert result["accepted"] is True
    assert result["rejection_codes"] == []
    assert result["replay_audit_receipt"]["audit_kind"] == "noop_ledger_replay_audit"


def test_replay_audit_rederives_hashes():
    result = noop_replay_audit.build_descriptor_spine_noop_ledger_replay_audit(load_replay_ready_descriptor())

    receipt = result["replay_audit_receipt"]
    assert receipt["verified_hashes"]["receipt_hash_match"] is True
    assert receipt["verified_hashes"]["governance_hash_match"] is True
    assert receipt["verified_hashes"]["replay_hash_match"] is True
    assert receipt["verified_hashes"]["ledger_event_hash_match"] is True
    assert receipt["verified_hashes"]["ledger_chain_hash_match"] is True


def test_replay_audit_contains_chain_and_boundary_status():
    result = noop_replay_audit.build_descriptor_spine_noop_ledger_replay_audit(load_replay_ready_descriptor())

    receipt = result["replay_audit_receipt"]
    assert receipt["audit_status"] == "rederived_and_verified"
    assert receipt["proof_status"] == "not_proven"
    assert receipt["ledger"]["previous_event_hash"] == "GENESIS"


def test_replay_audit_output_is_deterministic():
    payload = load_replay_ready_descriptor()

    first = noop_replay_audit.build_descriptor_spine_noop_ledger_replay_audit(payload)
    second = noop_replay_audit.build_descriptor_spine_noop_ledger_replay_audit(copy.deepcopy(payload))

    assert first == second


def test_replay_audit_preserves_no_side_effect_probe():
    result = noop_replay_audit.build_descriptor_spine_noop_ledger_replay_audit(load_replay_ready_descriptor())

    assert result["replay_audit_receipt"]["workspace_effects"]["mutated"] is False
    assert result["replay_audit_receipt"]["tool_invocation"]["invoked"] is False
    assert result["replay_audit_receipt"]["llm_invocation"]["invoked"] is False


def test_invalid_noop_ledger_result_rejected():
    result = noop_replay_audit.build_noop_ledger_replay_audit(
        {"accepted": True, "noop_ledger_receipt": {"binding_kind": "wrong"}}
    )

    assert result["accepted"] is False
    assert "NOOP_REPLAY_AUDIT_INVALID_NOOP_LEDGER_RESULT" in result["rejection_codes"]
    assert result["replay_audit_receipt"] is None
    assert result["workspace_probe"]["mutated"] is False


def build_valid_noop_ledger_result() -> dict:
    return noop_replay_audit.build_descriptor_spine_noop_ledger_binding(load_replay_ready_descriptor())


@pytest.mark.parametrize(
    ("test_name", "mutate", "expected_code"),
    [
        (
            "invalid_descriptor_rejected_before_replay_audit",
            lambda payload: payload.pop("task_ref"),
            "SPINE_CONTRACT_REJECTED",
        ),
        (
            "tampered_receipt_hash_rejected",
            lambda result: result["noop_ledger_receipt"]["hashes"].update({"receipt_hash": "sha256:0" * 8}),
            "NOOP_REPLAY_AUDIT_RECEIPT_HASH_MISMATCH",
        ),
        (
            "tampered_governance_hash_rejected",
            lambda result: result["noop_ledger_receipt"]["hashes"].update({"governance_hash": "sha256:1" * 8}),
            "NOOP_REPLAY_AUDIT_GOVERNANCE_HASH_MISMATCH",
        ),
        (
            "tampered_replay_hash_rejected",
            lambda result: result["noop_ledger_receipt"]["hashes"].update({"replay_hash": "sha256:2" * 8}),
            "NOOP_REPLAY_AUDIT_REPLAY_HASH_MISMATCH",
        ),
        (
            "tampered_ledger_event_hash_rejected",
            lambda result: result["noop_ledger_receipt"]["hashes"].update({"ledger_event_hash": "sha256:3" * 8}),
            "NOOP_REPLAY_AUDIT_LEDGER_EVENT_HASH_MISMATCH",
        ),
        (
            "tampered_ledger_chain_hash_rejected",
            lambda result: result["noop_ledger_receipt"]["hashes"].update({"ledger_chain_hash": "sha256:4" * 8}),
            "NOOP_REPLAY_AUDIT_LEDGER_CHAIN_HASH_MISMATCH",
        ),
        (
            "tampered_governance_field_rejected",
            lambda result: result["noop_ledger_receipt"]["governance"].update({"decision_ref": "governance:tampered"}),
            "NOOP_REPLAY_AUDIT_GOVERNANCE_HASH_MISMATCH",
        ),
        (
            "tampered_replay_field_rejected",
            lambda result: result["noop_ledger_receipt"]["replay"].update({"ledger_ref": "ledger:tampered"}),
            "NOOP_REPLAY_AUDIT_REPLAY_HASH_MISMATCH",
        ),
    ],
)
def test_negative_noop_replay_audit_cases_fail_closed(test_name, mutate, expected_code):
    if test_name == "invalid_descriptor_rejected_before_replay_audit":
        payload = load_replay_ready_descriptor()
        mutate(payload)
        result = noop_replay_audit.build_descriptor_spine_noop_ledger_replay_audit(payload)
    else:
        noop_ledger_result = build_valid_noop_ledger_result()
        mutate(noop_ledger_result)
        result = noop_replay_audit.build_noop_ledger_replay_audit(noop_ledger_result)

    assert result["accepted"] is False, test_name
    assert expected_code in result["rejection_codes"], test_name
    assert result["replay_audit_receipt"] is None, test_name
    assert result["workspace_probe"]["mutated"] is False, test_name
