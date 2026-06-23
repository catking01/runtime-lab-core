from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from runtime_lab.descriptors import spine_contract
from runtime_lab.kernel20.coverage import KERNEL20_PRIMITIVE_ORDER, MINIMAL_KERNEL_BINDING_12


FIXTURE_ROOT = Path(__file__).parent.parent / "descriptors/fixtures"


def _base_payload() -> dict:
    payload = json.loads((FIXTURE_ROOT / "valid_minimal_descriptor.json").read_text(encoding="utf-8"))
    payload["replay_binding"].update(
        {
            "ledger_ref": "ledger:r111-112-test",
            "receipt_ref": "receipt:r111-112-test",
            "receipt_hash": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        }
    )
    payload["kernel_binding"] = {
        "kernel": "Kernel 20",
        "coverage": sorted(MINIMAL_KERNEL_BINDING_12),
    }
    payload["executor_eligibility"] = {"executor_class": "validator_only", "requested": True}
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
        ]
    }
    payload["governance_requirements"]["decision"] = "approved"
    return payload


def test_minimal_spine_binding_not_interpreted_as_full_kernel20_coverage():
    result = spine_contract.validate_descriptor_spine_contract(_base_payload())

    assert result["accepted"] is False
    assert result["kernel_20_checked"] is True
    assert result["kernel_20_full_checked"] is False
    assert result["kernel20_coverage_report"]["minimal_coverage"] is True
    assert result["kernel20_coverage_report"]["full_coverage"] is False


def test_minimal_binding_set_does_not_trigger_kernel20_full_coverage_alias():
    assert not hasattr(spine_contract, "KERNEL_20_COVERAGE")
    assert not hasattr(spine_contract, "kernel_20_coverage")


@pytest.mark.parametrize(
    "missing_primitive",
    [
        "Schema",
        "Actor Lifecycle",
        "Clock",
        "Scheduler",
        "Handoff",
        "Tool",
        "LLM",
        "Resource",
        "Security",
    ],
)
def test_kernel20_full_coverage_fails_when_any_required_primitive_missing(missing_primitive: str):
    payload = _base_payload()
    coverage = [name for name in KERNEL20_PRIMITIVE_ORDER if name != missing_primitive]
    coverage.append("Replay")
    payload["kernel_binding"]["coverage"] = coverage

    result = spine_contract.validate_descriptor_spine_contract(payload)

    assert result["kernel_20_full_checked"] is False
    assert missing_primitive in result["kernel20_coverage_report"]["missing_full"]


def test_full_kernel20_coverage_marker_passes_with_all_required_primitives():
    payload = _base_payload()
    payload["kernel_binding"]["coverage"] = list(KERNEL20_PRIMITIVE_ORDER)

    result = spine_contract.validate_descriptor_spine_contract(payload)

    assert result["kernel_20_checked"] is True
    assert result["kernel_20_full_checked"] is True


def test_incomplete_kernel20_binding_without_minimal_subset_rejected():
    payload = _base_payload()
    payload["kernel_binding"]["coverage"] = ["Task", "Replay"]

    result = spine_contract.validate_descriptor_spine_contract(payload)

    assert result["accepted"] is False
    assert result["kernel_20_checked"] is True
    assert result["kernel_20_minimal_checked"] is False
    assert result["kernel_20_full_checked"] is False
    assert spine_contract.KERNEL_20_BINDING in result["rejection_codes"]
