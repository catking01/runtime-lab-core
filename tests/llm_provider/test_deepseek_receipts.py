from __future__ import annotations

import copy

from runtime_lab.llm_provider.receipts import build_invocation_receipt, verify_invocation_receipt


def _receipt(response_text: str = '{"runtime_lab_live_instance":"ok"}') -> dict:
    return build_invocation_receipt(
        provider_id="deepseek",
        model="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
        prompt='Return exactly this JSON object and nothing else:\n{"runtime_lab_live_instance":"ok"}',
        request_body={
            "model": "deepseek-v4-flash",
            "messages": [
                {
                    "role": "user",
                    "content": 'Return exactly this JSON object and nothing else:\n{"runtime_lab_live_instance":"ok"}',
                }
            ],
            "stream": False,
        },
        response_payload={
            "choices": [{"message": {"content": response_text}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 8, "completion_tokens": 6, "total_tokens": 14},
        },
        response_text=response_text,
        elapsed_ms=123,
        classification="VALID_JSON_EXACT",
        provider_error=None,
    )


def test_receipt_is_hash_bound_and_omits_raw_prompt_response_and_secret_fields():
    receipt = _receipt()

    assert receipt["schema_version"] == "llm_provider_invocation_receipt.v1"
    assert receipt["provider_id"] == "deepseek"
    assert receipt["model"] == "deepseek-v4-flash"
    assert receipt["base_url"] == "https://api.deepseek.com"
    assert receipt["request_hash"].startswith("sha256:")
    assert receipt["prompt_hash"].startswith("sha256:")
    assert receipt["response_hash"].startswith("sha256:")
    assert receipt["receipt_hash"].startswith("sha256:")
    assert receipt["raw_prompt_recorded"] is False
    assert receipt["raw_response_text_recorded"] is False
    assert receipt["api_key_recorded"] is False
    assert receipt["authorization_header_recorded"] is False
    assert receipt["tool_calls_sent"] is False
    assert receipt["tool_calls_executed"] is False
    assert receipt["executor_dispatch_started"] is False
    assert receipt["workspace_mutation_started"] is False
    assert "runtime_lab_live_instance" not in repr(receipt)
    assert verify_invocation_receipt(receipt) is True


def test_receipt_hash_changes_when_response_hash_changes():
    first = _receipt()
    second = _receipt('{"runtime_lab_live_instance":"changed"}')

    assert first["response_hash"] != second["response_hash"]
    assert first["receipt_hash"] != second["receipt_hash"]
    assert verify_invocation_receipt(first) is True
    assert verify_invocation_receipt(second) is True


def test_receipt_verification_fails_after_tamper():
    receipt = _receipt()
    tampered = copy.deepcopy(receipt)
    tampered["classification"] = "NON_JSON_RESPONSE"

    assert verify_invocation_receipt(receipt) is True
    assert verify_invocation_receipt(tampered) is False
