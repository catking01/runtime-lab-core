from __future__ import annotations

import json

from runtime_lab.llm_provider.deepseek import DeepSeekTestProviderAdapter
from runtime_lab.llm_provider.errors import ProviderTimeout
from runtime_lab.llm_provider.transport import FakeDeepSeekTransport, ProviderResponse


PROMPT = 'Return exactly this JSON object and nothing else:\n{"runtime_lab_live_instance":"ok"}'


def test_fake_success_response_generates_redacted_receipt_and_sends_no_tools():
    transport = FakeDeepSeekTransport(
        ProviderResponse(
            status_code=200,
            payload={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": '{"runtime_lab_live_instance":"ok"}'},
                    }
                ],
                "usage": {"prompt_tokens": 9, "completion_tokens": 6, "total_tokens": 15},
            },
        )
    )
    adapter = DeepSeekTestProviderAdapter(api_key="ds-secret-value", transport=transport)

    result = adapter.invoke_json_smoke(prompt=PROMPT, model="deepseek-v4-flash")

    assert result["accepted"] is True
    assert result["classification"] == "VALID_JSON_EXACT"
    assert result["json_result"] == {"runtime_lab_live_instance": "ok"}
    assert result["receipt"]["provider_id"] == "deepseek"
    assert result["receipt"]["model"] == "deepseek-v4-flash"
    assert result["receipt"]["api_key_recorded"] is False
    assert result["receipt"]["authorization_header_recorded"] is False
    assert result["receipt"]["tool_calls_sent"] is False
    assert result["receipt"]["tool_calls_executed"] is False
    assert result["receipt"]["executor_dispatch_started"] is False
    assert result["receipt"]["workspace_mutation_started"] is False
    assert "ds-secret-value" not in repr(result)
    assert transport.calls[0]["url"] == "https://api.deepseek.com/chat/completions"
    assert transport.calls[0]["headers"]["Authorization"] == "Bearer ds-secret-value"
    assert "tools" not in transport.calls[0]["json"]
    assert "tool_choice" not in transport.calls[0]["json"]


def test_response_with_extra_text_is_classified_without_adapter_failure():
    transport = FakeDeepSeekTransport(
        ProviderResponse(
            status_code=200,
            payload={
                "choices": [{"finish_reason": "stop", "message": {"content": 'Here: {"runtime_lab_live_instance":"ok"}'}}],
                "usage": {},
            },
        )
    )
    adapter = DeepSeekTestProviderAdapter(api_key="ds-secret-value", transport=transport)

    result = adapter.invoke_json_smoke(prompt=PROMPT)

    assert result["accepted"] is True
    assert result["classification"] == "VALID_JSON_EXTRA_TEXT"
    assert result["json_result"] == {"runtime_lab_live_instance": "ok"}
    assert result["receipt"]["classification"] == "VALID_JSON_EXTRA_TEXT"


def test_response_with_tool_calls_is_recorded_as_rejected_proposal_not_execution():
    transport = FakeDeepSeekTransport(
        ProviderResponse(
            status_code=200,
            payload={
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {"name": "run_shell", "arguments": '{"cmd":"date"}'},
                                }
                            ],
                        },
                    }
                ],
                "usage": {"total_tokens": 7},
            },
        )
    )
    adapter = DeepSeekTestProviderAdapter(api_key="ds-secret-value", transport=transport)

    result = adapter.invoke_json_smoke(prompt=PROMPT)

    assert result["accepted"] is True
    assert result["classification"] == "TOOL_CALL_PROPOSAL_REJECTED"
    assert result["tool_call_proposals_rejected"] == 1
    assert result["receipt"]["tool_calls_sent"] is False
    assert result["receipt"]["tool_calls_present"] is True
    assert result["receipt"]["tool_calls_executed"] is False
    assert result["receipt"]["executor_dispatch_started"] is False
    assert result["receipt"]["workspace_mutation_started"] is False


def test_provider_errors_map_to_redacted_error_receipts():
    for status_code, expected_type in {
        400: "INVALID_FORMAT",
        401: "AUTHENTICATION_FAILED",
        402: "INSUFFICIENT_BALANCE",
        422: "INVALID_PARAMETERS",
        429: "RATE_LIMIT",
        500: "SERVER_ERROR",
        503: "SERVER_OVERLOADED",
    }.items():
        transport = FakeDeepSeekTransport(
            ProviderResponse(status_code=status_code, payload={"error": {"message": "bad ds-secret-value"}})
        )
        adapter = DeepSeekTestProviderAdapter(api_key="ds-secret-value", transport=transport)

        result = adapter.invoke_json_smoke(prompt=PROMPT)

        assert result["accepted"] is True
        assert result["classification"] == "PROVIDER_ERROR"
        assert result["receipt"]["provider_error"]["status_code"] == status_code
        assert result["receipt"]["provider_error"]["error_type"] == expected_type
        assert "ds-secret-value" not in repr(result)


def test_malformed_and_empty_responses_are_classified_with_receipts():
    for payload in ({}, {"choices": []}, {"choices": [{"message": {}}]}):
        transport = FakeDeepSeekTransport(ProviderResponse(status_code=200, payload=payload))
        adapter = DeepSeekTestProviderAdapter(api_key="ds-secret-value", transport=transport)

        result = adapter.invoke_json_smoke(prompt=PROMPT)

        assert result["accepted"] is True
        assert result["classification"] == "MALFORMED_RESPONSE"
        assert result["receipt"]["classification"] == "MALFORMED_RESPONSE"
        assert "receipt_hash" in result["receipt"]


def test_timeout_is_classified_with_redacted_receipt():
    transport = FakeDeepSeekTransport(ProviderTimeout("timeout with ds-secret-value"))
    adapter = DeepSeekTestProviderAdapter(api_key="ds-secret-value", transport=transport)

    result = adapter.invoke_json_smoke(prompt=PROMPT)

    assert result["accepted"] is True
    assert result["classification"] == "TIMEOUT"
    assert result["receipt"]["provider_error"]["error_type"] == "TIMEOUT"
    assert "ds-secret-value" not in repr(result)


def test_non_json_response_has_response_hash_but_no_raw_response_recording():
    transport = FakeDeepSeekTransport(
        ProviderResponse(status_code=200, payload={"choices": [{"finish_reason": "stop", "message": {"content": "not json"}}]})
    )
    adapter = DeepSeekTestProviderAdapter(api_key="ds-secret-value", transport=transport)

    result = adapter.invoke_json_smoke(prompt=PROMPT)

    assert result["classification"] == "NON_JSON_RESPONSE"
    assert result["receipt"]["response_hash"].startswith("sha256:")
    assert result["receipt"]["raw_response_text_recorded"] is False
    assert "not json" not in json.dumps(result["receipt"])
