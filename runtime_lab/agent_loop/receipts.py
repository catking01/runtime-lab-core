from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from typing import Any


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def sha256_text(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def canonical_hash(value: Any) -> str:
    return sha256_text(stable_json(value))


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_agent_loop_receipt(
    *,
    task_id: str,
    run_id: str,
    base_commit: str | None = None,
    workspace_root_hash: str | None = None,
    mode: str = "DRY_RUN",
    policy_hash: str,
    authority_decision_hash: str | None = None,
    state_transition_hash_chain: str,
    executor_receipt_hashes: dict[str, str] | list[str] | tuple[str, ...],
    artifact_hashes: dict[str, str],
    final_result: str,
    non_claims: dict[str, bool] | None = None,
    rejection_codes: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    receipt = {
        "schema_version": "1.0",
        "receipt_version": "agent_loop.v0",
        "milestone": "R128_SUPERVISED_LOCAL_AGENT_LOOP_V0_LOCAL_VALIDATION",
        "task_id": task_id,
        "run_id": run_id,
        "base_commit": base_commit,
        "workspace_root_hash": workspace_root_hash,
        "mode": mode,
        "policy_hash": policy_hash,
        "authority_decision_hash": authority_decision_hash,
        "state_transition_hash_chain": state_transition_hash_chain,
        "executor_receipt_hashes": executor_receipt_hashes,
        "artifact_hashes": dict(sorted(artifact_hashes.items())),
        "final_result": final_result,
        "rejection_codes": list(dict.fromkeys(rejection_codes or [])),
        "created_at_utc": _utc_now(),
        "non_claim_boundary": non_claims or {
            "autonomous_operation": False,
            "arbitrary_shell": False,
            "arbitrary_command_execution": False,
            "network_execution": False,
            "live_llm_provider": False,
            "model_driven_executor_dispatch": False,
            "codex_equivalence": False,
            "claude_code_equivalence": False,
            "production_readiness": False,
            "remote_sealed_pass": False,
        },
    }
    receipt["receipt_hash"] = canonical_hash(receipt)
    return receipt


def verify_agent_loop_receipt(receipt: dict[str, Any]) -> bool:
    if not isinstance(receipt, dict) or "receipt_hash" not in receipt:
        return False
    expected = receipt["receipt_hash"]
    candidate = dict(receipt)
    candidate.pop("receipt_hash", None)
    if canonical_hash(candidate) != expected:
        return False
    if receipt.get("receipt_version") != "agent_loop.v0":
        return False
    return True
