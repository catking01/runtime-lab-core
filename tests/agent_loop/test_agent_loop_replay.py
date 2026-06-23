from __future__ import annotations

from runtime_lab.agent_loop.replay import build_replay_manifest, verify_replay_manifest


def test_replay_manifest_verifies():
    manifest = build_replay_manifest(
        run_id="run-1",
        base_commit="abc123",
        state_transition_hash="sha256:states",
        ledger_tail_hash="sha256:ledger",
        receipt_hashes={"agent": "sha256:agent"},
        artifact_hashes={"final_report": "sha256:report"},
    )

    assert manifest["replay_manifest_hash"].startswith("sha256:")
    assert verify_replay_manifest(manifest) is True


def test_replay_manifest_detects_tamper():
    manifest = build_replay_manifest(
        run_id="run-1",
        base_commit="abc123",
        state_transition_hash="sha256:states",
        ledger_tail_hash="sha256:ledger",
        receipt_hashes={},
        artifact_hashes={},
    )
    manifest["base_commit"] = "changed"

    assert verify_replay_manifest(manifest) is False
