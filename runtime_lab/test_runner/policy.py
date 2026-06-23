from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime_lab.test_runner.allowlist import DEFAULT_ALLOWLIST, resolve_command_spec
from runtime_lab.test_runner.errors import TestRunnerPolicyError
from runtime_lab.test_runner.models import TestCommandSpec, TestRunRequest, TestRunnerPolicy


def _base_result(command_id: str) -> dict[str, Any]:
    return {
        "command_id": command_id,
        "accepted": False,
        "rejection_codes": [],
        "test_execution_started": False,
        "shell_execution_started": False,
        "network_execution_started": False,
        "llm_invocation_started": False,
        "model_driven_executor_dispatch_started": False,
    }


def _reject(command_id: str, code: str) -> dict[str, Any]:
    result = _base_result(command_id)
    result["rejection_codes"] = [code]
    return result


def _policy_rejection(policy: TestRunnerPolicy) -> str | None:
    if not policy.receipt_required:
        return "RECEIPT_CONTRACT_REQUIRED"
    if not policy.ledger_event_required:
        return "LEDGER_EVENT_REQUIRED"
    if policy.shell_allowed:
        return "SHELL_POLICY_REJECTED"
    if policy.network_allowed:
        return "NETWORK_POLICY_REJECTED"
    if policy.llm_invocation_allowed:
        return "LLM_POLICY_REJECTED"
    if policy.allow_live_deepseek:
        return "LIVE_DEEPSEEK_POLICY_REJECTED"
    if policy.model_driven_executor_dispatch_allowed:
        return "MODEL_DRIVEN_EXECUTOR_DISPATCH_POLICY_REJECTED"
    return None


def _request_rejection(request: TestRunRequest, policy: TestRunnerPolicy) -> str | None:
    if request.raw_command is not None:
        return "RAW_COMMAND_REJECTED"
    if request.argv is not None:
        return "ARGV_OVERRIDE_REJECTED"
    if request.shell:
        return "SHELL_TRUE_REJECTED"
    if request.network_allowed:
        return "NETWORK_EXECUTION_REQUEST_REJECTED"
    if request.llm_invocation_requested:
        return "LLM_INVOCATION_REQUEST_REJECTED"
    if request.model_driven_executor_dispatch_requested:
        return "MODEL_DRIVEN_EXECUTOR_DISPATCH_REJECTED"
    if request.allow_live_deepseek:
        return "LIVE_DEEPSEEK_REJECTED"
    if request.timeout_seconds is None or request.timeout_seconds <= 0:
        return "TIMEOUT_REQUIRED"
    if request.timeout_seconds > policy.timeout_seconds:
        return "TIMEOUT_LIMIT_EXCEEDED"
    if request.max_stdout_bytes is None or request.max_stdout_bytes <= 0:
        return "STDOUT_LIMIT_REQUIRED"
    if request.max_stderr_bytes is None or request.max_stderr_bytes <= 0:
        return "STDERR_LIMIT_REQUIRED"
    if request.max_total_output_bytes is None or request.max_total_output_bytes <= 0:
        return "TOTAL_OUTPUT_LIMIT_REQUIRED"
    if request.max_stdout_bytes > policy.max_stdout_bytes:
        return "STDOUT_LIMIT_EXCEEDED"
    if request.max_stderr_bytes > policy.max_stderr_bytes:
        return "STDERR_LIMIT_EXCEEDED"
    if request.max_total_output_bytes > policy.max_total_output_bytes:
        return "TOTAL_OUTPUT_LIMIT_EXCEEDED"
    if request.max_total_output_bytes < max(request.max_stdout_bytes, request.max_stderr_bytes):
        return "TOTAL_OUTPUT_LIMIT_TOO_SMALL"
    return None


def resolve_cwd(request: TestRunRequest) -> Path:
    root = request.workspace_root.resolve()
    cwd = (root / request.cwd_relative).resolve()
    try:
        cwd.relative_to(root)
    except ValueError as exc:
        raise TestRunnerPolicyError("CWD_PATH_TRAVERSAL_REJECTED") from exc
    if not root.exists() or not root.is_dir():
        raise TestRunnerPolicyError("WORKSPACE_ROOT_NOT_FOUND")
    if not cwd.exists() or not cwd.is_dir():
        raise TestRunnerPolicyError("CWD_NOT_FOUND")
    return cwd


def validate_test_run_request(
    request: TestRunRequest,
    *,
    allowlist: dict[str, TestCommandSpec] | None = None,
    policy: TestRunnerPolicy | None = None,
) -> dict[str, Any]:
    policy = policy or TestRunnerPolicy()
    policy_code = _policy_rejection(policy)
    if policy_code:
        return _reject(request.command_id, policy_code)
    request_code = _request_rejection(request, policy)
    if request_code:
        return _reject(request.command_id, request_code)
    try:
        spec = resolve_command_spec(request.command_id, allowlist=allowlist or DEFAULT_ALLOWLIST)
        cwd = resolve_cwd(request)
    except TestRunnerPolicyError as exc:
        return _reject(request.command_id, exc.code)

    result = _base_result(request.command_id)
    result.update(
        {
            "accepted": True,
            "rejection_codes": [],
            "spec": spec,
            "cwd": cwd,
        }
    )
    return result
