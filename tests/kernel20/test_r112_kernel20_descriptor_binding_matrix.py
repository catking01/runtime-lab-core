from __future__ import annotations

import json
from pathlib import Path

from runtime_lab.kernel20 import (
    KERNEL20_PRIMITIVE_ORDER,
    KERNEL20_PRIMITIVE_REGISTRY,
)


ARTIFACT_ROOT = Path(__file__).resolve().parents[2] / "artifacts/runtime/RL-R112"
MATRIX_ARTIFACT = ARTIFACT_ROOT / "KERNEL20_DESCRIPTOR_BINDING_MATRIX.json"


def _artifact_matrix() -> list[dict]:
    return json.loads(MATRIX_ARTIFACT.read_text(encoding="utf-8"))


def _registry_by_name() -> dict[str, object]:
    return {primitive.name: primitive for primitive in KERNEL20_PRIMITIVE_REGISTRY}


def test_binding_matrix_has_exact_primitive_rows_and_order():
    matrix = _artifact_matrix()

    assert len(matrix) == len(KERNEL20_PRIMITIVE_ORDER)
    assert [row["name"] for row in matrix] == list(KERNEL20_PRIMITIVE_ORDER)


def test_binding_matrix_rows_align_with_registry_metadata():
    matrix = _artifact_matrix()
    registry = _registry_by_name()

    for row in matrix:
        primitive = registry[row["name"]]

        assert row["status"] == primitive.status
        assert row["descriptor_binding_fields"] == primitive.descriptor_binding_fields
        assert row["evidence_path"] == primitive.evidence_path
        assert row["test_path"] == primitive.test_path
        assert row["gap_reason"] == primitive.gap_reason


def test_binding_matrix_gap_reason_rules_match_registry_state():
    matrix = _artifact_matrix()

    for row in matrix:
        status = row["status"]

        if status in {"descriptor_only", "noop_only", "implemented"}:
            assert row["evidence_path"]
            assert row["test_path"]
            assert row["gap_reason"] is None

        if status in {"planned", "unsupported"}:
            assert row["gap_reason"]
            assert not row["evidence_path"]
            assert not row["test_path"]
