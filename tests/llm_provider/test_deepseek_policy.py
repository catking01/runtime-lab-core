from __future__ import annotations

from runtime_lab.llm_provider.policy import (
    DEEPSEEK_BASE_URL,
    DEEPSEEK_PROVIDER_ID,
    LIVE_INSTANCE_REQUIRED_GATES,
    build_deepseek_request_body,
    deepseek_policy,
    validate_deepseek_live_gate,
    validate_deepseek_model,
)


def test_deepseek_policy_classifies_provider_without_executor_capability():
    policy = deepseek_policy()

    assert policy["provider_id"] == DEEPSEEK_PROVIDER_ID
    assert policy["base_url"] == DEEPSEEK_BASE_URL
    assert policy["supported_provider_roles"] == [
        "TEST_LLM_PROVIDER",
        "LLM_PROVIDER_ADAPTER_CANDIDATE",
        "RECEIPT_BOUND_MODEL_INVOCATION_PROVIDER",
    ]
    assert policy["executor"] is False
    assert policy["tool_runtime"] is False
    assert policy["agent_loop"] is False
    assert policy["workspace_mutator"] is False
    assert policy["network_allowed_by_default"] is False
    assert policy["live_instance_tests_enabled_by_default"] is False
    assert policy["tool_calls_sent"] is False
    assert policy["tool_calls_executed"] is False
    assert policy["executor_dispatch_started"] is False
    assert policy["workspace_mutation_started"] is False


def test_model_allowlist_rejects_legacy_compatibility_names():
    assert validate_deepseek_model("deepseek-v4-flash")["accepted"] is True
    assert validate_deepseek_model("deepseek-v4-pro")["accepted"] is True

    rejected_chat = validate_deepseek_model("deepseek-chat")
    rejected_reasoner = validate_deepseek_model("deepseek-reasoner")

    assert rejected_chat["accepted"] is False
    assert "DEEPSEEK_MODEL_NOT_ALLOWLISTED" in rejected_chat["rejection_codes"]
    assert rejected_reasoner["accepted"] is False
    assert "DEEPSEEK_MODEL_NOT_ALLOWLISTED" in rejected_reasoner["rejection_codes"]


def test_live_gate_requires_all_explicit_environment_flags(monkeypatch):
    for name in LIVE_INSTANCE_REQUIRED_GATES + ("DEEPSEEK_API_KEY", "DEEPSEEK_MODEL"):
        monkeypatch.delenv(name, raising=False)

    result = validate_deepseek_live_gate()

    assert result["accepted"] is False
    assert result["network_allowed"] is False
    assert result["live_instance_tests_enabled"] is False
    assert result["api_key_source"] == "ENV:DEEPSEEK_API_KEY"
    assert result["api_key_recorded"] is False
    assert "DEEPSEEK_LIVE_GATE_DISABLED" in result["rejection_codes"]
    assert "DEEPSEEK_API_KEY_MISSING" in result["rejection_codes"]


def test_live_gate_accepts_only_with_all_flags_key_and_allowlisted_model(monkeypatch):
    monkeypatch.setenv("RUNTIME_LAB_ALLOW_LLM_PROVIDER", "1")
    monkeypatch.setenv("RUNTIME_LAB_ALLOW_NETWORK", "1")
    monkeypatch.setenv("RUNTIME_LAB_ALLOW_LIVE_INSTANCE_TESTS", "1")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-test-secret")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-v4-flash")

    result = validate_deepseek_live_gate()

    assert result["accepted"] is True
    assert result["provider_id"] == "deepseek"
    assert result["model"] == "deepseek-v4-flash"
    assert result["base_url"] == "https://api.deepseek.com"
    assert result["api_key_source"] == "ENV:DEEPSEEK_API_KEY"
    assert result["api_key_recorded"] is False
    assert result["authorization_header_recorded"] is False


def test_request_body_omits_tools_and_forces_small_json_smoke_shape():
    body = build_deepseek_request_body(
        model="deepseek-v4-flash",
        prompt='Return exactly this JSON object and nothing else:\n{"runtime_lab_live_instance":"ok"}',
        max_tokens=64,
        response_format={"type": "json_object"},
    )

    assert body["model"] == "deepseek-v4-flash"
    assert body["stream"] is False
    assert body["max_tokens"] == 64
    assert body["response_format"] == {"type": "json_object"}
    assert "tools" not in body
    assert "tool_choice" not in body
    assert body["messages"] == [
        {
            "role": "user",
            "content": 'Return exactly this JSON object and nothing else:\n{"runtime_lab_live_instance":"ok"}',
        }
    ]
