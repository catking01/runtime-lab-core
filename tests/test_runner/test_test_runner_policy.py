from __future__ import annotations

from pathlib import Path

import pytest

from runtime_lab.test_runner.allowlist import DEFAULT_ALLOWLIST
from runtime_lab.test_runner.models import TestRunRequest, TestRunnerPolicy
from runtime_lab.test_runner.policy import validate_test_run_request


def _request(tmp_path: Path, **overrides):
    values = {
        "command_id": "test_runner",
        "workspace_root": tmp_path,
        "cwd_relative": ".",
        "timeout_seconds": 30,
        "max_stdout_bytes": 1024,
        "max_stderr_bytes": 1024,
        "max_total_output_bytes": 2048,
    }
    values.update(overrides)
    return TestRunRequest(**values)


def test_policy_accepts_complete_allowlisted_request(tmp_path: Path):
    result = validate_test_run_request(_request(tmp_path), allowlist=DEFAULT_ALLOWLIST, policy=TestRunnerPolicy())

    assert result["accepted"] is True
    assert result["rejection_codes"] == []
    assert result["shell_execution_started"] is False
    assert result["network_execution_started"] is False
    assert result["llm_invocation_started"] is False


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"raw_command": "pytest tests/test_runner"}, "RAW_COMMAND_REJECTED"),
        ({"argv": ("python", "-m", "pytest", "tests/test_runner")}, "ARGV_OVERRIDE_REJECTED"),
        ({"shell": True}, "SHELL_TRUE_REJECTED"),
        ({"cwd_relative": "../outside"}, "CWD_PATH_TRAVERSAL_REJECTED"),
        ({"timeout_seconds": None}, "TIMEOUT_REQUIRED"),
        ({"timeout_seconds": 0}, "TIMEOUT_REQUIRED"),
        ({"timeout_seconds": 9999}, "TIMEOUT_LIMIT_EXCEEDED"),
        ({"max_stdout_bytes": None}, "STDOUT_LIMIT_REQUIRED"),
        ({"max_stderr_bytes": None}, "STDERR_LIMIT_REQUIRED"),
        ({"max_total_output_bytes": None}, "TOTAL_OUTPUT_LIMIT_REQUIRED"),
        ({"max_total_output_bytes": 1}, "TOTAL_OUTPUT_LIMIT_TOO_SMALL"),
        ({"network_allowed": True}, "NETWORK_EXECUTION_REQUEST_REJECTED"),
        ({"llm_invocation_requested": True}, "LLM_INVOCATION_REQUEST_REJECTED"),
        ({"model_driven_executor_dispatch_requested": True}, "MODEL_DRIVEN_EXECUTOR_DISPATCH_REJECTED"),
        ({"allow_live_deepseek": True}, "LIVE_DEEPSEEK_REJECTED"),
    ],
)
def test_policy_rejects_request_boundary_violations(tmp_path: Path, overrides: dict, code: str):
    result = validate_test_run_request(_request(tmp_path, **overrides), allowlist=DEFAULT_ALLOWLIST)

    assert result["accepted"] is False
    assert code in result["rejection_codes"]
    assert result["shell_execution_started"] is False
    assert result["network_execution_started"] is False
    assert result["llm_invocation_started"] is False


@pytest.mark.parametrize(
    ("policy", "code"),
    [
        (TestRunnerPolicy(receipt_required=False), "RECEIPT_CONTRACT_REQUIRED"),
        (TestRunnerPolicy(ledger_event_required=False), "LEDGER_EVENT_REQUIRED"),
        (TestRunnerPolicy(shell_allowed=True), "SHELL_POLICY_REJECTED"),
        (TestRunnerPolicy(network_allowed=True), "NETWORK_POLICY_REJECTED"),
        (TestRunnerPolicy(llm_invocation_allowed=True), "LLM_POLICY_REJECTED"),
        (TestRunnerPolicy(allow_live_deepseek=True), "LIVE_DEEPSEEK_POLICY_REJECTED"),
    ],
)
def test_policy_rejects_unsafe_policy_configuration(tmp_path: Path, policy: TestRunnerPolicy, code: str):
    result = validate_test_run_request(_request(tmp_path), allowlist=DEFAULT_ALLOWLIST, policy=policy)

    assert result["accepted"] is False
    assert code in result["rejection_codes"]
