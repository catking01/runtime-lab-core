from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

from runtime_lab.descriptors import validator
from runtime_lab.descriptors import spine_contract
from runtime_lab.descriptors.errors import DescriptorValidationError
from runtime_lab.kernel20.coverage import KERNEL20_PRIMITIVE_ORDER


FIXTURE_ROOT = Path(__file__).parent.parent / "descriptors/fixtures"
ALLOWED_SCANNING_SUFFIXES = {".py", ".json", ".md", ".txt", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".rst"}


def _base_payload() -> dict:
    payload = json.loads((FIXTURE_ROOT / "valid_minimal_descriptor.json").read_text(encoding="utf-8"))
    payload["non_claims"] = ["implementation not verified yet"]
    payload["governance_requirements"]["decision"] = "approved"
    payload["replay_binding"].update(
        {
            "ledger_ref": "ledger:r111-112-claim-boundary",
            "receipt_ref": "receipt:r111-112-claim-boundary",
            "receipt_hash": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        }
    )
    payload["executor_eligibility"] = {"executor_class": "validator_only", "requested": True}
    return payload


@pytest.mark.parametrize(
    ("field", "token"),
    [
        ("non_claims", "runtime_capability_proven"),
        ("non_claims", "organization_runtime_proven"),
        ("non_claims", "artificial_civilization_seed_proven"),
        ("compatibility_refs", "r105-r110 fully implemented"),
    ],
)
def test_kernel20_artifacts_cannot_assert_proof_or_full_convergence(field: str, token: str):
    payload = _base_payload()
    if field == "non_claims":
        payload[field] = [f"This artifact text claims {token}."]
    else:
        payload[field] = [f"This artifact text states {token}."]

    with pytest.raises(DescriptorValidationError) as excinfo:
        validator.validate_descriptor(payload)

    assert excinfo.value.code == "B1_DESCRIPTOR_FORBIDDEN_CLAIM"


@pytest.mark.parametrize(
    ("field", "token"),
    [
        ("non_claims", "runtime_capability_proven not proven"),
        ("non_claims", "organization runtime proven not claimed"),
        ("non_claims", "artificial_civilization_seed_proven not proven"),
    ],
)
def test_kernel20_boundary_negation_examples_do_not_trigger_false_positive(field: str, token: str):
    payload = _base_payload()
    payload[field] = [token]

    validated = validator.validate_descriptor(copy.deepcopy(payload))

    assert validated["descriptor_id"].startswith("b1-desc-")
    assert validated["canonical_hash"]


def test_removing_r110_r111_non_claims_is_rejected_without_explicit_non_claims():
    payload = _base_payload()
    payload["non_claims"] = []

    with pytest.raises(DescriptorValidationError) as excinfo:
        validator.validate_descriptor(payload)

    assert excinfo.value.code == "B1_DESCRIPTOR_EMPTY_NON_CLAIMS"


def test_kernel20_coverage_alias_is_not_exported_by_spine_contract_source():
    assert not hasattr(spine_contract, "KERNEL_20_COVERAGE")
    assert hasattr(spine_contract, "MINIMAL_KERNEL_BINDING")
    assert hasattr(spine_contract, "DESCRIPTOR_SPINE_BINDING_12")
    assert hasattr(spine_contract, "MINIMAL_SPINE_KERNEL_RELEVANT_FIELDS")


def test_runtime_and_docs_do_not_reintroduce_kernel20_coverage_alias():
    project_root = Path(__file__).resolve().parents[2]
    closure_artifact = project_root / Path(
        "artifacts/runtime/RL-R112/RL_R112_S1_KERNEL20_COVERAGE_ALIAS_CLOSURE.json"
    )
    closure_doc = project_root / Path(
        "docs/runtime_lab/2026-06-17-r112-s1-kernel20-coverage-alias-closure.md"
    )
    scope_roots = [
        project_root / "runtime_lab",
        project_root / "docs",
        project_root / "artifacts",
        project_root / ".codex",
    ]
    hits: list[tuple[str, int, str]] = []
    for scope_root in scope_roots:
        if not scope_root.exists():
            continue
        for path in scope_root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in ALLOWED_SCANNING_SUFFIXES:
                continue
            if "node_modules" in path.parts:
                continue
            if path in {closure_artifact, closure_doc}:
                continue
            if path.name in {"research_record.md", "research_report.md"}:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for lineno, line in enumerate(text.splitlines(), start=1):
                if re.search(r"\bKERNEL_20_COVERAGE\b", line):
                    hits.append((str(path.relative_to(project_root)), lineno, line.rstrip()))
    assert hits == []


def test_kernel20_coverage_alias_absent_from_runtime_contract_source_files():
    project_root = Path(__file__).resolve().parents[2]
    path = project_root / "runtime_lab" / "descriptors" / "spine_contract.py"
    text = path.read_text(encoding="utf-8")
    assert "KERNEL_20_COVERAGE" not in text


def test_kernel20_matrix_minimal_spine_only_subset_is_explicit():
    project_root = Path(__file__).resolve().parents[2]
    matrix_path = project_root / "artifacts/runtime/RL-R112/MINIMAL_SPINE_12_VS_KERNEL20_MATRIX.json"
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    minimal_spine = set(matrix["minimal_spine_12"])
    kernel20 = set(KERNEL20_PRIMITIVE_ORDER)
    minimal_only = minimal_spine - kernel20
    expected_summary = matrix["summary"]

    assert minimal_only == set(expected_summary["minimal_spine_12_only"])
    assert expected_summary["minimal_spine_12_only_count"] == len(minimal_only)
    assert expected_summary["minimal_spine_12_is_strict_subset"] == (not bool(minimal_only))
    assert expected_summary["overlap_count"] == len(minimal_spine & kernel20)
