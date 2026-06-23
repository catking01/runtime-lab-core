"""Admission controller for descriptor intake.

This composes existing validation gates (policy, spine contract, descriptor
schema) and emits a deterministic admission receipt. It is intentionally fail
closed and does not introduce runtime execution behavior.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from runtime_lab import descriptors
from runtime_lab.descriptors.errors import DescriptorValidationError
from runtime_lab.descriptors import spine_contract
from runtime_lab.descriptors import schema
from runtime_lab.kernel20.coverage import describe_kernel20_coverage

from .errors import (
    ADMISSION_DESERIALIZATION_ERROR,
    ADMISSION_VALIDATION_ERROR,
    ADMISSION_DESCRIPTOR_VALIDATION_ERROR,
    AdmissionDeserializationError,
    AdmissionValidationError,
)
from runtime_lab.authority.errors import AUTHORITY_PACKET_REQUIRED
from runtime_lab.authority.verify import verify_authority_packet
from .policy import (
    validate_admission_policy,
)
from .result import make_admission_receipt

FULL_KERNEL_CLAIM_PATTERNS = (
    re.compile(r"\bfull\s+kernel20\b"),
    re.compile(r"\bkernel20\s+full\b"),
    re.compile(r"\bfull\s+coverage\b"),
)
NEGATED_CLAIM_PATTERNS = (
    re.compile(r"\bnot\s+full\s+kernel20\b"),
    re.compile(r"\bkernel20\s+not\s+full\b"),
    re.compile(r"\bnot\s+full\s+coverage\b"),
    re.compile(r"\bfull\s+coverage\s+not\b"),
    re.compile(r"\bno\s+full\s+kernel20\b"),
)

_DESCRIPTOR_ADMISSION_EXTENSIONS = {
    "kernel_binding",
    "minimal_spine_binding",
    "tool_invocation",
    "llm_invocation",
    "workspace_mutation",
    "actor_transfer",
    "handoff_record",
    "state_mutation",
}


def _is_mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


def _unique_codes(raw_codes: list[str]) -> list[str]:
    deduped: list[str] = []
    for code in raw_codes:
        if code and code not in deduped:
            deduped.append(code)
    return deduped


def _extract_text_fields(payload: Mapping[str, Any]) -> list[str]:
    text_fields = []
    for field in ("compatibility_refs", "non_claims", "notes", "preconditions", "postconditions"):
        value = payload.get(field)
        if isinstance(value, str):
            text_fields.append(value)
        elif isinstance(value, list):
            text_fields.extend(str(item) for item in value if isinstance(item, str))
    return text_fields


def _has_disallowed_full_kernel20_claim(payload: Mapping[str, Any]) -> bool:
    for line in _extract_text_fields(payload):
        normalized = re.sub(r"\s+", " ", line.lower())
        if not FULL_KERNEL_CLAIM_PATTERNS[0].search(normalized) and not FULL_KERNEL_CLAIM_PATTERNS[1].search(
            normalized
        ):
            if FULL_KERNEL_CLAIM_PATTERNS[2].search(normalized):
                # Full coverage references must still pair with explicit full-kernel semantics.
                if not any(pattern.search(normalized) for pattern in NEGATED_CLAIM_PATTERNS):
                    return True
            continue

        if not any(pattern.search(normalized) for pattern in NEGATED_CLAIM_PATTERNS):
            return True

    return False


def _normalize_non_claims(payload: Mapping[str, Any]) -> list[str]:
    non_claims = payload.get("non_claims", [])
    if not isinstance(non_claims, list):
        return []
    return [str(item) for item in non_claims if isinstance(item, str)]


def _authority_binding_reference(payload: Mapping[str, Any]) -> str | None:
    governance = payload.get("governance_requirements")
    if _is_mapping(governance):
        decision_ref = governance.get("decision_ref")
        if isinstance(decision_ref, str) and decision_ref:
            return decision_ref
    return None


def _descriptor_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    allowed = set(schema.ALLOWED_FIELDS)
    return {key: value for key, value in payload.items() if key in allowed}


def _has_unexpected_payload_fields(payload: Mapping[str, Any]) -> list[str]:
    allowed = set(schema.ALLOWED_FIELDS) | _DESCRIPTOR_ADMISSION_EXTENSIONS
    return sorted(key for key in payload.keys() if key not in allowed)


def _governance_decision(payload: Mapping[str, Any]) -> str:
    governance = payload.get("governance_requirements")
    if _is_mapping(governance):
        decision = governance.get("decision")
        if isinstance(decision, str):
            return decision
    return ""


def _make_rejection_result(
    *,
    payload: Mapping[str, Any],
    rejection_codes: list[str],
    spine_result: dict[str, Any] | None,
    kernel20_report: dict[str, Any] | None,
) -> dict[str, Any]:
    descriptor = dict(payload)
    kernel20_report = dict(kernel20_report or {})

    descriptor_hash = descriptor.get("canonical_hash") if isinstance(descriptor.get("canonical_hash"), str) else ""
    descriptor_id = descriptor.get("descriptor_id") if isinstance(descriptor.get("descriptor_id"), str) else ""

    if not descriptor_hash and _is_mapping(spine_result):
        # Use canonical hash from successful spine/validation path if present.
        descriptor_hash = str(descriptor.get("canonical_hash", ""))
    if not descriptor_id and _is_mapping(spine_result):
        descriptor_id = str(descriptor.get("descriptor_id", ""))

    codes = _unique_codes(list(rejection_codes) + [ADMISSION_VALIDATION_ERROR])
    receipt = make_admission_receipt(
        descriptor_id=descriptor_id,
        descriptor_hash=str(descriptor_hash),
        kernel20_minimal_binding_status=bool(kernel20_report.get("minimal_coverage")) if _is_mapping(kernel20_report) else False,
        kernel20_full_coverage_status=bool(kernel20_report.get("full_coverage")) if _is_mapping(kernel20_report) else False,
        governance_decision=_governance_decision(descriptor),
        authority_binding_ref=_authority_binding_reference(descriptor),
        accepted=False,
        rejection_code=codes[0] if codes else ADMISSION_VALIDATION_ERROR,
        non_claims=_normalize_non_claims(descriptor),
    )

    return {
        "accepted": False,
        "rejection_codes": codes,
        "rejection_code": codes[0] if codes else ADMISSION_VALIDATION_ERROR,
        "descriptor": descriptor,
        "kernel20_coverage": kernel20_report,
        "spine_contract": spine_result,
        "admission_receipt": receipt.to_dict(),
    }


def _make_accept_result(
    *,
    payload: Mapping[str, Any],
    spine_result: dict[str, Any] | None,
    kernel20_report: dict[str, Any],
) -> dict[str, Any]:
    descriptor = dict(payload)

    receipt = make_admission_receipt(
        descriptor_id=str(descriptor.get("descriptor_id", "")),
        descriptor_hash=str(descriptor.get("canonical_hash", "")),
        kernel20_minimal_binding_status=bool(kernel20_report.get("minimal_coverage")),
        kernel20_full_coverage_status=bool(kernel20_report.get("full_coverage")),
        governance_decision=_governance_decision(descriptor),
        authority_binding_ref=_authority_binding_reference(descriptor),
        accepted=True,
        rejection_code=None,
        non_claims=_normalize_non_claims(descriptor),
    )

    return {
        "accepted": True,
        "rejection_codes": [],
        "rejection_code": "",
        "descriptor": descriptor,
        "kernel20_coverage": kernel20_report,
        "spine_contract": spine_result,
        "admission_receipt": receipt.to_dict(),
    }


def _bind_authority_receipt(result: dict[str, Any], authority_result: Mapping[str, Any]) -> dict[str, Any]:
    receipt = result.get("admission_receipt")
    if not _is_mapping(receipt):
        return result

    rebound = make_admission_receipt(
        descriptor_id=str(receipt.get("descriptor_id", "")),
        descriptor_hash=str(receipt.get("descriptor_hash", "")),
        kernel20_minimal_binding_status=bool(receipt.get("kernel20_minimal_binding_status")),
        kernel20_full_coverage_status=bool(receipt.get("kernel20_full_coverage_status")),
        governance_decision=str(receipt.get("governance_decision", "")),
        authority_binding_ref=receipt.get("authority_binding_ref")
        if isinstance(receipt.get("authority_binding_ref"), str)
        else None,
        authority_packet_id=authority_result.get("authority_packet_id")
        if isinstance(authority_result.get("authority_packet_id"), str)
        else None,
        authority_packet_hash=authority_result.get("authority_packet_hash")
        if isinstance(authority_result.get("authority_packet_hash"), str)
        else None,
        accepted=bool(receipt.get("accepted")),
        rejection_code=receipt.get("rejection_code") if isinstance(receipt.get("rejection_code"), str) else None,
        non_claims=list(receipt.get("non_claims", [])) if isinstance(receipt.get("non_claims"), list) else [],
    )
    updated = dict(result)
    updated["admission_receipt"] = rebound.to_dict()
    return updated


def _parse_descriptor(payload: Mapping[str, Any]) -> dict[str, Any]:
    try:
        return descriptors.validator.validate_descriptor(_descriptor_payload(payload))
    except DescriptorValidationError as exc:
        raise AdmissionValidationError(ADMISSION_DESCRIPTOR_VALIDATION_ERROR, exc.code) from exc


def evaluate_admission(payload: Any) -> dict[str, Any]:
    """Evaluate a payload through fail-closed admission gates."""

    if not _is_mapping(payload):
        raise AdmissionDeserializationError(ADMISSION_DESERIALIZATION_ERROR, "payload is not a mapping")

    payload_map = dict(payload)

    policy_codes = _unique_codes(list(validate_admission_policy(payload_map)))
    if policy_codes:
        return _make_rejection_result(
            payload=payload_map,
            rejection_codes=[ADMISSION_VALIDATION_ERROR] + policy_codes,
            spine_result=None,
            kernel20_report=None,
        )

    unexpected_fields = _has_unexpected_payload_fields(payload_map)
    if unexpected_fields:
        return _make_rejection_result(
            payload=payload_map,
            rejection_codes=[ADMISSION_VALIDATION_ERROR, "B1_DESCRIPTOR_UNKNOWN_FIELD"],
            spine_result=None,
            kernel20_report=None,
        )

    contract_result = spine_contract.validate_descriptor_spine_contract(payload_map)
    if not contract_result.get("accepted", False):
        return _make_rejection_result(
            payload=payload_map,
            rejection_codes=[ADMISSION_VALIDATION_ERROR, "SPINE_CONTRACT_REJECTED"]
            + list(dict.fromkeys(contract_result.get("rejection_codes", []))),
            spine_result=contract_result,
            kernel20_report=contract_result.get("kernel20_coverage_report")
            if isinstance(contract_result.get("kernel20_coverage_report"), Mapping)
            else None,
        )

    try:
        validated_payload = _parse_descriptor(payload_map)
    except AdmissionValidationError as exc:
        details = [str(exc)]
        if exc.detail:
            details = [str(exc.code), str(exc.detail)]
        return _make_rejection_result(
            payload=payload_map,
            rejection_codes=[ADMISSION_VALIDATION_ERROR, ADMISSION_DESCRIPTOR_VALIDATION_ERROR] + details,
            spine_result=contract_result,
            kernel20_report=contract_result.get("kernel20_coverage_report")
            if isinstance(contract_result.get("kernel20_coverage_report"), Mapping)
            else None,
        )

    if isinstance(contract_result.get("kernel20_coverage_report"), Mapping):
        kernel20_report = dict(contract_result["kernel20_coverage_report"])
    else:
        kernel20_report = describe_kernel20_coverage(payload_map.get("kernel_binding")) if _is_mapping(payload_map.get("kernel_binding")) else {
        "kernel_name": None,
        "minimal_coverage": False,
        "full_coverage": False,
        "declared_coverage": [],
        "missing_minimal": [],
        "missing_full": [],
    }

    rejection_codes: list[str] = []
    if not kernel20_report.get("minimal_coverage", False):
        rejection_codes.append("KERNEL20_MINIMAL_BOUNDARY_NOT_MET")

    if _has_disallowed_full_kernel20_claim(validated_payload) and not kernel20_report.get("full_coverage", False):
        rejection_codes.append("KERNEL20_FULL_COVERAGE_CLAIM_BOUNDARY_VIOLATION")

    if rejection_codes:
        return _make_rejection_result(
            payload=validated_payload,
            rejection_codes=[ADMISSION_VALIDATION_ERROR] + rejection_codes,
            spine_result=contract_result,
            kernel20_report=kernel20_report,
        )

    return _make_accept_result(
        payload=validated_payload,
        spine_result=contract_result,
        kernel20_report=kernel20_report,
    )


def evaluate_authorized_admission(payload: Any, authority_packet: Any) -> dict[str, Any]:
    """Evaluate descriptor intake through the R114 authority-packet gate."""

    if not _is_mapping(payload):
        return _make_rejection_result(
            payload={},
            rejection_codes=[ADMISSION_DESERIALIZATION_ERROR],
            spine_result=None,
            kernel20_report=None,
        )

    payload_map = dict(payload)
    if authority_packet is None:
        result = _make_rejection_result(
            payload=payload_map,
            rejection_codes=[AUTHORITY_PACKET_REQUIRED],
            spine_result=None,
            kernel20_report=None,
        )
        result["authority"] = {
            "accepted": False,
            "rejection_codes": [AUTHORITY_PACKET_REQUIRED],
            "authority_packet_id": None,
            "authority_packet_hash": None,
        }
    else:
        authority_result = verify_authority_packet(authority_packet, payload_map)
        if not authority_result.get("accepted", False):
            result = _make_rejection_result(
                payload=payload_map,
                rejection_codes=list(authority_result.get("rejection_codes", [])),
                spine_result=None,
                kernel20_report=None,
            )
            result["authority"] = authority_result
        else:
            result = _bind_authority_receipt(evaluate_admission(payload_map), authority_result)
            result["authority"] = authority_result

    result["executor_dispatch_performed"] = False
    result["tool_invocation_performed"] = False
    result["llm_invocation_performed"] = False
    return result


def admit_descriptor_payload(payload: Any) -> dict[str, Any]:
    """Backward-compatible wrapper returning a structured admission result."""

    try:
        return evaluate_admission(payload)
    except AdmissionValidationError as exc:
        return _make_rejection_result(
            payload=dict(payload) if _is_mapping(payload) else {},
            rejection_codes=[ADMISSION_VALIDATION_ERROR, str(exc)],
            spine_result=None,
            kernel20_report=None,
        )
    except AdmissionDeserializationError as exc:
        return _make_rejection_result(
            payload={},
            rejection_codes=[ADMISSION_DESERIALIZATION_ERROR, str(exc)],
            spine_result=None,
            kernel20_report=None,
        )
