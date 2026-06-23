from __future__ import annotations

from pathlib import Path

import pytest

from runtime_lab.test_runner.models import CompletedTestProcess, TestCommandSpec, TestRunRequest, TestRunnerPolicy
from runtime_lab.test_runner.runner import run_allowlisted_test


def _request(tmp_path: Path, **overrides):
    values = {
        "command_id": "sample",
        "workspace_root": tmp_path,
        "cwd_relative": ".",
        "timeout_seconds": 5,
        "max_stdout_bytes": 1024,
        "max_stderr_bytes": 1024,
        "max_total_output_bytes": 2048,
    }
    values.update(overrides)
    return TestRunRequest(**values)


def _spec(argv=("python", "-m", "pytest", "tests/sample"), **overrides):
    values = {"command_id": "sample", "argv": argv}
    values.update(overrides)
    return TestCommandSpec(**values)


def _run_case(tmp_path: Path, case_id: str):
    allowlist = {"sample": _spec()}
    policy = TestRunnerPolicy()
    request = _request(tmp_path)

    if case_id == "unknown_command_id":
        request = _request(tmp_path, command_id="missing")
        return run_allowlisted_test(request, allowlist=allowlist), "UNKNOWN_COMMAND_ID"
    if case_id == "raw_command_string":
        request = _request(tmp_path, raw_command="pytest tests/test_runner")
        return run_allowlisted_test(request, allowlist=allowlist), "RAW_COMMAND_REJECTED"
    if case_id == "argv_override":
        request = _request(tmp_path, argv=("python", "-m", "pytest", "tests/test_runner"))
        return run_allowlisted_test(request, allowlist=allowlist), "ARGV_OVERRIDE_REJECTED"
    if case_id == "shell_true":
        request = _request(tmp_path, shell=True)
        return run_allowlisted_test(request, allowlist=allowlist), "SHELL_TRUE_REJECTED"
    if case_id == "bash":
        allowlist = {"sample": _spec(("bash", "-lc", "pytest tests/test_runner"))}
        return run_allowlisted_test(request, allowlist=allowlist), "DISALLOWED_COMMAND_FAMILY"
    if case_id == "sh":
        allowlist = {"sample": _spec(("sh", "-c", "pytest tests/test_runner"))}
        return run_allowlisted_test(request, allowlist=allowlist), "DISALLOWED_COMMAND_FAMILY"
    if case_id == "zsh":
        allowlist = {"sample": _spec(("zsh", "-c", "pytest tests/test_runner"))}
        return run_allowlisted_test(request, allowlist=allowlist), "DISALLOWED_COMMAND_FAMILY"
    if case_id == "python_c":
        allowlist = {"sample": _spec(("python", "-c", "print(1)"))}
        return run_allowlisted_test(request, allowlist=allowlist), "PYTHON_C_REJECTED"
    if case_id == "curl":
        allowlist = {"sample": _spec(("curl", "https://example.com"))}
        return run_allowlisted_test(request, allowlist=allowlist), "DISALLOWED_COMMAND_FAMILY"
    if case_id == "git":
        allowlist = {"sample": _spec(("git", "status"))}
        return run_allowlisted_test(request, allowlist=allowlist), "DISALLOWED_COMMAND_FAMILY"
    if case_id == "make":
        allowlist = {"sample": _spec(("make", "test"))}
        return run_allowlisted_test(request, allowlist=allowlist), "DISALLOWED_COMMAND_FAMILY"
    if case_id == "npm":
        allowlist = {"sample": _spec(("npm", "test"))}
        return run_allowlisted_test(request, allowlist=allowlist), "DISALLOWED_COMMAND_FAMILY"
    if case_id == "pytest_without_target":
        allowlist = {"sample": _spec(("python", "-m", "pytest"))}
        return run_allowlisted_test(request, allowlist=allowlist), "PYTEST_TARGET_REQUIRED"
    if case_id == "pytest_k_expression":
        allowlist = {"sample": _spec(("python", "-m", "pytest", "-k", "slow"))}
        return run_allowlisted_test(request, allowlist=allowlist), "PYTEST_K_EXPRESSION_REJECTED"
    if case_id == "pytest_live_deepseek":
        allowlist = {"sample": _spec(("python", "-m", "pytest", "tests/llm_provider", "-m", "live_deepseek"))}
        return run_allowlisted_test(request, allowlist=allowlist), "LIVE_DEEPSEEK_REJECTED"
    if case_id == "cwd_outside_workspace":
        outside = tmp_path / "outside"
        outside.mkdir()
        request = _request(tmp_path / "workspace", cwd_relative="../outside")
        return run_allowlisted_test(request, allowlist=allowlist), "CWD_PATH_TRAVERSAL_REJECTED"
    if case_id == "path_traversal_cwd":
        request = _request(tmp_path, cwd_relative="../../")
        return run_allowlisted_test(request, allowlist=allowlist), "CWD_PATH_TRAVERSAL_REJECTED"
    if case_id == "missing_timeout":
        request = _request(tmp_path, timeout_seconds=None)
        return run_allowlisted_test(request, allowlist=allowlist), "TIMEOUT_REQUIRED"
    if case_id == "timeout_too_large":
        request = _request(tmp_path, timeout_seconds=9999)
        return run_allowlisted_test(request, allowlist=allowlist), "TIMEOUT_LIMIT_EXCEEDED"
    if case_id == "missing_output_limit":
        request = _request(tmp_path, max_stdout_bytes=None)
        return run_allowlisted_test(request, allowlist=allowlist), "STDOUT_LIMIT_REQUIRED"
    if case_id == "secret_env_rejected_or_redacted":
        request = _request(
            tmp_path,
            env={"PATH": "/bin", "DEEPSEEK_API_KEY": "secret"},
            allowed_env_keys=("PATH", "DEEPSEEK_API_KEY"),
            redacted_env_keys=("DEEPSEEK_API_KEY",),
        )
        result = run_allowlisted_test(
            request,
            allowlist=allowlist,
            executor=lambda invocation: CompletedTestProcess(exit_code=0, stdout=b"", stderr=b""),
        )
        assert result["accepted"] is True
        assert result["env"]["DEEPSEEK_API_KEY"] == "<REDACTED>"
        return result, None
    if case_id == "authorization_env_rejected_or_redacted":
        request = _request(
            tmp_path,
            env={"Authorization": "Bearer secret"},
            allowed_env_keys=("Authorization",),
            redacted_env_keys=("Authorization",),
        )
        result = run_allowlisted_test(
            request,
            allowlist=allowlist,
            executor=lambda invocation: CompletedTestProcess(exit_code=0, stdout=b"", stderr=b""),
        )
        assert result["accepted"] is True
        assert result["env"]["Authorization"] == "<REDACTED>"
        return result, None
    if case_id == "network_allowed":
        request = _request(tmp_path, network_allowed=True)
        return run_allowlisted_test(request, allowlist=allowlist), "NETWORK_EXECUTION_REQUEST_REJECTED"
    if case_id == "llm_invocation":
        request = _request(tmp_path, llm_invocation_requested=True)
        return run_allowlisted_test(request, allowlist=allowlist), "LLM_INVOCATION_REQUEST_REJECTED"
    if case_id == "model_dispatch":
        request = _request(tmp_path, model_driven_executor_dispatch_requested=True)
        return run_allowlisted_test(request, allowlist=allowlist), "MODEL_DRIVEN_EXECUTOR_DISPATCH_REJECTED"
    if case_id == "receipt_missing_policy":
        policy = TestRunnerPolicy(receipt_required=False)
        return run_allowlisted_test(request, allowlist=allowlist, policy=policy), "RECEIPT_CONTRACT_REQUIRED"
    if case_id == "ledger_missing_policy":
        policy = TestRunnerPolicy(ledger_event_required=False)
        return run_allowlisted_test(request, allowlist=allowlist, policy=policy), "LEDGER_EVENT_REQUIRED"

    raise AssertionError(f"unhandled case {case_id}")


@pytest.mark.parametrize(
    "case_id",
    [
        "unknown_command_id",
        "raw_command_string",
        "argv_override",
        "shell_true",
        "bash",
        "sh",
        "zsh",
        "python_c",
        "curl",
        "git",
        "make",
        "npm",
        "pytest_without_target",
        "pytest_k_expression",
        "pytest_live_deepseek",
        "cwd_outside_workspace",
        "path_traversal_cwd",
        "missing_timeout",
        "timeout_too_large",
        "missing_output_limit",
        "secret_env_rejected_or_redacted",
        "authorization_env_rejected_or_redacted",
        "network_allowed",
        "llm_invocation",
        "model_dispatch",
        "receipt_missing_policy",
        "ledger_missing_policy",
    ],
)
def test_test_runner_negative_cases_fail_closed_or_redact(tmp_path: Path, case_id: str):
    result, expected_code = _run_case(tmp_path, case_id)

    if expected_code is None:
        assert result["shell_execution_started"] is False
        assert result["network_execution_started"] is False
        assert result["llm_invocation_started"] is False
        return

    assert result["accepted"] is False
    assert expected_code in result["rejection_codes"]
    assert result["shell_execution_started"] is False
    assert result["network_execution_started"] is False
    assert result["llm_invocation_started"] is False
