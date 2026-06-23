from __future__ import annotations

import copy
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from .noop_replay_audit import build_descriptor_spine_noop_ledger_replay_audit
from .noop_replay_audit import build_noop_ledger_replay_audit


NOOP_TAMPER_MATRIX_INVALID_REPLAY_AUDIT_RESULT = "NOOP_TAMPER_MATRIX_INVALID_REPLAY_AUDIT_RESULT"
NOOP_TAMPER_MATRIX_REPLAY_AUDIT_REJECTED = "NOOP_TAMPER_MATRIX_REPLAY_AUDIT_REJECTED"
NOOP_TAMPER_MATRIX_REQUIRED_CASE_MISSING = "NOOP_TAMPER_MATRIX_REQUIRED_CASE_MISSING"
NOOP_TAMPER_MATRIX_EXPECTED_REJECTION_MISSING = "NOOP_TAMPER_MATRIX_EXPECTED_REJECTION_MISSING"
NOOP_TAMPER_MATRIX_WRONG_EXPECTED_CODE = "NOOP_TAMPER_MATRIX_WRONG_EXPECTED_CODE"

_REQUIRED_CASE_IDS = [
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


def _is_mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


def _reject(*codes: str, details: Mapping[str, Any] | None = None) -> dict[str, Any]:
    result = {
        "accepted": False,
        "rejection_codes": list(codes),
        "tamper_matrix_receipt": None,
        "workspace_probe": {
            "mutated": False,
            "touched_paths": [],
        },
    }
    if details is not None:
        result["details"] = dict(details)
    return result


def _replay_audit_rejection_codes(replay_audit_result: Mapping[str, Any]) -> list[str]:
    codes = list(replay_audit_result.get("rejection_codes", []))
    if NOOP_TAMPER_MATRIX_REPLAY_AUDIT_REJECTED not in codes:
        codes.insert(0, NOOP_TAMPER_MATRIX_REPLAY_AUDIT_REJECTED)
    return codes


def _valid_replay_audit_receipt(receipt: Any) -> bool:
    if not _is_mapping(receipt):
        return False
    if receipt.get("audit_kind") != "noop_ledger_replay_audit":
        return False
    required_fields = {
        "audit_receipt_id",
        "source_binding_receipt_id",
        "audit_status",
        "proof_status",
        "descriptor_id",
        "descriptor_hash",
        "verified_hashes",
        "actual_hashes",
        "expected_hashes",
        "governance",
        "replay",
        "ledger",
        "workspace_effects",
        "tool_invocation",
        "llm_invocation",
    }
    return required_fields <= set(receipt)


def _valid_replay_audit_result(replay_audit_result: Any) -> bool:
    if not _is_mapping(replay_audit_result):
        return False
    required_fields = {
        "accepted",
        "rejection_codes",
        "descriptor",
        "spine_contract",
        "dry_run_plan",
        "noop_bridge_receipt",
        "noop_ledger_receipt",
        "replay_audit_receipt",
        "workspace_probe",
    }
    if not required_fields <= set(replay_audit_result):
        return False
    return _valid_replay_audit_receipt(replay_audit_result.get("replay_audit_receipt"))


def _update_hash(receipt: Mapping[str, Any], field: str, value: str) -> None:
    receipt["hashes"][field] = value


def _default_case_specs() -> list[dict[str, Any]]:
    return [
        {
            "case_id": "tamper_receipt_hash",
            "expected_code": "NOOP_REPLAY_AUDIT_RECEIPT_HASH_MISMATCH",
            "mutate": lambda result: _update_hash(result["noop_ledger_receipt"], "receipt_hash", "sha256:0" * 8),
        },
        {
            "case_id": "tamper_governance_hash",
            "expected_code": "NOOP_REPLAY_AUDIT_GOVERNANCE_HASH_MISMATCH",
            "mutate": lambda result: _update_hash(result["noop_ledger_receipt"], "governance_hash", "sha256:1" * 8),
        },
        {
            "case_id": "tamper_governance_decision_ref",
            "expected_code": "NOOP_REPLAY_AUDIT_GOVERNANCE_HASH_MISMATCH",
            "mutate": lambda result: result["noop_ledger_receipt"]["governance"].update({"decision_ref": "governance:tampered"}),
        },
        {
            "case_id": "tamper_replay_hash",
            "expected_code": "NOOP_REPLAY_AUDIT_REPLAY_HASH_MISMATCH",
            "mutate": lambda result: _update_hash(result["noop_ledger_receipt"], "replay_hash", "sha256:2" * 8),
        },
        {
            "case_id": "tamper_replay_receipt_ref",
            "expected_code": "NOOP_REPLAY_AUDIT_REPLAY_HASH_MISMATCH",
            "mutate": lambda result: result["noop_ledger_receipt"]["replay"].update({"receipt_ref": "receipt:tampered"}),
        },
        {
            "case_id": "tamper_replay_ledger_ref",
            "expected_code": "NOOP_REPLAY_AUDIT_REPLAY_HASH_MISMATCH",
            "mutate": lambda result: result["noop_ledger_receipt"]["replay"].update({"ledger_ref": "ledger:tampered"}),
        },
        {
            "case_id": "tamper_ledger_event_hash",
            "expected_code": "NOOP_REPLAY_AUDIT_LEDGER_EVENT_HASH_MISMATCH",
            "mutate": lambda result: _update_hash(result["noop_ledger_receipt"], "ledger_event_hash", "sha256:3" * 8),
        },
        {
            "case_id": "tamper_ledger_chain_hash",
            "expected_code": "NOOP_REPLAY_AUDIT_LEDGER_CHAIN_HASH_MISMATCH",
            "mutate": lambda result: _update_hash(result["noop_ledger_receipt"], "ledger_chain_hash", "sha256:4" * 8),
        },
        {
            "case_id": "tamper_ledger_previous_event_hash",
            "expected_code": "NOOP_REPLAY_AUDIT_LEDGER_EVENT_HASH_MISMATCH",
            "mutate": lambda result: result["noop_ledger_receipt"]["ledger"].update({"previous_event_hash": "tampered-previous-hash"}),
        },
        {
            "case_id": "tamper_workspace_effects_mutated_true",
            "expected_code": "NOOP_REPLAY_AUDIT_WORKSPACE_MUTATION_FORBIDDEN",
            "mutate": lambda result: result["noop_ledger_receipt"]["workspace_effects"].update({"mutated": True}),
        },
        {
            "case_id": "tamper_tool_invocation_true",
            "expected_code": "NOOP_REPLAY_AUDIT_TOOL_INVOCATION_FORBIDDEN",
            "mutate": lambda result: result["noop_ledger_receipt"]["tool_invocation"].update({"invoked": True, "tools": ["forbidden-tool"]}),
        },
        {
            "case_id": "tamper_llm_invocation_true",
            "expected_code": "NOOP_REPLAY_AUDIT_LLM_INVOCATION_FORBIDDEN",
            "mutate": lambda result: result["noop_ledger_receipt"]["llm_invocation"].update({"invoked": True, "models": ["forbidden-model"]}),
        },
        {
            "case_id": "tamper_replay_proof_status_proven",
            "expected_code": "NOOP_REPLAY_AUDIT_REPLAY_PROOF_FORBIDDEN",
            "mutate": lambda result: result["noop_ledger_receipt"]["replay"].update({"proof_status": "proven"}),
        },
    ]


def default_tamper_cases() -> list[dict[str, Any]]:
    return list(_default_case_specs())


def _validate_case_manifest(tamper_cases: Sequence[Mapping[str, Any]]) -> str | None:
    case_ids = [str(case.get("case_id")) for case in tamper_cases]
    if case_ids != _REQUIRED_CASE_IDS:
        return NOOP_TAMPER_MATRIX_REQUIRED_CASE_MISSING
    return None


def _run_case(
    replay_audit_result: Mapping[str, Any],
    case_spec: Mapping[str, Any],
) -> dict[str, Any]:
    mutated_result = copy.deepcopy(replay_audit_result)
    mutate = case_spec["mutate"]
    if isinstance(mutate, Callable):
        mutate(mutated_result)

    case_result = build_noop_ledger_replay_audit(mutated_result)
    actual_codes = list(case_result.get("rejection_codes", []))
    expected_code = str(case_spec["expected_code"])

    if case_result.get("accepted") is True:
        return {
            "failed": True,
            "failure_code": NOOP_TAMPER_MATRIX_EXPECTED_REJECTION_MISSING,
            "case": {
                "case_id": str(case_spec["case_id"]),
                "expected_code": expected_code,
                "accepted": True,
                "actual_rejection_codes": actual_codes,
            },
        }

    if expected_code not in actual_codes:
        return {
            "failed": True,
            "failure_code": NOOP_TAMPER_MATRIX_WRONG_EXPECTED_CODE,
            "case": {
                "case_id": str(case_spec["case_id"]),
                "expected_code": expected_code,
                "accepted": False,
                "actual_rejection_codes": actual_codes,
            },
        }

    return {
        "failed": False,
        "case": {
            "case_id": str(case_spec["case_id"]),
            "expected_code": expected_code,
            "accepted": False,
            "actual_rejection_codes": actual_codes,
        },
    }


def _build_receipt(replay_audit_result: Mapping[str, Any], cases: list[dict[str, Any]]) -> dict[str, Any]:
    replay_audit_receipt = replay_audit_result["replay_audit_receipt"]
    return {
        "matrix_kind": "noop_ledger_tamper_replay_matrix",
        "matrix_receipt_id": f"noop-tamper-matrix-{replay_audit_receipt['descriptor_id']}",
        "matrix_status": "all_expected_tamper_cases_rejected",
        "case_count": len(cases),
        "passed_case_count": len(cases),
        "failed_case_count": 0,
        "replay_scope": "negative_replay_matrix_only_not_engine_proof",
        "proof_status": "not_proven",
        "source_audit_receipt_id": replay_audit_receipt["audit_receipt_id"],
        "descriptor_id": replay_audit_receipt["descriptor_id"],
        "descriptor_hash": replay_audit_receipt["descriptor_hash"],
        "workspace_effects": {
            "mutated": False,
            "touched_paths": [],
        },
        "tool_invocation": {
            "invoked": False,
            "tools": [],
        },
        "llm_invocation": {
            "invoked": False,
            "models": [],
        },
        "cases": cases,
    }


def build_noop_ledger_tamper_matrix_from_replay_audit(
    replay_audit_result: Any,
    *,
    tamper_cases: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    if not _is_mapping(replay_audit_result):
        return _reject(NOOP_TAMPER_MATRIX_INVALID_REPLAY_AUDIT_RESULT)

    if replay_audit_result.get("accepted") is not True:
        return _reject(
            *_replay_audit_rejection_codes(replay_audit_result),
            details={"replay_audit_result": dict(replay_audit_result)},
        )

    if not _valid_replay_audit_result(replay_audit_result):
        return _reject(NOOP_TAMPER_MATRIX_INVALID_REPLAY_AUDIT_RESULT)

    resolved_cases = list(tamper_cases) if tamper_cases is not None else default_tamper_cases()
    manifest_failure = _validate_case_manifest(resolved_cases)
    if manifest_failure is not None:
        return _reject(manifest_failure)

    completed_cases: list[dict[str, Any]] = []
    for case_spec in resolved_cases:
        case_run = _run_case(replay_audit_result, case_spec)
        if case_run["failed"]:
            return _reject(
                case_run["failure_code"],
                details={"case_result": case_run["case"]},
            )
        completed_cases.append(case_run["case"])

    tamper_matrix_receipt = _build_receipt(replay_audit_result, completed_cases)
    return {
        "accepted": True,
        "rejection_codes": [],
        "descriptor": dict(replay_audit_result["descriptor"]),
        "spine_contract": dict(replay_audit_result["spine_contract"]),
        "dry_run_plan": dict(replay_audit_result["dry_run_plan"]),
        "noop_bridge_receipt": dict(replay_audit_result["noop_bridge_receipt"]),
        "noop_ledger_receipt": dict(replay_audit_result["noop_ledger_receipt"]),
        "replay_audit_receipt": dict(replay_audit_result["replay_audit_receipt"]),
        "tamper_matrix_receipt": tamper_matrix_receipt,
        "workspace_probe": {
            "mutated": False,
            "touched_paths": [],
        },
    }


def build_noop_ledger_tamper_matrix(payload: Any) -> dict[str, Any]:
    replay_audit_result = build_descriptor_spine_noop_ledger_replay_audit(payload)
    if replay_audit_result.get("accepted") is not True:
        return _reject(
            *_replay_audit_rejection_codes(replay_audit_result),
            details={"replay_audit_result": dict(replay_audit_result)},
        )
    return build_noop_ledger_tamper_matrix_from_replay_audit(replay_audit_result)
