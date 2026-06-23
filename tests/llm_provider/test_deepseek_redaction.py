from __future__ import annotations

from runtime_lab.llm_provider.redaction import redact_deepseek_error, redact_headers, redact_text


def test_redact_text_removes_secret_literal_and_authorization_header():
    secret = "ds-secret-value"
    raw = f"Authorization: Bearer {secret}\nbody includes {secret}"

    redacted = redact_text(raw, secret=secret)

    assert secret not in redacted
    assert "Bearer ds-secret-value" not in redacted
    assert "Authorization: Bearer [REDACTED]" in redacted


def test_redact_headers_never_records_authorization_value():
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer ds-secret-value",
        "X-Trace": "trace-1",
    }

    redacted = redact_headers(headers, secret="ds-secret-value")

    assert redacted["Content-Type"] == "application/json"
    assert redacted["Authorization"] == "[REDACTED]"
    assert redacted["X-Trace"] == "trace-1"
    assert "ds-secret-value" not in repr(redacted)


def test_provider_error_redaction_preserves_status_without_secret():
    error = redact_deepseek_error(
        status_code=401,
        error_body='{"error":{"message":"bad key ds-secret-value"}}',
        secret="ds-secret-value",
    )

    assert error["provider_id"] == "deepseek"
    assert error["status_code"] == 401
    assert error["error_type"] == "AUTHENTICATION_FAILED"
    assert error["retryable"] is False
    assert "ds-secret-value" not in repr(error)
    assert "[REDACTED]" in error["redacted_error_body"]
