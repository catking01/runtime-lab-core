from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .noop_ledger import (
    _build_noop_ledger_receipt,
    _valid_noop_bridge_receipt,
    _validate_receipt_boundaries,
    build_descriptor_spine_noop_ledger_binding,
)


NOOP_REPLAY_AUDIT_INVALID_NOOP_LEDGER_RESULT = "NOOP_REPLAY_AUDIT_INVALID_NOOP_LEDGER_RESULT"
NOOP_REPLAY_AUDIT_NOOP_LEDGER_REJECTED = "NOOP_REPLAY_AUDIT_NOOP_LEDGER_REJECTED"
NOOP_REPLAY_AUDIT_RECEIPT_HASH_MISMATCH = "NOOP_REPLAY_AUDIT_RECEIPT_HASH_MISMATCH"
NOOP_REPLAY_AUDIT_GOVERNANCE_HASH_MISMATCH = "NOOP_REPLAY_AUDIT_GOVERNANCE_HASH_MISMATCH"
NOOP_REPLAY_AUDIT_REPLAY_HASH_MISMATCH = "NOOP_REPLAY_AUDIT_REPLAY_HASH_MISMATCH"
NOOP_REPLAY_AUDIT_LEDGER_EVENT_HASH_MISMATCH = "NOOP_REPLAY_AUDIT_LEDGER_EVENT_HASH_MISMATCH"
NOOP_REPLAY_AUDIT_LEDGER_CHAIN_HASH_MISMATCH = "NOOP_REPLAY_AUDIT_LEDGER_CHAIN_HASH_MISMATCH"
NOOP_REPLAY_AUDIT_WORKSPACE_MUTATION_FORBIDDEN = "NOOP_REPLAY_AUDIT_WORKSPACE_MUTATION_FORBIDDEN"
NOOP_REPLAY_AUDIT_TOOL_INVOCATION_FORBIDDEN = "NOOP_REPLAY_AUDIT_TOOL_INVOCATION_FORBIDDEN"
NOOP_REPLAY_AUDIT_LLM_INVOCATION_FORBIDDEN = "NOOP_REPLAY_AUDIT_LLM_INVOCATION_FORBIDDEN"
NOOP_REPLAY_AUDIT_REPLAY_PROOF_FORBIDDEN = "NOOP_REPLAY_AUDIT_REPLAY_PROOF_FORBIDDEN"

_REPLAY_AUDIT_CODE_MAP = {
    "NOOP_LEDGER_WORKSPACE_MUTATION_FORBIDDEN": NOOP_REPLAY_AUDIT_WORKSPACE_MUTATION_FORBIDDEN,
    "NOOP_LEDGER_TOOL_INVOCATION_FORBIDDEN": NOOP_REPLAY_AUDIT_TOOL_INVOCATION_FORBIDDEN,
    "NOOP_LEDGER_LLM_INVOCATION_FORBIDDEN": NOOP_REPLAY_AUDIT_LLM_INVOCATION_FORBIDDEN,
    "NOOP_LEDGER_REPLAY_PROOF_FORBIDDEN": NOOP_REPLAY_AUDIT_REPLAY_PROOF_FORBIDDEN,
}


def _is_mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


def _reject(*codes: str, details: Mapping[str, Any] | None = None) -> dict[str, Any]:
    result = {
        "accepted": False,
        "rejection_codes": list(codes),
        "replay_audit_receipt": None,
        "workspace_probe": {
            "mutated": False,
            "touched_paths": [],
        },
    }
    if details is not None:
        result["details"] = dict(details)
    return result


def _replay_audit_rejection_codes(noop_ledger_result: Mapping[str, Any]) -> list[str]:
    codes: list[str] = []
    for code in noop_ledger_result.get("rejection_codes", []):
        codes.append(_REPLAY_AUDIT_CODE_MAP.get(code, code))
    if codes and codes[0] not in {
        "SPINE_CONTRACT_REJECTED",
        NOOP_REPLAY_AUDIT_WORKSPACE_MUTATION_FORBIDDEN,
        NOOP_REPLAY_AUDIT_TOOL_INVOCATION_FORBIDDEN,
        NOOP_REPLAY_AUDIT_LLM_INVOCATION_FORBIDDEN,
        NOOP_REPLAY_AUDIT_REPLAY_PROOF_FORBIDDEN,
    }:
        codes.insert(0, NOOP_REPLAY_AUDIT_NOOP_LEDGER_REJECTED)
    return codes


def _valid_noop_ledger_receipt(receipt: Any) -> bool:
    if not _is_mapping(receipt):
        return False
    if receipt.get("binding_kind") != "noop_bridge_receipt_ledger_binding":
        return False
    required_fields = {
        "binding_receipt_id",
        "source_bridge_receipt_id",
        "task",
        "state",
        "transition",
        "audit",
        "governance",
        "artifacts",
        "validation",
        "replay",
        "workspace_effects",
        "tool_invocation",
        "llm_invocation",
        "ledger",
        "hashes",
        "descriptor_hash",
        "descriptor_id",
        "execution_result",
        "receipt_status",
    }
    return required_fields <= set(receipt)


def _boundary_codes(receipt: Mapping[str, Any]) -> list[str]:
    codes: list[str] = []
    workspace_effects = receipt.get("workspace_effects")
    if _is_mapping(workspace_effects) and workspace_effects.get("mutated") is True:
        codes.append(NOOP_REPLAY_AUDIT_WORKSPACE_MUTATION_FORBIDDEN)
    tool_invocation = receipt.get("tool_invocation")
    if _is_mapping(tool_invocation) and tool_invocation.get("invoked") is True:
        codes.append(NOOP_REPLAY_AUDIT_TOOL_INVOCATION_FORBIDDEN)
    llm_invocation = receipt.get("llm_invocation")
    if _is_mapping(llm_invocation) and llm_invocation.get("invoked") is True:
        codes.append(NOOP_REPLAY_AUDIT_LLM_INVOCATION_FORBIDDEN)
    replay = receipt.get("replay")
    if _is_mapping(replay) and replay.get("proof_status") == "proven":
        codes.append(NOOP_REPLAY_AUDIT_REPLAY_PROOF_FORBIDDEN)
    return codes


def _expected_noop_ledger_receipt(noop_ledger_result: Mapping[str, Any]) -> dict[str, Any]:
    noop_bridge_receipt = noop_ledger_result["noop_bridge_receipt"]
    return _build_noop_ledger_receipt(noop_bridge_receipt)


def _mismatch_codes(actual: Mapping[str, Any], expected: Mapping[str, Any]) -> list[str]:
    codes: list[str] = []

    actual_hashes = actual["hashes"]
    expected_hashes = expected["hashes"]
    if actual_hashes["receipt_hash"] != expected_hashes["receipt_hash"]:
        codes.append(NOOP_REPLAY_AUDIT_RECEIPT_HASH_MISMATCH)
    if actual_hashes["governance_hash"] != expected_hashes["governance_hash"] or actual["governance"] != expected["governance"]:
        codes.append(NOOP_REPLAY_AUDIT_GOVERNANCE_HASH_MISMATCH)
    if actual_hashes["replay_hash"] != expected_hashes["replay_hash"] or actual["replay"] != expected["replay"]:
        codes.append(NOOP_REPLAY_AUDIT_REPLAY_HASH_MISMATCH)
    if actual_hashes["ledger_event_hash"] != expected_hashes["ledger_event_hash"] or actual["ledger"] != expected["ledger"]:
        codes.append(NOOP_REPLAY_AUDIT_LEDGER_EVENT_HASH_MISMATCH)
    if actual_hashes["ledger_chain_hash"] != expected_hashes["ledger_chain_hash"]:
        codes.append(NOOP_REPLAY_AUDIT_LEDGER_CHAIN_HASH_MISMATCH)

    return codes


def _build_replay_audit_receipt(
    actual: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> dict[str, Any]:
    actual_hashes = actual["hashes"]
    expected_hashes = expected["hashes"]
    return {
        "audit_kind": "noop_ledger_replay_audit",
        "audit_receipt_id": f"noop-replay-audit-{actual['descriptor_id']}",
        "source_binding_receipt_id": actual["binding_receipt_id"],
        "audit_status": "rederived_and_verified",
        "proof_status": "not_proven",
        "descriptor_id": actual["descriptor_id"],
        "descriptor_hash": actual["descriptor_hash"],
        "verified_hashes": {
            "receipt_hash_match": actual_hashes["receipt_hash"] == expected_hashes["receipt_hash"],
            "governance_hash_match": actual_hashes["governance_hash"] == expected_hashes["governance_hash"],
            "replay_hash_match": actual_hashes["replay_hash"] == expected_hashes["replay_hash"],
            "ledger_event_hash_match": actual_hashes["ledger_event_hash"] == expected_hashes["ledger_event_hash"],
            "ledger_chain_hash_match": actual_hashes["ledger_chain_hash"] == expected_hashes["ledger_chain_hash"],
        },
        "actual_hashes": dict(actual_hashes),
        "expected_hashes": dict(expected_hashes),
        "governance": dict(actual["governance"]),
        "replay": dict(actual["replay"]),
        "ledger": dict(actual["ledger"]),
        "workspace_effects": dict(actual["workspace_effects"]),
        "tool_invocation": dict(actual["tool_invocation"]),
        "llm_invocation": dict(actual["llm_invocation"]),
    }


def build_noop_ledger_replay_audit(noop_ledger_result: Any) -> dict[str, Any]:
    if not _is_mapping(noop_ledger_result):
        return _reject(NOOP_REPLAY_AUDIT_INVALID_NOOP_LEDGER_RESULT)

    if noop_ledger_result.get("accepted") is not True:
        return _reject(
            *_replay_audit_rejection_codes(noop_ledger_result),
            details={"noop_ledger_result": dict(noop_ledger_result)},
        )

    noop_bridge_receipt = noop_ledger_result.get("noop_bridge_receipt")
    noop_ledger_receipt = noop_ledger_result.get("noop_ledger_receipt")
    if not (_valid_noop_bridge_receipt(noop_bridge_receipt) and _valid_noop_ledger_receipt(noop_ledger_receipt)):
        return _reject(NOOP_REPLAY_AUDIT_INVALID_NOOP_LEDGER_RESULT)

    bridge_boundary_codes = _validate_receipt_boundaries(noop_bridge_receipt)
    if bridge_boundary_codes:
        return _reject(NOOP_REPLAY_AUDIT_INVALID_NOOP_LEDGER_RESULT, details={"bridge_boundary_codes": bridge_boundary_codes})

    boundary_codes = _boundary_codes(noop_ledger_receipt)
    if boundary_codes:
        return _reject(*boundary_codes)

    expected = _expected_noop_ledger_receipt(noop_ledger_result)
    mismatch_codes = _mismatch_codes(noop_ledger_receipt, expected)
    if mismatch_codes:
        return _reject(*mismatch_codes)

    replay_audit_receipt = _build_replay_audit_receipt(noop_ledger_receipt, expected)
    return {
        "accepted": True,
        "rejection_codes": [],
        "descriptor": dict(noop_ledger_result["descriptor"]),
        "spine_contract": dict(noop_ledger_result["spine_contract"]),
        "dry_run_plan": dict(noop_ledger_result["dry_run_plan"]),
        "noop_bridge_receipt": dict(noop_bridge_receipt),
        "noop_ledger_receipt": dict(noop_ledger_receipt),
        "replay_audit_receipt": replay_audit_receipt,
        "workspace_probe": {
            "mutated": False,
            "touched_paths": [],
        },
    }


def build_descriptor_spine_noop_ledger_replay_audit(payload: Any) -> dict[str, Any]:
    return build_noop_ledger_replay_audit(build_descriptor_spine_noop_ledger_binding(payload))
