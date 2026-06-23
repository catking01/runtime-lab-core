from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime_lab.descriptors import validator
from runtime_lab.descriptors.errors import DescriptorValidationError


FIXTURE_ROOT = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def test_valid_minimal_descriptor_is_accepted():
    payload = load_fixture("valid_minimal_descriptor.json")

    validated = validator.validate_descriptor(payload)

    assert validated["descriptor_id"].startswith("b1-desc-")
    assert validated["canonical_hash"]
    assert validated["descriptor_hash"] == validated["canonical_hash"]


def test_non_mapping_payload_fails_closed():
    with pytest.raises(DescriptorValidationError) as excinfo:
        validator.validate_descriptor(["not", "a", "mapping"])

    assert excinfo.value.code == "B1_DESCRIPTOR_INVALID_FIELD_TYPE"


@pytest.mark.parametrize(
    ("fixture_name", "error_code"),
    [
        ("invalid_missing_task_ref.json", "B1_DESCRIPTOR_MISSING_REQUIRED_FIELD"),
        ("invalid_missing_state_ref.json", "B1_DESCRIPTOR_MISSING_REQUIRED_FIELD"),
        ("invalid_missing_authority_binding.json", "B1_DESCRIPTOR_MISSING_AUTHORITY_BINDING"),
        ("invalid_ambiguous_workspace_boundary.json", "B1_DESCRIPTOR_AMBIGUOUS_WORKSPACE_BOUNDARY"),
        ("invalid_undeclared_artifact_output.json", "B1_DESCRIPTOR_UNDECLARED_ARTIFACT_OUTPUT"),
        ("invalid_forbidden_side_effect_field.json", "B1_DESCRIPTOR_FORBIDDEN_FIELD"),
        ("invalid_proposer_supplied_hash.json", "B1_DESCRIPTOR_PROPOSER_SUPPLIED_DERIVED_FIELD"),
        ("invalid_proposer_supplied_descriptor_hash.json", "B1_DESCRIPTOR_PROPOSER_SUPPLIED_DERIVED_FIELD"),
        ("invalid_unknown_executor_class.json", "B1_DESCRIPTOR_UNKNOWN_FIELD"),
        ("invalid_missing_validation_requirements.json", "B1_DESCRIPTOR_MISSING_REQUIRED_FIELD"),
        ("invalid_missing_non_claims.json", "B1_DESCRIPTOR_EMPTY_NON_CLAIMS"),
        ("invalid_missing_replay_binding.json", "B1_DESCRIPTOR_MISSING_REPLAY_BINDING"),
        ("invalid_non_deterministic_timestamp.json", "B1_DESCRIPTOR_FORBIDDEN_FIELD"),
        ("invalid_unknown_field_strict_mode.json", "B1_DESCRIPTOR_UNKNOWN_FIELD"),
        ("invalid_missing_governance_predicate.json", "B1_DESCRIPTOR_MISSING_GOVERNANCE_REQUIREMENT"),
        ("invalid_authority_capability_mismatch.json", "B1_DESCRIPTOR_AUTHORITY_CAPABILITY_MISMATCH"),
        ("invalid_authority_extra_required_grant.json", "B1_DESCRIPTOR_AUTHORITY_CAPABILITY_MISMATCH"),
        ("invalid_authority_duplicate_required_grant.json", "B1_DESCRIPTOR_AUTHORITY_CAPABILITY_MISMATCH"),
        ("invalid_capability_extra_allowed_action.json", "B1_DESCRIPTOR_AUTHORITY_CAPABILITY_MISMATCH"),
        ("invalid_capability_duplicate_allowed_action.json", "B1_DESCRIPTOR_AUTHORITY_CAPABILITY_MISMATCH"),
        ("invalid_capability_unknown_allowed_action.json", "B1_DESCRIPTOR_AUTHORITY_CAPABILITY_MISMATCH"),
        ("invalid_empty_task_ref.json", "B1_DESCRIPTOR_MISSING_REQUIRED_FIELD"),
        ("invalid_empty_state_ref.json", "B1_DESCRIPTOR_MISSING_REQUIRED_FIELD"),
        ("invalid_missing_transition_target.json", "B1_DESCRIPTOR_MISSING_REQUIRED_FIELD"),
        ("invalid_missing_transition_type.json", "B1_DESCRIPTOR_MISSING_REQUIRED_FIELD"),
        ("invalid_missing_identity_fields.json", "B1_DESCRIPTOR_MISSING_REQUIRED_FIELD"),
        ("invalid_missing_audit_trail.json", "B1_DESCRIPTOR_MISSING_REQUIRED_FIELD"),
        ("invalid_missing_replay_signature_fields.json", "B1_DESCRIPTOR_MISSING_REQUIRED_FIELD"),
        ("invalid_replay_signature_fields_missing_canonical_hash.json", "B1_DESCRIPTOR_MISSING_REQUIRED_FIELD"),
        ("invalid_replay_signature_fields_missing_logical_clock.json", "B1_DESCRIPTOR_MISSING_REQUIRED_FIELD"),
        ("invalid_empty_logical_clock.json", "B1_DESCRIPTOR_MISSING_REQUIRED_FIELD"),
        ("invalid_artifact_expectation_missing_logical_path.json", "B1_DESCRIPTOR_MISSING_REQUIRED_FIELD"),
        ("invalid_artifact_expectation_missing_binding_method.json", "B1_DESCRIPTOR_MISSING_REQUIRED_FIELD"),
        ("invalid_artifact_logical_path_absolute.json", "B1_DESCRIPTOR_MISSING_REQUIRED_FIELD"),
        ("invalid_artifact_logical_path_traversal.json", "B1_DESCRIPTOR_MISSING_REQUIRED_FIELD"),
        ("invalid_optional_notes_item_type.json", "B1_DESCRIPTOR_INVALID_FIELD_TYPE"),
        ("invalid_descriptor_overclaim_note.json", "B1_DESCRIPTOR_FORBIDDEN_CLAIM"),
        ("invalid_compatibility_ref_overclaim.json", "B1_DESCRIPTOR_FORBIDDEN_CLAIM"),
        ("invalid_write_text_empty_artifact_expectation_non_artifact_target.json", "B1_DESCRIPTOR_UNDECLARED_ARTIFACT_OUTPUT"),
        ("invalid_non_claims_runtime_capability_overclaim.json", "B1_DESCRIPTOR_FORBIDDEN_CLAIM"),
        ("invalid_non_claims_runtime_capability_proven_but_not_claimed.json", "B1_DESCRIPTOR_FORBIDDEN_CLAIM"),
        ("invalid_non_claims_main_canonical_overclaim.json", "B1_DESCRIPTOR_FORBIDDEN_CLAIM"),
        ("invalid_non_claims_r105_r110_overclaim.json", "B1_DESCRIPTOR_FORBIDDEN_CLAIM"),
        ("invalid_authority_denies_required_grant.json", "B1_DESCRIPTOR_AUTHORITY_CAPABILITY_MISMATCH"),
        ("invalid_capability_denies_allowed_action.json", "B1_DESCRIPTOR_AUTHORITY_CAPABILITY_MISMATCH"),
    ],
)
def test_invalid_descriptors_fail_closed(fixture_name: str, error_code: str):
    payload = load_fixture(fixture_name)

    with pytest.raises(DescriptorValidationError) as excinfo:
        validator.validate_descriptor(payload)

    assert excinfo.value.code == error_code
