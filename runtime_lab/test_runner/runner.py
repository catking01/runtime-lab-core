"""Allowlisted pytest command runner for R127.

The runner accepts command IDs from a fixed allowlist, executes with
``shell=False``, bounds output capture, redacts the environment, and records a
receipt without allowing arbitrary command strings.
"""

from __future__ import annotations

from datetime import UTC, datetime
import os
from pathlib import Path
import subprocess
import time
from typing import Any, Callable

from runtime_lab.test_runner.allowlist import DEFAULT_ALLOWLIST
from runtime_lab.test_runner.errors import TestRunnerTimeoutError
from runtime_lab.test_runner.models import CompletedTestProcess, TestCommandSpec, TestRunRequest, TestRunnerPolicy
from runtime_lab.test_runner.policy import _reject, validate_test_run_request
from runtime_lab.test_runner.receipts import build_test_run_receipt
from runtime_lab.test_runner.redaction import redact_environment


TestRunnerTimeout = TestRunnerTimeoutError


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _base_env(request: TestRunRequest) -> dict[str, str]:
    env = {key: os.environ[key] for key in request.allowed_env_keys if key in os.environ}
    env.update(dict(request.env))
    return env


def _default_executor(invocation: dict[str, Any]) -> CompletedTestProcess:
    completed = subprocess.run(
        list(invocation["argv"]),
        cwd=invocation["cwd"],
        env=invocation["env"],
        shell=False,
        capture_output=True,
        timeout=invocation["timeout_seconds"],
        check=False,
    )
    return CompletedTestProcess(exit_code=completed.returncode, stdout=completed.stdout, stderr=completed.stderr)


def _truncate_outputs(
    *,
    stdout: bytes,
    stderr: bytes,
    max_stdout_bytes: int,
    max_stderr_bytes: int,
    max_total_output_bytes: int,
) -> tuple[bytes, bytes, bool, bool]:
    stdout_limit = min(max_stdout_bytes, max_total_output_bytes)
    recorded_stdout = stdout[:stdout_limit]
    remaining = max(max_total_output_bytes - len(recorded_stdout), 0)
    stderr_limit = min(max_stderr_bytes, remaining)
    recorded_stderr = stderr[:stderr_limit]
    return recorded_stdout, recorded_stderr, len(recorded_stdout) < len(stdout), len(recorded_stderr) < len(stderr)


def _ledger_event(command_id: str, receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_type": f"test_runner.{command_id}",
        "receipt_hash": receipt["receipt_hash"],
        "test_execution_allowed": True,
        "arbitrary_command_execution_allowed": False,
        "shell_used": False,
    }


def _failure_result(command_id: str, code: str) -> dict[str, Any]:
    return _reject(command_id, code)


def run_allowlisted_test(
    request: TestRunRequest,
    *,
    allowlist: dict[str, TestCommandSpec] | None = None,
    policy: TestRunnerPolicy | None = None,
    executor: Callable[[dict[str, Any]], CompletedTestProcess] | None = None,
) -> dict[str, Any]:
    """Run one allowlisted test command and return receipt-bound output."""

    validation = validate_test_run_request(request, allowlist=allowlist or DEFAULT_ALLOWLIST, policy=policy)
    if not validation["accepted"]:
        return validation

    spec: TestCommandSpec = validation["spec"]
    cwd: Path = validation["cwd"]
    safe_env, env_meta = redact_environment(
        _base_env(request),
        allowed_env_keys=request.allowed_env_keys,
        redacted_env_keys=request.redacted_env_keys,
    )
    if env_meta["secret_like_values_present"]:
        return _failure_result(request.command_id, "UNREDACTED_SECRET_ENV_REJECTED")

    invocation = {
        "argv": spec.argv,
        "cwd": cwd,
        "env": safe_env,
        "timeout_seconds": request.timeout_seconds,
        "shell": False,
    }
    runner = executor or _default_executor
    started = _utc_now()
    start_monotonic = time.monotonic()
    stdout = b""
    stderr = b""
    exit_code: int | None = None
    result_code = "SUCCESS"

    try:
        completed = runner(invocation)
        stdout = completed.stdout
        stderr = completed.stderr
        exit_code = completed.exit_code
        if exit_code != 0:
            result_code = "FAILED_EXIT_CODE"
    except (TestRunnerTimeoutError, subprocess.TimeoutExpired):
        result_code = "TIMEOUT"

    ended = _utc_now()
    elapsed_ms = int((time.monotonic() - start_monotonic) * 1000)
    recorded_stdout, recorded_stderr, stdout_truncated, stderr_truncated = _truncate_outputs(
        stdout=stdout,
        stderr=stderr,
        max_stdout_bytes=int(request.max_stdout_bytes),
        max_stderr_bytes=int(request.max_stderr_bytes),
        max_total_output_bytes=int(request.max_total_output_bytes),
    )
    receipt = build_test_run_receipt(
        command_id=request.command_id,
        argv=spec.argv,
        cwd_relative=request.cwd_relative,
        workspace_root=str(request.workspace_root.resolve()),
        timeout_seconds=int(request.timeout_seconds),
        started_at_utc=started,
        ended_at_utc=ended,
        elapsed_ms=elapsed_ms,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        stdout_truncated=stdout_truncated,
        stderr_truncated=stderr_truncated,
        result=result_code,
    )
    return {
        "command_id": request.command_id,
        "accepted": True,
        "rejection_codes": [],
        "test_execution_started": True,
        "shell_execution_started": False,
        "network_execution_started": False,
        "llm_invocation_started": False,
        "model_driven_executor_dispatch_started": False,
        "result": result_code,
        "exit_code": exit_code,
        "stdout": recorded_stdout.decode("utf-8", errors="replace"),
        "stderr": recorded_stderr.decode("utf-8", errors="replace"),
        "env": safe_env,
        "env_redaction": env_meta,
        "receipt": receipt,
        "ledger_event": _ledger_event(request.command_id, receipt),
    }
