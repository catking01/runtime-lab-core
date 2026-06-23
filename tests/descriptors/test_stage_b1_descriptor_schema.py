from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime_lab.descriptors import schema


FIXTURE_ROOT = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def test_schema_classifies_required_optional_derived_and_forbidden_fields():
    field_specs = schema.field_specs()

    assert field_specs["descriptor_version"]["class"] == "required"
    assert field_specs["task_ref"]["class"] == "required"
    assert field_specs["executor_eligibility"]["class"] == "optional"
    assert field_specs["canonical_hash"]["class"] == "derived"
    assert field_specs["unknown_fields"]["class"] == "forbidden"


def test_schema_rejects_non_mapping_payload():
    errors = schema.validate_schema_shape(["not", "a", "mapping"])

    assert errors == ["B1_DESCRIPTOR_INVALID_FIELD_TYPE"]


def test_schema_rejects_missing_required_field():
    payload = load_fixture("invalid_missing_task_ref.json")

    errors = schema.validate_schema_shape(payload)

    assert errors == ["B1_DESCRIPTOR_MISSING_REQUIRED_FIELD"]


def test_schema_rejects_unknown_field_in_strict_mode():
    payload = load_fixture("invalid_unknown_field_strict_mode.json")

    errors = schema.validate_schema_shape(payload)

    assert errors == ["B1_DESCRIPTOR_UNKNOWN_FIELD"]


@pytest.mark.parametrize(
    "fixture_name",
    [
        "invalid_empty_task_ref.json",
        "invalid_empty_state_ref.json",
        "invalid_missing_transition_target.json",
        "invalid_missing_transition_type.json",
        "invalid_missing_identity_fields.json",
        "invalid_missing_audit_trail.json",
        "invalid_missing_replay_signature_fields.json",
        "invalid_replay_signature_fields_missing_canonical_hash.json",
        "invalid_replay_signature_fields_missing_logical_clock.json",
        "invalid_empty_logical_clock.json",
        "invalid_artifact_expectation_missing_logical_path.json",
        "invalid_artifact_expectation_missing_binding_method.json",
    ],
)
def test_schema_rejects_missing_nested_required_content(fixture_name: str):
    payload = load_fixture(fixture_name)

    errors = schema.validate_schema_shape(payload)

    assert errors == ["B1_DESCRIPTOR_MISSING_REQUIRED_FIELD"]


@pytest.mark.parametrize(
    "fixture_name",
    [
        "invalid_optional_notes_item_type.json",
    ],
)
def test_schema_rejects_optional_text_list_item_type_violations(fixture_name: str):
    payload = load_fixture(fixture_name)

    errors = schema.validate_schema_shape(payload)

    assert errors == ["B1_DESCRIPTOR_INVALID_FIELD_TYPE"]


@pytest.mark.parametrize(
    "fixture_name",
    [
        "invalid_artifact_logical_path_absolute.json",
        "invalid_artifact_logical_path_traversal.json",
    ],
)
def test_schema_rejects_artifact_paths_outside_workspace_boundary(fixture_name: str):
    payload = load_fixture(fixture_name)

    errors = schema.validate_schema_shape(payload)

    assert errors == ["B1_DESCRIPTOR_MISSING_REQUIRED_FIELD"]
