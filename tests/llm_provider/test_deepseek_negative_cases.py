from __future__ import annotations

from runtime_lab.llm_provider.deepseek import DeepSeekTestProviderAdapter
from runtime_lab.llm_provider.transport import FakeDeepSeekTransport, ProviderResponse


def test_adapter_rejects_request_that_attempts_to_send_tools():
    adapter = DeepSeekTestProviderAdapter(
        api_key="ds-secret-value",
        transport=FakeDeepSeekTransport(ProviderResponse(status_code=200, payload={})),
    )

    result = adapter.invoke(
        prompt="hello",
        model="deepseek-v4-flash",
        extra_request_fields={"tools": [{"type": "function"}]},
    )

    assert result["accepted"] is False
    assert "DEEPSEEK_TOOL_CALLS_FORBIDDEN" in result["rejection_codes"]
    assert result["transport_started"] is False
    assert result["tool_calls_sent"] is False
    assert result["tool_calls_executed"] is False
    assert result["executor_dispatch_started"] is False
    assert result["workspace_mutation_started"] is False


def test_adapter_rejects_model_driven_executor_dispatch_fields_before_transport():
    adapter = DeepSeekTestProviderAdapter(
        api_key="ds-secret-value",
        transport=FakeDeepSeekTransport(ProviderResponse(status_code=200, payload={})),
    )

    result = adapter.invoke(
        prompt="hello",
        model="deepseek-v4-flash",
        extra_request_fields={"executor_dispatch": {"action": "run_shell"}},
    )

    assert result["accepted"] is False
    assert "DEEPSEEK_EXECUTOR_DISPATCH_FORBIDDEN" in result["rejection_codes"]
    assert result["transport_started"] is False
    assert result["executor_dispatch_started"] is False
    assert result["workspace_mutation_started"] is False


def test_adapter_rejects_unallowlisted_model_before_transport():
    adapter = DeepSeekTestProviderAdapter(
        api_key="ds-secret-value",
        transport=FakeDeepSeekTransport(ProviderResponse(status_code=200, payload={})),
    )

    result = adapter.invoke(prompt="hello", model="deepseek-chat")

    assert result["accepted"] is False
    assert "DEEPSEEK_MODEL_NOT_ALLOWLISTED" in result["rejection_codes"]
    assert result["transport_started"] is False


def test_adapter_rejects_missing_api_key_without_serializing_secret_fields():
    adapter = DeepSeekTestProviderAdapter(api_key="", transport=FakeDeepSeekTransport(ProviderResponse(status_code=200, payload={})))

    result = adapter.invoke(prompt="hello", model="deepseek-v4-flash")

    assert result["accepted"] is False
    assert "DEEPSEEK_API_KEY_MISSING" in result["rejection_codes"]
    assert result["api_key_recorded"] is False
    assert result["authorization_header_recorded"] is False
    assert result["transport_started"] is False
