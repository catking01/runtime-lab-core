from __future__ import annotations

from runtime_lab.kernel20.coverage import KERNEL20_PRIMITIVE_ORDER, KERNEL20_PRIMITIVE_SET
from runtime_lab.kernel20.primitives import (
    KERNEL20_PRIMITIVE_REGISTRY,
    kernel20_primitives_by_name,
)
from runtime_lab.kernel20.status import ALLOWED_PRIMITIVE_STATUSES


def test_registry_has_exactly_twenty_primitives_and_exact_required_names():
    assert len(KERNEL20_PRIMITIVE_REGISTRY) == len(KERNEL20_PRIMITIVE_ORDER) == 20
    assert KERNEL20_PRIMITIVE_SET == set(KERNEL20_PRIMITIVE_ORDER)


def test_registry_names_are_unique_and_in_required_order():
    registry_by_name = kernel20_primitives_by_name()

    assert list(registry_by_name.keys()) == list(KERNEL20_PRIMITIVE_ORDER)
    assert set(registry_by_name) == set(KERNEL20_PRIMITIVE_ORDER)
    assert registry_by_name["Schema"].name == "Schema"
    assert registry_by_name["Schema"].status in ALLOWED_PRIMITIVE_STATUSES


def test_registry_contains_all_required_statuses_and_evidence_requirements():
    registry_by_name = kernel20_primitives_by_name()

    statuses = {entry.status for entry in KERNEL20_PRIMITIVE_REGISTRY}
    assert statuses.issubset(ALLOWED_PRIMITIVE_STATUSES)
    assert statuses == {
        "descriptor_only",
        "noop_only",
        "planned",
        "unsupported",
    }

    for primitive_name in KERNEL20_PRIMITIVE_ORDER:
        primitive = registry_by_name[primitive_name]

        assert primitive.name == primitive_name
        assert primitive.status in ALLOWED_PRIMITIVE_STATUSES
        assert primitive.descriptor_binding_fields

        if primitive.status in {"descriptor_only", "noop_only"}:
            assert primitive.evidence_path
            assert primitive.test_path
            assert primitive.gap_reason is None

        if primitive.status == "planned":
            assert primitive.gap_reason is not None
            assert primitive.gap_reason.strip()
            assert primitive.evidence_path is None
            assert primitive.test_path is None

        if primitive.status == "unsupported":
            assert primitive.gap_reason is not None
            assert primitive.gap_reason.strip()
            assert primitive.evidence_path is None
            assert primitive.test_path is None


def test_registry_lookup_function_returns_all_primitives():
    registry_by_name = kernel20_primitives_by_name()

    for expected in KERNEL20_PRIMITIVE_ORDER:
        assert expected in registry_by_name
