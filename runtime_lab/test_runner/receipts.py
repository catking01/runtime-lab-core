from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any


MILESTONE = "R127_ALLOWLISTED_TEST_RUNNER_LOCAL_VALIDATION"


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def canonical_hash(value: Any) -> str:
    return sha256_text(stable_json(value))


def _hash_payload(value: Mapping[str, Any], hash_field: str = "receipt_hash") -> dict[str, Any]:
    payload = dict(value)
    payload.pop(hash_field, None)
    return payload


def build_test_run_receipt(
    *,
    command_id: str,
    argv: tuple[str, ...],
    cwd_relative: str,
    workspace_root: str,
    timeout_seconds: int,
    started_at_utc: str,
    ended_at_utc: str,
    elapsed_ms: int,
    exit_code: int | None,
    stdout: bytes,
    stderr: bytes,
    stdout_truncated: bool,
    stderr_truncated: bool,
    result: str,
) -> dict[str, Any]:
    receipt = {
        "schema_version": "1.0",
        "receipt_type": "ALLOWLISTED_TEST_RUNNER_RECEIPT",
        "milestone": MILESTONE,
        "command_id": command_id,
        "argv": list(argv),
        "argv_hash": canonical_hash(list(argv)),
        "cwd_relative": cwd_relative,
        "workspace_root_hash": sha256_text(workspace_root),
        "timeout_seconds": int(timeout_seconds),
        "started_at_utc": started_at_utc,
        "ended_at_utc": ended_at_utc,
        "elapsed_ms": int(elapsed_ms),
        "exit_code": exit_code,
        "stdout_recorded": False,
        "stderr_recorded": False,
        "stdout_hash": sha256_bytes(stdout),
        "stderr_hash": sha256_bytes(stderr),
        "stdout_truncated": bool(stdout_truncated),
        "stderr_truncated": bool(stderr_truncated),
        "shell_used": False,
        "network_allowed": False,
        "llm_invocation_allowed": False,
        "result": result,
        "non_claims": {
            "arbitrary_shell": False,
            "arbitrary_command_execution": False,
            "network_execution": False,
            "llm_invocation": False,
            "agent_loop": False,
            "remote_sealed_pass": False,
        },
        "receipt_hash": "",
    }
    receipt["receipt_hash"] = canonical_hash(_hash_payload(receipt))
    return receipt


def verify_test_run_receipt(receipt: Mapping[str, Any]) -> bool:
    if not isinstance(receipt, Mapping):
        return False
    provided = receipt.get("receipt_hash")
    return isinstance(provided, str) and provided.startswith("sha256:") and canonical_hash(
        _hash_payload(receipt)
    ) == provided
