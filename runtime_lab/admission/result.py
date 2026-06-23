"""Admission receipt model and deterministic hash helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from collections.abc import Mapping
from typing import Any

from runtime_lab.common.deterministic import stable_json, sha256_text


@dataclass(frozen=True)
class AdmissionReceipt:
    """Deterministic admission receipt used by R113/R114."""

    descriptor_id: str
    descriptor_hash: str
    authority_packet_id: str | None
    authority_packet_hash: str | None
    kernel20_minimal_binding_status: bool
    kernel20_full_coverage_status: bool
    governance_decision: str
    authority_binding_ref: str | None
    accepted: bool
    rejection_code: str | None
    non_claims: list[str]
    receipt_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)



def compute_admission_receipt_payload_hash(receipt_payload: Mapping[str, Any]) -> str:
    """Compute deterministic hash over a receipt payload excluding the hash field."""

    sanitized = dict(receipt_payload)
    sanitized.pop("receipt_hash", None)
    return f"sha256:{sha256_text(stable_json(sanitized))}"


def make_admission_receipt(
    *,
    descriptor_id: str,
    descriptor_hash: str,
    kernel20_minimal_binding_status: bool,
    kernel20_full_coverage_status: bool,
    governance_decision: str,
    authority_binding_ref: str | None,
    accepted: bool,
    rejection_code: str | None,
    non_claims: list[str],
    authority_packet_id: str | None = None,
    authority_packet_hash: str | None = None,
) -> AdmissionReceipt:
    """Build a frozen admission receipt with a deterministic hash."""

    candidate = AdmissionReceipt(
        descriptor_id=descriptor_id,
        descriptor_hash=descriptor_hash,
        authority_packet_id=authority_packet_id,
        authority_packet_hash=authority_packet_hash,
        kernel20_minimal_binding_status=bool(kernel20_minimal_binding_status),
        kernel20_full_coverage_status=bool(kernel20_full_coverage_status),
        governance_decision=governance_decision,
        authority_binding_ref=authority_binding_ref,
        accepted=bool(accepted),
        rejection_code=rejection_code,
        non_claims=list(non_claims),
        receipt_hash="",
    )
    receipt_dict = candidate.to_dict()
    receipt_hash = compute_admission_receipt_payload_hash(receipt_dict)
    return AdmissionReceipt(
        descriptor_id=candidate.descriptor_id,
        descriptor_hash=candidate.descriptor_hash,
        authority_packet_id=candidate.authority_packet_id,
        authority_packet_hash=candidate.authority_packet_hash,
        kernel20_minimal_binding_status=candidate.kernel20_minimal_binding_status,
        kernel20_full_coverage_status=candidate.kernel20_full_coverage_status,
        governance_decision=candidate.governance_decision,
        authority_binding_ref=candidate.authority_binding_ref,
        accepted=candidate.accepted,
        rejection_code=candidate.rejection_code,
        non_claims=candidate.non_claims,
        receipt_hash=receipt_hash,
    )


def verify_admission_receipt(receipt: Mapping[str, Any] | AdmissionReceipt) -> bool:
    """Verify a persisted admission receipt hash with deterministic replay."""

    payload = asdict(receipt) if isinstance(receipt, AdmissionReceipt) else dict(receipt)
    provided = payload.get("receipt_hash")
    if not isinstance(provided, str) or not provided.startswith("sha256:"):
        return False
    return compute_admission_receipt_payload_hash(payload) == provided
