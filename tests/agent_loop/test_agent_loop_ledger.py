from __future__ import annotations

from runtime_lab.agent_loop.ledger import build_ledger_events, verify_ledger_events


def test_ledger_hash_chain_is_stable():
    events = build_ledger_events(
        run_id="run-1",
        receipt_hashes=["sha256:authority", "sha256:proposal", "sha256:tests"],
    )

    assert verify_ledger_events(events) is True
    assert events[0]["previous_event_hash"] == "GENESIS"
    assert events[-1]["event_hash"].startswith("sha256:")


def test_ledger_hash_mismatch_fails_verification():
    events = build_ledger_events(run_id="run-1", receipt_hashes=["sha256:authority"])
    events[0]["receipt_hash"] = "sha256:changed"

    assert verify_ledger_events(events) is False
