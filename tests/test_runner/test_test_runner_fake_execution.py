from __future__ import annotations

from pathlib import Path

from runtime_lab.test_runner.models import CompletedTestProcess, TestCommandSpec, TestRunRequest
from runtime_lab.test_runner.runner import TestRunnerTimeout, run_allowlisted_test


def _request(tmp_path: Path, **overrides):
    values = {
        "command_id": "sample",
        "workspace_root": tmp_path,
        "cwd_relative": ".",
        "timeout_seconds": 5,
        "max_stdout_bytes": 8,
        "max_stderr_bytes": 8,
        "max_total_output_bytes": 16,
    }
    values.update(overrides)
    return TestRunRequest(**values)


def _allowlist():
    return {"sample": TestCommandSpec(command_id="sample", argv=("python", "-m", "pytest", "tests/sample"))}


def test_fake_execution_success_records_receipt_and_ledger_event(tmp_path: Path):
    calls = []

    def fake_executor(invocation):
        calls.append(invocation)
        return CompletedTestProcess(exit_code=0, stdout=b"passed\n", stderr=b"")

    result = run_allowlisted_test(_request(tmp_path), allowlist=_allowlist(), executor=fake_executor)

    assert result["accepted"] is True
    assert result["result"] == "SUCCESS"
    assert result["exit_code"] == 0
    assert result["receipt"]["result"] == "SUCCESS"
    assert result["ledger_event"]["event_type"] == "test_runner.sample"
    assert result["ledger_event"]["receipt_hash"] == result["receipt"]["receipt_hash"]
    assert calls[0]["argv"] == ("python", "-m", "pytest", "tests/sample")
    assert calls[0]["cwd"] == tmp_path
    assert calls[0]["shell"] is False


def test_fake_execution_records_nonzero_exit_without_raising(tmp_path: Path):
    def fake_executor(_invocation):
        return CompletedTestProcess(exit_code=3, stdout=b"", stderr=b"failed")

    result = run_allowlisted_test(_request(tmp_path), allowlist=_allowlist(), executor=fake_executor)

    assert result["accepted"] is True
    assert result["result"] == "FAILED_EXIT_CODE"
    assert result["exit_code"] == 3
    assert result["receipt"]["stderr_hash"].startswith("sha256:")


def test_fake_execution_truncates_output_and_preserves_full_hashes(tmp_path: Path):
    def fake_executor(_invocation):
        return CompletedTestProcess(exit_code=0, stdout=b"0123456789abcdef", stderr=b"abcdefghijk")

    result = run_allowlisted_test(_request(tmp_path), allowlist=_allowlist(), executor=fake_executor)

    assert result["accepted"] is True
    assert result["stdout"] == "01234567"
    assert result["stderr"] == "abcdefgh"
    assert result["receipt"]["stdout_truncated"] is True
    assert result["receipt"]["stderr_truncated"] is True
    assert result["receipt"]["stdout_recorded"] is False
    assert result["receipt"]["stderr_recorded"] is False


def test_fake_execution_timeout_produces_timeout_receipt(tmp_path: Path):
    def fake_executor(_invocation):
        raise TestRunnerTimeout("timed out")

    result = run_allowlisted_test(_request(tmp_path), allowlist=_allowlist(), executor=fake_executor)

    assert result["accepted"] is True
    assert result["result"] == "TIMEOUT"
    assert result["exit_code"] is None
    assert result["receipt"]["result"] == "TIMEOUT"
    assert result["receipt"]["timeout_seconds"] == 5
