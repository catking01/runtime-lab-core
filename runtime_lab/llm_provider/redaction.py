"""Redaction helpers for provider receipts and provider errors."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

DEEPSEEK_ERROR_TYPES = {
    400: ("INVALID_FORMAT", False),
    401: ("AUTHENTICATION_FAILED", False),
    402: ("INSUFFICIENT_BALANCE", False),
    422: ("INVALID_PARAMETERS", False),
    429: ("RATE_LIMIT", True),
    500: ("SERVER_ERROR", True),
    503: ("SERVER_OVERLOADED", True),
}


def redact_text(text: str, *, secret: str | None = None) -> str:
    """Remove API-key material and raw Authorization values from text."""

    redacted = text
    redacted = re.sub(r"Authorization:\s*Bearer\s+[^\s\\n]+", "Authorization: Bearer [REDACTED]", redacted)
    redacted = re.sub(r"Bearer\s+[A-Za-z0-9._\-]+", "Bearer [REDACTED]", redacted)
    if secret:
        redacted = redacted.replace(secret, "[REDACTED]")
    return redacted


def redact_headers(headers: Mapping[str, str], *, secret: str | None = None) -> dict[str, str]:
    """Return headers with credential-bearing fields redacted."""

    redacted: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() == "authorization":
            redacted[key] = "[REDACTED]"
        else:
            redacted[key] = redact_text(str(value), secret=secret)
    return redacted


def redact_deepseek_error(*, status_code: int, error_body: Any, secret: str | None = None) -> dict[str, Any]:
    """Map a DeepSeek provider error to a redacted receipt-safe shape."""

    error_type, retryable = DEEPSEEK_ERROR_TYPES.get(status_code, ("UNKNOWN_PROVIDER_ERROR", False))
    if isinstance(error_body, str):
        body_text = error_body
    else:
        body_text = json.dumps(error_body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return {
        "provider_id": "deepseek",
        "status_code": status_code,
        "error_type": error_type,
        "retryable": retryable,
        "redacted_error_body": redact_text(body_text, secret=secret),
    }
