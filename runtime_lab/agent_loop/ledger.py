from __future__ import annotations

from typing import Any

from runtime_lab.agent_loop.receipts import canonical_hash


def build_ledger_events(*, run_id: str, receipt_hashes: list[str] | tuple[str, ...]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    previous_hash = "GENESIS"
    for index, receipt_hash in enumerate(receipt_hashes, start=1):
        event = {
            "schema_version": "1.0",
            "ledger_version": "agent_loop_ledger.v0",
            "run_id": run_id,
            "sequence": index,
            "event_type": "agent_loop.receipt_recorded",
            "receipt_hash": receipt_hash,
            "previous_event_hash": previous_hash,
        }
        event["event_hash"] = canonical_hash(event)
        events.append(event)
        previous_hash = event["event_hash"]
    return events


def verify_ledger_events(events: list[dict[str, Any]]) -> bool:
    previous_hash = "GENESIS"
    for event in events:
        expected = dict(event)
        event_hash = expected.pop("event_hash", None)
        if expected.get("previous_event_hash") != previous_hash:
            return False
        if canonical_hash(expected) != event_hash:
            return False
        previous_hash = str(event_hash)
    return True
