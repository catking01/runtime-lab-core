"""Append-only event ledger v1 for R118.

R118 records deterministic event envelopes and validates a hash-linked ledger
chain. It intentionally does not replay events, dispatch executors, invoke
tools, invoke LLMs, or use network access.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from runtime_lab.authority.canonical import canonical_hash

GENESIS_PREVIOUS_EVENT_HASH = "GENESIS"

LEDGER_EVENT_MALFORMED = "LEDGER_EVENT_MALFORMED"
LEDGER_EVENT_TYPE_NOT_ALLOWED = "LEDGER_EVENT_TYPE_NOT_ALLOWED"
LEDGER_FORBIDDEN_FIELD = "LEDGER_FORBIDDEN_FIELD"
LEDGER_PREVIOUS_EVENT_HASH_REQUIRED = "LEDGER_PREVIOUS_EVENT_HASH_REQUIRED"
LEDGER_PREVIOUS_EVENT_HASH_MISMATCH = "LEDGER_PREVIOUS_EVENT_HASH_MISMATCH"
LEDGER_REQUIRED_RECEIPT_HASH_MISSING = "LEDGER_REQUIRED_RECEIPT_HASH_MISSING"
LEDGER_DUPLICATE_EVENT_ID = "LEDGER_DUPLICATE_EVENT_ID"
LEDGER_CHAIN_DISCONTINUITY = "LEDGER_CHAIN_DISCONTINUITY"
LEDGER_EVENT_HASH_MISMATCH = "LEDGER_EVENT_HASH_MISMATCH"
LEDGER_EXPECTED_EVENT_COUNT_MISMATCH = "LEDGER_EXPECTED_EVENT_COUNT_MISMATCH"
LEDGER_EXPECTED_LEDGER_CHAIN_HASH_MISMATCH = "LEDGER_EXPECTED_LEDGER_CHAIN_HASH_MISMATCH"
LEDGER_EXPECTED_TERMINAL_EVENT_HASH_MISMATCH = "LEDGER_EXPECTED_TERMINAL_EVENT_HASH_MISMATCH"
LEDGER_CHAIN_MALFORMED = "LEDGER_CHAIN_MALFORMED"
LEDGER_CHAIN_INVALID = "LEDGER_CHAIN_INVALID"

ALLOWED_EVENT_TYPES = {
    "task_admitted",
    "authority_bound",
    "workspace_transaction_prepared",
    "artifact_registered",
    "executor_started",
    "executor_completed",
    "validation_completed",
}

BASE_EVENT_FIELDS = {
    "schema_version",
    "event_id",
    "event_type",
    "previous_event_hash",
    "task_id",
    "descriptor_hash",
    "authority_receipt_hash",
    "workspace_transaction_receipt_hash",
    "artifact_receipt_hash",
    "executor_receipt_hash",
    "validation_receipt_hash",
    "event_hash",
}

FORBIDDEN_EVENT_FIELDS = {
    "shell_command",
    "subprocess",
    "command",
    "tool_call",
    "tool_invocation",
    "llm_call",
    "llm_invocation",
    "network_endpoint",
    "http_request",
    "socket",
    "replay_engine",
    "executor_dispatch",
    "arbitrary_action",
}

EVENT_REQUIRED_RECEIPT_HASHES = {
    "task_admitted": ("authority_receipt_hash",),
    "authority_bound": ("authority_receipt_hash",),
    "workspace_transaction_prepared": ("authority_receipt_hash", "workspace_transaction_receipt_hash"),
    "artifact_registered": ("authority_receipt_hash", "workspace_transaction_receipt_hash", "artifact_receipt_hash"),
    "executor_started": (
        "authority_receipt_hash",
        "workspace_transaction_receipt_hash",
        "artifact_receipt_hash",
        "executor_receipt_hash",
    ),
    "executor_completed": (
        "authority_receipt_hash",
        "workspace_transaction_receipt_hash",
        "artifact_receipt_hash",
        "executor_receipt_hash",
    ),
    "validation_completed": (
        "authority_receipt_hash",
        "workspace_transaction_receipt_hash",
        "artifact_receipt_hash",
        "executor_receipt_hash",
        "validation_receipt_hash",
    ),
}


def _is_mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


def _is_hash(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("sha256:") and len(value.removeprefix("sha256:")) == 64


def _dedupe(codes: list[str]) -> list[str]:
    return list(dict.fromkeys(codes))


def _non_execution_flags() -> dict[str, bool]:
    return {
        "replay_engine_performed": False,
        "executor_invocation_performed": False,
        "tool_invocation_performed": False,
        "llm_invocation_performed": False,
        "network_access_performed": False,
    }


def _base_result(
    *,
    accepted: bool,
    status: str,
    rejection_codes: list[str],
    event: dict[str, Any] | None = None,
    receipt: dict[str, Any] | None = None,
    ledger: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    result = {
        "accepted": accepted,
        "status": status,
        "rejection_codes": _dedupe(rejection_codes),
        "event": event,
        "receipt": receipt,
        "ledger": ledger,
    }
    result.update(_non_execution_flags())
    return result


def _reject(code: str) -> dict[str, Any]:
    return _base_result(accepted=False, status="rejected", rejection_codes=[code])


def _chain_report(
    *,
    accepted: bool,
    status: str,
    rejection_codes: list[str],
    ledger_chain_hash: str | None = None,
) -> dict[str, Any]:
    result = {
        "accepted": accepted,
        "status": status,
        "rejection_codes": _dedupe(rejection_codes),
        "ledger_chain_hash": ledger_chain_hash,
    }
    result.update(_non_execution_flags())
    return result


def _event_hash_payload(event: Mapping[str, Any]) -> dict[str, Any]:
    candidate = dict(event)
    candidate.pop("event_hash", None)
    return candidate


def _receipt_hash_payload(receipt: Mapping[str, Any]) -> dict[str, Any]:
    candidate = dict(receipt)
    candidate.pop("receipt_hash", None)
    return candidate


def canonical_event_hash(event: Mapping[str, Any]) -> str:
    """Return the deterministic hash for a ledger event envelope."""

    return canonical_hash(_event_hash_payload(event))


def _ledger_chain_hash(ledger: list[Mapping[str, Any]]) -> str:
    return canonical_hash(
        {
            "schema_version": "ledger_chain.v1",
            "event_hashes": [event.get("event_hash") for event in ledger],
        }
    )


def _event_structure_error(event: Mapping[str, Any]) -> str | None:
    if FORBIDDEN_EVENT_FIELDS & set(event):
        return LEDGER_FORBIDDEN_FIELD
    if set(event) - BASE_EVENT_FIELDS:
        return LEDGER_FORBIDDEN_FIELD

    required_strings = ("schema_version", "event_id", "event_type", "previous_event_hash", "task_id", "descriptor_hash")
    for field in required_strings:
        if not isinstance(event.get(field), str) or not event.get(field):
            if field == "previous_event_hash":
                return LEDGER_PREVIOUS_EVENT_HASH_REQUIRED
            return LEDGER_EVENT_MALFORMED

    if event.get("schema_version") != "ledger_event.v1":
        return LEDGER_EVENT_MALFORMED
    event_type = event.get("event_type")
    if event_type not in ALLOWED_EVENT_TYPES:
        return LEDGER_EVENT_TYPE_NOT_ALLOWED
    if not _is_hash(event.get("descriptor_hash")):
        return LEDGER_EVENT_MALFORMED

    for field in EVENT_REQUIRED_RECEIPT_HASHES[event_type]:
        if not _is_hash(event.get(field)):
            return LEDGER_REQUIRED_RECEIPT_HASH_MISSING
    return None


def _existing_ledger(value: Any) -> list[dict[str, Any]] | None:
    if not isinstance(value, list):
        return None
    if not all(_is_mapping(event) for event in value):
        return None
    return [dict(event) for event in value]


def _append_receipt(event: Mapping[str, Any], *, event_index: int, ledger_chain_hash: str) -> dict[str, Any]:
    receipt = {
        "schema_version": "ledger_append_receipt.v1",
        "event_id": event["event_id"],
        "event_type": event["event_type"],
        "event_index": event_index,
        "event_hash": event["event_hash"],
        "previous_event_hash": event["previous_event_hash"],
        "ledger_chain_hash": ledger_chain_hash,
        "task_id": event["task_id"],
        "descriptor_hash": event["descriptor_hash"],
        "authority_receipt_hash": event.get("authority_receipt_hash"),
        "workspace_transaction_receipt_hash": event.get("workspace_transaction_receipt_hash"),
        "artifact_receipt_hash": event.get("artifact_receipt_hash"),
        "executor_receipt_hash": event.get("executor_receipt_hash"),
        "validation_receipt_hash": event.get("validation_receipt_hash"),
        "replay_engine_performed": False,
        "executor_invocation_performed": False,
        "tool_invocation_performed": False,
        "llm_invocation_performed": False,
        "network_access_performed": False,
        "receipt_hash": "",
    }
    receipt["receipt_hash"] = canonical_hash(_receipt_hash_payload(receipt))
    return receipt


def verify_ledger_append_receipt(receipt: Mapping[str, Any]) -> bool:
    """Verify a deterministic R118 ledger append receipt."""

    if not _is_mapping(receipt):
        return False
    provided = receipt.get("receipt_hash")
    return isinstance(provided, str) and provided.startswith("sha256:") and canonical_hash(
        _receipt_hash_payload(receipt)
    ) == provided


def validate_ledger_chain(
    ledger: Any,
    *,
    expected_event_count: int | None = None,
    expected_ledger_chain_hash: str | None = None,
    expected_terminal_event_hash: str | None = None,
) -> dict[str, Any]:
    """Validate append-only hash-chain continuity for a ledger."""

    ledger_events = _existing_ledger(ledger)
    if ledger_events is None:
        return _chain_report(accepted=False, status="rejected", rejection_codes=[LEDGER_CHAIN_MALFORMED])

    rejection_codes: list[str] = []
    seen_event_ids: set[str] = set()
    previous_event_hash = GENESIS_PREVIOUS_EVENT_HASH
    for index, event in enumerate(ledger_events):
        event_id = event.get("event_id")
        if isinstance(event_id, str) and event_id in seen_event_ids:
            rejection_codes.append(LEDGER_DUPLICATE_EVENT_ID)
        if isinstance(event_id, str):
            seen_event_ids.add(event_id)

        structure_error = _event_structure_error(event)
        if structure_error:
            rejection_codes.append(structure_error)

        if event.get("previous_event_hash") != previous_event_hash:
            rejection_codes.append(LEDGER_CHAIN_DISCONTINUITY)

        provided_hash = event.get("event_hash")
        if not _is_hash(provided_hash):
            rejection_codes.append(LEDGER_EVENT_HASH_MISMATCH)
        elif canonical_event_hash(event) != provided_hash:
            rejection_codes.append(LEDGER_EVENT_HASH_MISMATCH)

        previous_event_hash = provided_hash if isinstance(provided_hash, str) else f"invalid:{index}"

    ledger_chain_hash = _ledger_chain_hash(ledger_events) if not rejection_codes else None
    terminal_event_hash = ledger_events[-1].get("event_hash") if ledger_events else GENESIS_PREVIOUS_EVENT_HASH
    if expected_event_count is not None and len(ledger_events) != expected_event_count:
        rejection_codes.append(LEDGER_EXPECTED_EVENT_COUNT_MISMATCH)
    if expected_ledger_chain_hash is not None and ledger_chain_hash != expected_ledger_chain_hash:
        rejection_codes.append(LEDGER_EXPECTED_LEDGER_CHAIN_HASH_MISMATCH)
    if expected_terminal_event_hash is not None and terminal_event_hash != expected_terminal_event_hash:
        rejection_codes.append(LEDGER_EXPECTED_TERMINAL_EVENT_HASH_MISMATCH)

    if rejection_codes:
        return _chain_report(accepted=False, status="rejected", rejection_codes=rejection_codes)
    return _chain_report(
        accepted=True,
        status="valid",
        rejection_codes=[],
        ledger_chain_hash=ledger_chain_hash,
    )


def append_event(ledger: Any, event: Any) -> dict[str, Any]:
    """Append one event to a deterministic ledger chain, fail-closed."""

    ledger_events = _existing_ledger(ledger)
    if ledger_events is None or not _is_mapping(event):
        return _reject(LEDGER_EVENT_MALFORMED)

    if ledger_events:
        chain_report = validate_ledger_chain(ledger_events)
        if not chain_report.get("accepted", False):
            return _reject(LEDGER_CHAIN_INVALID)

    event_map = dict(event)
    structure_error = _event_structure_error(event_map)
    if structure_error:
        return _reject(structure_error)

    if any(existing.get("event_id") == event_map["event_id"] for existing in ledger_events):
        return _reject(LEDGER_DUPLICATE_EVENT_ID)

    expected_previous = ledger_events[-1]["event_hash"] if ledger_events else GENESIS_PREVIOUS_EVENT_HASH
    supplied_previous = event_map.get("previous_event_hash")
    if not isinstance(supplied_previous, str) or not supplied_previous:
        return _reject(LEDGER_PREVIOUS_EVENT_HASH_REQUIRED)
    if supplied_previous != expected_previous:
        return _reject(LEDGER_PREVIOUS_EVENT_HASH_MISMATCH)

    event_map["event_hash"] = canonical_event_hash(event_map)
    next_ledger = ledger_events + [event_map]
    chain_hash = _ledger_chain_hash(next_ledger)
    receipt = _append_receipt(event_map, event_index=len(ledger_events), ledger_chain_hash=chain_hash)
    return _base_result(
        accepted=True,
        status="appended",
        rejection_codes=[],
        event=event_map,
        receipt=receipt,
        ledger=next_ledger,
    )
