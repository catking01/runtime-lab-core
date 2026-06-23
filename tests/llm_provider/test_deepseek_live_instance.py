from __future__ import annotations

import os

import pytest

from runtime_lab.llm_provider.deepseek import LIVE_SMOKE_PROMPT, run_live_deepseek_smoke_from_env
from runtime_lab.llm_provider.policy import validate_deepseek_live_gate


@pytest.mark.live_deepseek
def test_live_deepseek_smoke_is_gated_and_receipt_bound():
    gate = validate_deepseek_live_gate()
    if not gate["accepted"]:
        pytest.skip(f"DeepSeek live gate disabled: {gate['rejection_codes']}")

    result = run_live_deepseek_smoke_from_env(prompt=LIVE_SMOKE_PROMPT)

    assert result["accepted"] is True
    assert result["classification"] in {
        "VALID_JSON_EXACT",
        "VALID_JSON_EXTRA_TEXT",
        "NON_JSON_RESPONSE",
        "PROVIDER_ERROR",
        "TIMEOUT",
        "CONTENT_FILTER",
        "MALFORMED_RESPONSE",
        "TOOL_CALL_PROPOSAL_REJECTED",
    }
    assert result["receipt"]["provider_id"] == "deepseek"
    assert result["receipt"]["model"] == os.environ["DEEPSEEK_MODEL"]
    assert result["receipt"]["base_url"] == "https://api.deepseek.com"
    assert result["receipt"]["api_key_recorded"] is False
    assert result["receipt"]["authorization_header_recorded"] is False
    assert result["receipt"]["raw_response_text_recorded"] is False
    assert result["receipt"]["request_hash"].startswith("sha256:")
    assert result["receipt"]["prompt_hash"].startswith("sha256:")
    assert result["receipt"]["response_hash"].startswith("sha256:")
    assert result["receipt"]["elapsed_ms"] >= 0
    assert result["receipt"]["tool_calls_sent"] is False
    assert result["receipt"]["tool_calls_executed"] is False
    assert result["receipt"]["executor_dispatch_started"] is False
    assert result["receipt"]["workspace_mutation_started"] is False
    assert os.environ["DEEPSEEK_API_KEY"] not in repr(result)
