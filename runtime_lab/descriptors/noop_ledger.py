from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from runtime_lab.common.deterministic import sha256_text, stable_json

from .noop_bridge import build_descriptor_spine_noop_bridge


NOOP_LEDGER_INVALID_NOOP_BRIDGE_RESULT = "NOOP_LEDGER_INVALID_NOOP_BRIDGE_RESULT"
NOOP_LEDGER_NOOP_BRIDGE_REJECTED = "NOOP_LEDGER_NOOP_BRIDGE_REJECTED"
NOOP_LEDGER_WORKSPACE_MUTATION_FORBIDDEN = "NOOP_LEDGER_WORKSPACE_MUTATION_FORBIDDEN"
NOOP_LEDGER_TOOL_INVOCATION_FORBIDDEN = "NOOP_LEDGER_TOOL_INVOCATION_FORBIDDEN"
NOOP_LEDGER_LLM_INVOCATION_FORBIDDEN = "NOOP_LEDGER_LLM_INVOCATION_FORBIDDEN"
NOOP_LEDGER_GOVERNANCE_BINDING_MISSING = "NOOP_LEDGER_GOVERNANCE_BINDING_MISSING"
NOOP_LEDGER_REPLAY_BINDING_MISSING = "NOOP_LEDGER_REPLAY_BINDING_MISSING"
NOOP_LEDGER_REPLAY_PROOF_FORBIDDEN = "NOOP_LEDGER_REPLAY_PROOF_FORBIDDEN"
NOOP_LEDGER_TRANSITION_AUDIT_BINDING_MISSING = "NOOP_LEDGER_TRANSITION_AUDIT_BINDING_MISSING"

_LEDGER_CODE_MAP = {
    "NOOP_BRIDGE_WORKSPACE_MUTATION_FORBIDDEN": NOOP_LEDGER_WORKSPACE_MUTATION_FORBIDDEN,
    "NOOP_BRIDGE_TOOL_INVOCATION_FORBIDDEN": NOOP_LEDGER_TOOL_INVOCATION_FORBIDDEN,
    "NOOP_BRIDGE_LLM_INVOCATION_FORBIDDEN": NOOP_LEDGER_LLM_INVOCATION_FORBIDDEN,
    "NOOP_BRIDGE_GOVERNANCE_DECISION_MISSING": NOOP_LEDGER_GOVERNANCE_BINDING_MISSING,
    "NOOP_BRIDGE_REPLAY_PROOF_FORBIDDEN": NOOP_LEDGER_REPLAY_PROOF_FORBIDDEN,
    "NOOP_BRIDGE_TRANSITION_AUDIT_BINDING_MISSING": NOOP_LEDGER_TRANSITION_AUDIT_BINDING_MISSING,
    "REPLAY_WITHOUT_RECEIPT_LEDGER_HASH": NOOP_LEDGER_REPLAY_BINDING_MISSING,
}


def _is_mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


def _hash_mapping(value: Mapping[str, Any]) -> str:
    return f"sha256:{sha256_text(stable_json(dict(value)))}"


def _reject(*codes: str, details: Mapping[str, Any] | None = None) -> dict[str, Any]:
    result = {
        "accepted": False,
        "rejection_codes": list(codes),
        "noop_ledger_receipt": None,
        "workspace_probe": {
            "mutated": False,
            "touched_paths": [],
        },
    }
    if details is not None:
        result["details"] = dict(details)
    return result


def _ledger_rejection_codes(noop_bridge_result: Mapping[str, Any]) -> list[str]:
    codes: list[str] = []
    for code in noop_bridge_result.get("rejection_codes", []):
        codes.append(_LEDGER_CODE_MAP.get(code, code))
    if codes and codes[0] not in {
        "SPINE_CONTRACT_REJECTED",
        NOOP_LEDGER_WORKSPACE_MUTATION_FORBIDDEN,
        NOOP_LEDGER_TOOL_INVOCATION_FORBIDDEN,
        NOOP_LEDGER_LLM_INVOCATION_FORBIDDEN,
        NOOP_LEDGER_GOVERNANCE_BINDING_MISSING,
        NOOP_LEDGER_REPLAY_BINDING_MISSING,
        NOOP_LEDGER_REPLAY_PROOF_FORBIDDEN,
        NOOP_LEDGER_TRANSITION_AUDIT_BINDING_MISSING,
    }:
        codes.insert(0, NOOP_LEDGER_NOOP_BRIDGE_REJECTED)
    return codes


def _valid_noop_bridge_receipt(receipt: Any) -> bool:
    if not _is_mapping(receipt):
        return False
    if receipt.get("bridge_kind") != "descriptor_to_spine_noop_execution_bridge":
        return False
    required_fields = {
        "bridge_receipt_id",
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
        "descriptor_hash",
        "descriptor_id",
        "execution_result",
    }
    return required_fields <= set(receipt)


def _validate_receipt_boundaries(receipt: Mapping[str, Any]) -> list[str]:
    codes: list[str] = []

    governance = receipt.get("governance")
    if not (_is_mapping(governance) and governance.get("decision") == "approved" and governance.get("decision_ref")):
        codes.append(NOOP_LEDGER_GOVERNANCE_BINDING_MISSING)

    replay = receipt.get("replay")
    if not (
        _is_mapping(replay)
        and replay.get("receipt_ref")
        and replay.get("receipt_hash")
        and replay.get("ledger_ref")
    ):
        codes.append(NOOP_LEDGER_REPLAY_BINDING_MISSING)
    elif replay.get("proof_status") == "proven":
        codes.append(NOOP_LEDGER_REPLAY_PROOF_FORBIDDEN)

    if not (_is_mapping(receipt.get("audit")) and _is_mapping(receipt.get("transition"))):
        codes.append(NOOP_LEDGER_TRANSITION_AUDIT_BINDING_MISSING)

    workspace_effects = receipt.get("workspace_effects")
    if _is_mapping(workspace_effects) and workspace_effects.get("mutated") is True:
        codes.append(NOOP_LEDGER_WORKSPACE_MUTATION_FORBIDDEN)

    tool_invocation = receipt.get("tool_invocation")
    if _is_mapping(tool_invocation) and tool_invocation.get("invoked") is True:
        codes.append(NOOP_LEDGER_TOOL_INVOCATION_FORBIDDEN)

    llm_invocation = receipt.get("llm_invocation")
    if _is_mapping(llm_invocation) and llm_invocation.get("invoked") is True:
        codes.append(NOOP_LEDGER_LLM_INVOCATION_FORBIDDEN)

    return codes


def _build_noop_ledger_receipt(noop_bridge_receipt: Mapping[str, Any]) -> dict[str, Any]:
    receipt_hash = _hash_mapping(noop_bridge_receipt)
    governance_hash = _hash_mapping(noop_bridge_receipt["governance"])
    replay_hash = _hash_mapping(noop_bridge_receipt["replay"])
    ledger_event = {
        "event_kind": "noop_bridge_receipt_ledger_bound",
        "previous_event_hash": "GENESIS",
        "source_bridge_receipt_id": noop_bridge_receipt["bridge_receipt_id"],
        "descriptor_id": noop_bridge_receipt["descriptor_id"],
        "descriptor_hash": noop_bridge_receipt["descriptor_hash"],
        "receipt_hash": receipt_hash,
        "governance_hash": governance_hash,
        "replay_hash": replay_hash,
    }
    ledger_event_hash = _hash_mapping(ledger_event)
    ledger_chain_hash = _hash_mapping(
        {
            "previous_event_hash": ledger_event["previous_event_hash"],
            "ledger_event_hash": ledger_event_hash,
            "receipt_hash": receipt_hash,
            "governance_hash": governance_hash,
            "replay_hash": replay_hash,
        }
    )

    return {
        "binding_kind": "noop_bridge_receipt_ledger_binding",
        "binding_receipt_id": f"noop-ledger-{noop_bridge_receipt['descriptor_id']}",
        "source_bridge_receipt_id": noop_bridge_receipt["bridge_receipt_id"],
        "task": dict(noop_bridge_receipt["task"]),
        "state": dict(noop_bridge_receipt["state"]),
        "transition": dict(noop_bridge_receipt["transition"]),
        "audit": {
            **dict(noop_bridge_receipt["audit"]),
            "ledger_binding_ref": "ledger.current_event_hash",
        },
        "governance": dict(noop_bridge_receipt["governance"]),
        "artifacts": [dict(item) for item in noop_bridge_receipt["artifacts"]],
        "validation": {
            **dict(noop_bridge_receipt["validation"]),
            "ledger_binding_status": "bound_without_execution",
        },
        "replay": {
            **dict(noop_bridge_receipt["replay"]),
            "proof_status": "not_proven",
            "receipt_binding_status": "intent_receipt_only",
        },
        "workspace_effects": dict(noop_bridge_receipt["workspace_effects"]),
        "tool_invocation": dict(noop_bridge_receipt["tool_invocation"]),
        "llm_invocation": dict(noop_bridge_receipt["llm_invocation"]),
        "ledger": {
            **ledger_event,
            "current_event_hash": ledger_event_hash,
            "chain_position": 0,
        },
        "hashes": {
            "receipt_hash": receipt_hash,
            "governance_hash": governance_hash,
            "replay_hash": replay_hash,
            "ledger_event_hash": ledger_event_hash,
            "ledger_chain_hash": ledger_chain_hash,
        },
        "descriptor_hash": noop_bridge_receipt["descriptor_hash"],
        "descriptor_id": noop_bridge_receipt["descriptor_id"],
        "execution_result": "noop_ledger_receipt_only",
        "receipt_status": "ledger_bound_without_execution",
    }


def build_noop_ledger_binding(noop_bridge_result: Any) -> dict[str, Any]:
    if not _is_mapping(noop_bridge_result):
        return _reject(NOOP_LEDGER_INVALID_NOOP_BRIDGE_RESULT)

    if noop_bridge_result.get("accepted") is not True:
        return _reject(
            *_ledger_rejection_codes(noop_bridge_result),
            details={"noop_bridge_result": dict(noop_bridge_result)},
        )

    noop_bridge_receipt = noop_bridge_result.get("noop_bridge_receipt")
    if not _valid_noop_bridge_receipt(noop_bridge_receipt):
        return _reject(NOOP_LEDGER_INVALID_NOOP_BRIDGE_RESULT)

    boundary_codes = _validate_receipt_boundaries(noop_bridge_receipt)
    if boundary_codes:
        return _reject(*boundary_codes)

    noop_ledger_receipt = _build_noop_ledger_receipt(noop_bridge_receipt)
    return {
        "accepted": True,
        "rejection_codes": [],
        "descriptor": dict(noop_bridge_result["descriptor"]),
        "spine_contract": dict(noop_bridge_result["spine_contract"]),
        "dry_run_plan": dict(noop_bridge_result["dry_run_plan"]),
        "noop_bridge_receipt": dict(noop_bridge_receipt),
        "noop_ledger_receipt": noop_ledger_receipt,
        "workspace_probe": {
            "mutated": False,
            "touched_paths": [],
        },
    }


def build_descriptor_spine_noop_ledger_binding(payload: Any) -> dict[str, Any]:
    return build_noop_ledger_binding(build_descriptor_spine_noop_bridge(payload))
