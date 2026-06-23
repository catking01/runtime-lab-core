from __future__ import annotations

import json
from pathlib import Path

from runtime_lab.descriptors import canonical


FIXTURE_ROOT = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def test_canonical_hash_is_stable_for_equivalent_descriptors():
    payload = load_fixture("valid_minimal_descriptor.json")
    same_payload = load_fixture("valid_minimal_descriptor.json")

    assert canonical.canonical_hash(payload) == canonical.canonical_hash(same_payload)


def test_canonical_hash_is_stable_when_keys_are_reordered():
    payload = load_fixture("valid_minimal_descriptor.json")
    reordered = {
        "workspace_boundary": payload["workspace_boundary"],
        "validation_requirements": payload["validation_requirements"],
        "transition_intent": payload["transition_intent"],
        "task_ref": payload["task_ref"],
        "state_ref": payload["state_ref"],
        "replay_binding": payload["replay_binding"],
        "non_claims": payload["non_claims"],
        "logical_clock": payload["logical_clock"],
        "identity_binding": payload["identity_binding"],
        "governance_requirements": payload["governance_requirements"],
        "determinism_level": payload["determinism_level"],
        "descriptor_version": payload["descriptor_version"],
        "capability_boundary": payload["capability_boundary"],
        "authority_binding": payload["authority_binding"],
        "audit_binding": payload["audit_binding"],
        "artifact_expectation": payload["artifact_expectation"],
        "action_type": payload["action_type"],
    }

    assert canonical.canonical_hash(payload) == canonical.canonical_hash(reordered)


def test_canonical_hash_changes_when_task_ref_changes():
    payload = load_fixture("valid_minimal_descriptor.json")
    changed = load_fixture("valid_minimal_descriptor.json")
    changed["task_ref"]["task_id"] = "task-002"

    assert canonical.canonical_hash(payload) != canonical.canonical_hash(changed)


def test_canonical_hash_changes_when_authority_binding_changes():
    payload = load_fixture("valid_minimal_descriptor.json")
    changed = load_fixture("valid_minimal_descriptor.json")
    changed["authority_binding"]["required_grants"] = ["write_text_artifact"]

    assert canonical.canonical_hash(payload) != canonical.canonical_hash(changed)


def test_canonical_hash_changes_when_workspace_boundary_changes():
    payload = load_fixture("valid_minimal_descriptor.json")
    changed = load_fixture("valid_minimal_descriptor.json")
    changed["workspace_boundary"]["allowed_roots"] = ["artifacts/reports/"]

    assert canonical.canonical_hash(payload) != canonical.canonical_hash(changed)


def test_canonical_hash_changes_when_artifact_expectation_changes():
    payload = load_fixture("valid_minimal_descriptor.json")
    changed = load_fixture("valid_minimal_descriptor.json")
    changed["artifact_expectation"][0]["logical_path"] = "artifacts/output-v2.txt"

    assert canonical.canonical_hash(payload) != canonical.canonical_hash(changed)


def test_canonical_payload_excludes_derived_fields_from_hash_input():
    payload = load_fixture("valid_minimal_descriptor.json")
    payload["canonical_hash"] = "user-supplied"
    payload["descriptor_id"] = "user-supplied"
    payload["descriptor_hash"] = "user-supplied-alias"

    canonical_payload = canonical.canonical_payload(payload)

    assert "canonical_hash" not in canonical_payload
    assert "descriptor_id" not in canonical_payload
    assert "descriptor_hash" not in canonical_payload
