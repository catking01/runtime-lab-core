"""DeepSeek test-provider policy for R123."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from .models import NON_EXECUTION_FLAGS, PROVIDER_ROLES

DEEPSEEK_PROVIDER_ID = "deepseek"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_CHAT_COMPLETIONS_PATH = "/chat/completions"
DEEPSEEK_CHAT_COMPLETIONS_URL = f"{DEEPSEEK_BASE_URL}{DEEPSEEK_CHAT_COMPLETIONS_PATH}"
DEEPSEEK_ALLOWLISTED_MODELS = ("deepseek-v4-flash", "deepseek-v4-pro")
DEEPSEEK_DEFAULT_MODEL = "deepseek-v4-flash"
LIVE_INSTANCE_REQUIRED_GATES = (
    "RUNTIME_LAB_ALLOW_LLM_PROVIDER",
    "RUNTIME_LAB_ALLOW_NETWORK",
    "RUNTIME_LAB_ALLOW_LIVE_INSTANCE_TESTS",
)
FORBIDDEN_EXTRA_REQUEST_FIELDS = {
    "tools": "DEEPSEEK_TOOL_CALLS_FORBIDDEN",
    "tool_choice": "DEEPSEEK_TOOL_CALLS_FORBIDDEN",
    "tool_call": "DEEPSEEK_TOOL_CALLS_FORBIDDEN",
    "executor_dispatch": "DEEPSEEK_EXECUTOR_DISPATCH_FORBIDDEN",
    "workspace_mutation": "DEEPSEEK_WORKSPACE_MUTATION_FORBIDDEN",
    "shell_command": "DEEPSEEK_EXECUTOR_DISPATCH_FORBIDDEN",
    "subprocess": "DEEPSEEK_EXECUTOR_DISPATCH_FORBIDDEN",
}


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def deepseek_policy() -> dict[str, Any]:
    """Return the R123 static DeepSeek provider boundary."""

    policy = {
        "provider_id": DEEPSEEK_PROVIDER_ID,
        "base_url": DEEPSEEK_BASE_URL,
        "api_compatibility_mode": "openai_chat_completions",
        "allowlisted_models": list(DEEPSEEK_ALLOWLISTED_MODELS),
        "legacy_compatibility_names_rejected": ["deepseek-chat", "deepseek-reasoner"],
        "supported_provider_roles": list(PROVIDER_ROLES),
        "executor": False,
        "tool_runtime": False,
        "agent_loop": False,
        "coding_agent": False,
        "workspace_mutator": False,
        "network_allowed_by_default": False,
        "live_instance_tests_enabled_by_default": False,
        "api_key_source": "ENV:DEEPSEEK_API_KEY",
        "api_key_recorded": False,
        "authorization_header_recorded": False,
    }
    policy.update(NON_EXECUTION_FLAGS)
    return policy


def validate_deepseek_model(model: str | None) -> dict[str, Any]:
    """Validate an R123 allowlisted DeepSeek model id."""

    if model in DEEPSEEK_ALLOWLISTED_MODELS:
        return {"accepted": True, "model": model, "rejection_codes": []}
    return {"accepted": False, "model": model, "rejection_codes": ["DEEPSEEK_MODEL_NOT_ALLOWLISTED"]}


def validate_extra_request_fields(extra_request_fields: Mapping[str, Any] | None) -> dict[str, Any]:
    """Reject request fields that would turn provider output into execution."""

    if not extra_request_fields:
        return {"accepted": True, "rejection_codes": []}
    rejection_codes = [
        code for field, code in FORBIDDEN_EXTRA_REQUEST_FIELDS.items() if field in extra_request_fields
    ]
    if rejection_codes:
        return {"accepted": False, "rejection_codes": _dedupe(rejection_codes)}
    return {"accepted": True, "rejection_codes": []}


def validate_deepseek_live_gate(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Validate the explicit environment gate required before live provider use."""

    env_map = os.environ if env is None else env
    gate_values = {name: env_map.get(name) == "1" for name in LIVE_INSTANCE_REQUIRED_GATES}
    model = env_map.get("DEEPSEEK_MODEL")
    key_present = bool(env_map.get("DEEPSEEK_API_KEY"))
    rejection_codes: list[str] = []
    if not all(gate_values.values()):
        rejection_codes.append("DEEPSEEK_LIVE_GATE_DISABLED")
    if not key_present:
        rejection_codes.append("DEEPSEEK_API_KEY_MISSING")
    if model is None:
        rejection_codes.append("DEEPSEEK_MODEL_MISSING")
    else:
        model_result = validate_deepseek_model(model)
        rejection_codes.extend(model_result["rejection_codes"])

    return {
        "accepted": not rejection_codes,
        "provider_id": DEEPSEEK_PROVIDER_ID,
        "model": model,
        "base_url": DEEPSEEK_BASE_URL,
        "network_allowed": gate_values["RUNTIME_LAB_ALLOW_NETWORK"],
        "live_instance_tests_enabled": gate_values["RUNTIME_LAB_ALLOW_LIVE_INSTANCE_TESTS"],
        "network_gate": gate_values,
        "api_key_source": "ENV:DEEPSEEK_API_KEY",
        "api_key_recorded": False,
        "authorization_header_recorded": False,
        "rejection_codes": _dedupe(rejection_codes),
    }


def build_deepseek_request_body(
    *,
    model: str,
    prompt: str,
    max_tokens: int = 64,
    response_format: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Build the minimal R123 DeepSeek chat request body without tools."""

    model_result = validate_deepseek_model(model)
    if not model_result["accepted"]:
        raise ValueError("DEEPSEEK_MODEL_NOT_ALLOWLISTED")
    body: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "max_tokens": max_tokens,
    }
    if response_format is not None:
        body["response_format"] = dict(response_format)
    return body
