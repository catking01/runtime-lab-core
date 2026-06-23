from __future__ import annotations

from typing import Any

from runtime_lab.agent_loop.receipts import canonical_hash


def build_replay_manifest(
    *,
    run_id: str,
    base_commit: str,
    inputs: dict[str, Any] | None = None,
    state_transition_hash: str | None = None,
    ledger_tail_hash: str | None = None,
    artifact_hashes: dict[str, str],
    receipt_hashes: dict[str, str] | list[str] | tuple[str, ...],
    ledger_hash: str | None = None,
) -> dict[str, Any]:
    manifest = {
        "schema_version": "1.0",
        "replay_version": "agent_loop_replay.v0",
        "milestone": "R128_SUPERVISED_LOCAL_AGENT_LOOP_V0_LOCAL_VALIDATION",
        "run_id": run_id,
        "base_commit": base_commit,
        "inputs": inputs or {},
        "state_transition_hash": state_transition_hash,
        "artifact_hashes": dict(sorted(artifact_hashes.items())),
        "receipt_hashes": receipt_hashes,
        "ledger_tail_hash": ledger_tail_hash or ledger_hash,
        "replay_scope": "local_deterministic_artifact_replay",
        "non_claim_boundary": {
            "remote_replay": False,
            "remote_sealed_pass": False,
            "scientific_reproducibility": False,
            "production_readiness": False,
        },
    }
    manifest["replay_manifest_hash"] = canonical_hash(manifest)
    return manifest


def verify_replay_manifest(manifest: dict[str, Any]) -> bool:
    if not isinstance(manifest, dict) or "replay_hash" not in manifest:
        if "replay_manifest_hash" not in manifest:
            return False
    expected = manifest.get("replay_manifest_hash") or manifest.get("replay_hash")
    candidate = dict(manifest)
    candidate.pop("replay_hash", None)
    candidate.pop("replay_manifest_hash", None)
    if canonical_hash(candidate) != expected:
        return False
    return True
