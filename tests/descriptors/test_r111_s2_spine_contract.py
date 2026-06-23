from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from runtime_lab.descriptors import spine_contract


FIXTURE_ROOT = Path(__file__).parent / "fixtures"


def load_valid_descriptor() -> dict:
    payload = json.loads((FIXTURE_ROOT / "valid_minimal_descriptor.json").read_text(encoding="utf-8"))
    payload["executor_eligibility"] = {"executor_class": "validator_only", "requested": True}
    payload["governance_requirements"]["decision"] = "approved"
    payload["replay_binding"]["receipt_hash"] = "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    payload["replay_binding"]["ledger_ref"] = "ledger:r111-s2-local"
    payload["replay_binding"]["receipt_ref"] = "receipt:r111-s2-local"
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


def test_minimal_valid_descriptor_accepted():
    result = spine_contract.validate_descriptor_spine_contract(load_valid_descriptor())

    assert result["accepted"] is True
    assert result["rejection_codes"] == []
    assert result["kernel_20_checked"] is True
    assert result["kernel_20_full_checked"] is False
    assert result["minimal_spine_checked"] is True


@pytest.mark.parametrize(
    ("test_name", "mutate", "expected_code"),
    [
        (
            "descriptor_missing_task_identity_rejected",
            lambda payload: payload.pop("task_ref"),
            "MISSING_TASK_IDENTITY",
        ),
        (
            "descriptor_missing_authority_binding_rejected",
            lambda payload: payload.pop("authority_binding"),
            "MISSING_AUTHORITY_BINDING",
        ),
        (
            "descriptor_executor_without_workspace_rejected",
            lambda payload: payload.pop("workspace_boundary"),
            "EXECUTOR_WITHOUT_WORKSPACE_BOUNDARY",
        ),
        (
            "descriptor_artifact_without_validation_rejected",
            lambda payload: payload["validation_requirements"].pop("artifact_validation_bindings"),
            "ARTIFACT_WITHOUT_VALIDATION_BINDING",
        ),
        (
            "descriptor_replay_without_receipt_hash_ledger_rejected",
            lambda payload: payload["replay_binding"].pop("ledger_ref"),
            "REPLAY_WITHOUT_RECEIPT_LEDGER_HASH",
        ),
        (
            "descriptor_tool_without_capability_rejected",
            lambda payload: payload.update({"tool_invocation": {"tool_name": "local_file_writer"}}),
            "TOOL_WITHOUT_CAPABILITY",
        ),
        (
            "descriptor_handoff_without_actor_transfer_record_rejected",
            lambda payload: payload.update({"actor_transfer": {"to_actor": "executor"}}),
            "HANDOFF_WITHOUT_ACTOR_RECORD",
        ),
        (
            "descriptor_state_mutation_without_transition_audit_rejected",
            lambda payload: (payload.update({"state_mutation": {"mutates": True}}), payload.pop("audit_binding")),
            "STATE_MUTATION_WITHOUT_TRANSITION_AUDIT",
        ),
        (
            "descriptor_execution_before_governance_rejected",
            lambda payload: payload["governance_requirements"].update({"decision": "pending"}),
            "EXECUTION_BEFORE_GOVERNANCE",
        ),
    ],
)
def test_negative_descriptor_contract_cases_fail_closed(test_name, mutate, expected_code):
    payload = copy.deepcopy(load_valid_descriptor())
    mutate(payload)

    result = spine_contract.validate_descriptor_spine_contract(payload)

    assert result["accepted"] is False, test_name
    assert expected_code in result["rejection_codes"], test_name
