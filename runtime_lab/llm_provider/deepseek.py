"""DeepSeek test LLM provider adapter for R123.

The adapter produces receipt-bound model invocation evidence. It does not send
tools, execute tool calls, dispatch executors, or mutate the workspace.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Mapping
from typing import Any

from .errors import ProviderTimeout, ProviderTransportError
from .models import (
    CONTENT_FILTER,
    MALFORMED_RESPONSE,
    NON_JSON_RESPONSE,
    PROVIDER_ERROR,
    TIMEOUT,
    TOOL_CALL_PROPOSAL_REJECTED,
    VALID_JSON_EXACT,
    VALID_JSON_EXTRA_TEXT,
)
from .policy import (
    DEEPSEEK_BASE_URL,
    DEEPSEEK_CHAT_COMPLETIONS_URL,
    DEEPSEEK_DEFAULT_MODEL,
    build_deepseek_request_body,
    validate_deepseek_live_gate,
    validate_deepseek_model,
    validate_extra_request_fields,
)
from .receipts import build_invocation_receipt
from .redaction import redact_deepseek_error
from .transport import ProviderResponse, UrllibDeepSeekTransport

LIVE_SMOKE_PROMPT = 'Return exactly this JSON object and nothing else:\n{"runtime_lab_live_instance":"ok"}'
EXPECTED_LIVE_JSON = {"runtime_lab_live_instance": "ok"}


def _non_execution_flags() -> dict[str, bool]:
    return {
        "tool_calls_sent": False,
        "tool_calls_executed": False,
        "executor_dispatch_started": False,
        "workspace_mutation_started": False,
    }


def _reject(code: str) -> dict[str, Any]:
    result = {
        "accepted": False,
        "status": "rejected",
        "rejection_codes": [code],
        "transport_started": False,
        "api_key_recorded": False,
        "authorization_header_recorded": False,
    }
    result.update(_non_execution_flags())
    return result


def _extract_choice(payload: Any) -> tuple[Mapping[str, Any] | None, Mapping[str, Any] | None]:
    if not isinstance(payload, Mapping):
        return None, None
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], Mapping):
        return None, None
    message = choices[0].get("message")
    if not isinstance(message, Mapping):
        return choices[0], None
    return choices[0], message


def _parse_json_result(text: str) -> tuple[str, dict[str, Any] | None]:
    stripped = text.strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            try:
                parsed = json.loads(stripped[start : end + 1])
            except json.JSONDecodeError:
                return NON_JSON_RESPONSE, None
            if isinstance(parsed, dict):
                return VALID_JSON_EXTRA_TEXT, parsed
        return NON_JSON_RESPONSE, None
    if isinstance(parsed, dict):
        return VALID_JSON_EXACT, parsed
    return NON_JSON_RESPONSE, None


class DeepSeekTestProviderAdapter:
    """R123 DeepSeek adapter with injected transport for deterministic tests."""

    def __init__(
        self,
        *,
        api_key: str,
        transport: Any,
        base_url: str = DEEPSEEK_BASE_URL,
        timeout_seconds: float = 10.0,
    ):
        self.api_key = api_key
        self.transport = transport
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds

    def invoke_json_smoke(self, *, prompt: str, model: str = DEEPSEEK_DEFAULT_MODEL) -> dict[str, Any]:
        """Invoke the provider through the constrained JSON-object smoke path."""

        return self.invoke(
            prompt=prompt,
            model=model,
            response_format={"type": "json_object"},
            max_tokens=64,
        )

    def invoke(
        self,
        *,
        prompt: str,
        model: str = DEEPSEEK_DEFAULT_MODEL,
        response_format: Mapping[str, str] | None = None,
        max_tokens: int = 64,
        extra_request_fields: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Classify one DeepSeek chat-completions response into a sealed receipt."""

        model_result = validate_deepseek_model(model)
        if not model_result["accepted"]:
            return _reject("DEEPSEEK_MODEL_NOT_ALLOWLISTED")
        field_result = validate_extra_request_fields(extra_request_fields)
        if not field_result["accepted"]:
            result = _reject(field_result["rejection_codes"][0])
            result["rejection_codes"] = field_result["rejection_codes"]
            return result
        if not self.api_key:
            return _reject("DEEPSEEK_API_KEY_MISSING")

        body = build_deepseek_request_body(
            model=model,
            prompt=prompt,
            max_tokens=max_tokens,
            response_format=response_format,
        )
        if extra_request_fields:
            body.update(dict(extra_request_fields))
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        start = time.perf_counter()
        try:
            response = self.transport.post_json(
                url=f"{self.base_url}/chat/completions",
                headers=headers,
                json_body=body,
                timeout_seconds=self.timeout_seconds,
            )
        except ProviderTimeout as exc:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            provider_error = redact_deepseek_error(status_code=0, error_body=str(exc), secret=self.api_key)
            provider_error["error_type"] = "TIMEOUT"
            receipt = build_invocation_receipt(
                provider_id="deepseek",
                model=model,
                base_url=self.base_url,
                prompt=prompt,
                request_body=body,
                response_payload={"provider_error": provider_error},
                response_text=None,
                elapsed_ms=elapsed_ms,
                classification=TIMEOUT,
                provider_error=provider_error,
            )
            return self._accepted_result(classification=TIMEOUT, receipt=receipt, json_result=None)
        except ProviderTransportError as exc:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            provider_error = redact_deepseek_error(status_code=0, error_body=str(exc), secret=self.api_key)
            receipt = build_invocation_receipt(
                provider_id="deepseek",
                model=model,
                base_url=self.base_url,
                prompt=prompt,
                request_body=body,
                response_payload={"provider_error": provider_error},
                response_text=None,
                elapsed_ms=elapsed_ms,
                classification=PROVIDER_ERROR,
                provider_error=provider_error,
            )
            return self._accepted_result(classification=PROVIDER_ERROR, receipt=receipt, json_result=None)

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return self._classify_provider_response(
            response=response,
            model=model,
            prompt=prompt,
            request_body=body,
            elapsed_ms=elapsed_ms,
        )

    def _classify_provider_response(
        self,
        *,
        response: ProviderResponse,
        model: str,
        prompt: str,
        request_body: Mapping[str, Any],
        elapsed_ms: int,
    ) -> dict[str, Any]:
        if response.status_code != 200:
            provider_error = redact_deepseek_error(
                status_code=response.status_code,
                error_body=response.payload,
                secret=self.api_key,
            )
            receipt = build_invocation_receipt(
                provider_id="deepseek",
                model=model,
                base_url=self.base_url,
                prompt=prompt,
                request_body=request_body,
                response_payload={"provider_error": provider_error},
                response_text=None,
                elapsed_ms=elapsed_ms,
                classification=PROVIDER_ERROR,
                provider_error=provider_error,
            )
            return self._accepted_result(classification=PROVIDER_ERROR, receipt=receipt, json_result=None)

        choice, message = _extract_choice(response.payload)
        if choice is None or message is None:
            receipt = build_invocation_receipt(
                provider_id="deepseek",
                model=model,
                base_url=self.base_url,
                prompt=prompt,
                request_body=request_body,
                response_payload=response.payload,
                response_text=None,
                elapsed_ms=elapsed_ms,
                classification=MALFORMED_RESPONSE,
                provider_error=None,
            )
            return self._accepted_result(classification=MALFORMED_RESPONSE, receipt=receipt, json_result=None)

        tool_calls = message.get("tool_calls")
        if isinstance(tool_calls, list) and tool_calls:
            receipt = build_invocation_receipt(
                provider_id="deepseek",
                model=model,
                base_url=self.base_url,
                prompt=prompt,
                request_body=request_body,
                response_payload=response.payload,
                response_text=None,
                elapsed_ms=elapsed_ms,
                classification=TOOL_CALL_PROPOSAL_REJECTED,
                provider_error=None,
                tool_calls_present=True,
                tool_call_proposals_rejected=len(tool_calls),
            )
            result = self._accepted_result(
                classification=TOOL_CALL_PROPOSAL_REJECTED,
                receipt=receipt,
                json_result=None,
            )
            result["tool_call_proposals_rejected"] = len(tool_calls)
            return result

        if choice.get("finish_reason") == "content_filter":
            classification = CONTENT_FILTER
            json_result = None
            content = message.get("content") if isinstance(message.get("content"), str) else None
        else:
            content = message.get("content")
            if not isinstance(content, str):
                classification = MALFORMED_RESPONSE
                json_result = None
                content = None
            else:
                classification, json_result = _parse_json_result(content)

        receipt = build_invocation_receipt(
            provider_id="deepseek",
            model=model,
            base_url=self.base_url,
            prompt=prompt,
            request_body=request_body,
            response_payload=response.payload,
            response_text=content,
            elapsed_ms=elapsed_ms,
            classification=classification,
            provider_error=None,
        )
        return self._accepted_result(classification=classification, receipt=receipt, json_result=json_result)

    @staticmethod
    def _accepted_result(*, classification: str, receipt: Mapping[str, Any], json_result: Any) -> dict[str, Any]:
        result = {
            "accepted": True,
            "status": "provider_response_classified",
            "classification": classification,
            "json_result": json_result,
            "receipt": dict(receipt),
            "transport_started": True,
            "rejection_codes": [],
        }
        result.update(_non_execution_flags())
        return result


def run_live_deepseek_smoke_from_env(*, prompt: str = LIVE_SMOKE_PROMPT) -> dict[str, Any]:
    """Run the R123 live smoke only when all explicit environment gates pass."""

    gate = validate_deepseek_live_gate()
    if not gate["accepted"]:
        result = _reject("DEEPSEEK_LIVE_GATE_DISABLED")
        result["rejection_codes"] = gate["rejection_codes"]
        return result
    adapter = DeepSeekTestProviderAdapter(
        api_key=os.environ["DEEPSEEK_API_KEY"],
        transport=UrllibDeepSeekTransport(),
    )
    return adapter.invoke_json_smoke(prompt=prompt, model=os.environ["DEEPSEEK_MODEL"])
