"""Hash-bound LLM provider invocation receipts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any


def stable_json(value: Any) -> str:
    """Serialize data deterministically for R123 hashes."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_hash(value: Any) -> str:
    return sha256_text(stable_json(value))


def _receipt_hash_payload(receipt: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(receipt)
    payload.pop("receipt_hash", None)
    return payload


def build_invocation_receipt(
    *,
    provider_id: str,
    model: str,
    base_url: str,
    prompt: str,
    request_body: Mapping[str, Any],
    response_payload: Any,
    response_text: str | None,
    elapsed_ms: int,
    classification: str,
    provider_error: Mapping[str, Any] | None,
    tool_calls_present: bool = False,
    tool_call_proposals_rejected: int = 0,
) -> dict[str, Any]:
    """Build a deterministic receipt without raw prompt, raw response, or secrets."""

    receipt = {
        "schema_version": "llm_provider_invocation_receipt.v1",
        "provider_id": provider_id,
        "model": model,
        "base_url": base_url,
        "api_compatibility_mode": "openai_chat_completions",
        "request_hash": canonical_hash(dict(request_body)),
        "prompt_hash": sha256_text(prompt),
        "response_hash": canonical_hash(response_payload if response_text is None else {"text": response_text}),
        "elapsed_ms": elapsed_ms,
        "classification": classification,
        "usage": response_payload.get("usage", {}) if isinstance(response_payload, Mapping) else {},
        "provider_error": dict(provider_error) if provider_error is not None else None,
        "raw_prompt_recorded": False,
        "raw_response_text_recorded": False,
        "api_key_recorded": False,
        "authorization_header_recorded": False,
        "tool_calls_sent": False,
        "tool_calls_present": bool(tool_calls_present),
        "tool_call_proposals_rejected": int(tool_call_proposals_rejected),
        "tool_calls_executed": False,
        "executor_dispatch_started": False,
        "workspace_mutation_started": False,
        "receipt_hash": "",
    }
    receipt["receipt_hash"] = canonical_hash(_receipt_hash_payload(receipt))
    return receipt


def verify_invocation_receipt(receipt: Mapping[str, Any]) -> bool:
    """Verify an R123 provider invocation receipt hash."""

    if not isinstance(receipt, Mapping):
        return False
    provided = receipt.get("receipt_hash")
    return isinstance(provided, str) and provided.startswith("sha256:") and canonical_hash(
        _receipt_hash_payload(receipt)
    ) == provided
