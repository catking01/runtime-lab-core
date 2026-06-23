from __future__ import annotations

from pathlib import Path

from runtime_lab.test_runner.models import CompletedTestProcess, TestCommandSpec, TestRunRequest, TestRunnerPolicy


def test_test_runner_policy_defaults_are_fail_closed():
    policy = TestRunnerPolicy()

    assert policy.shell_allowed is False
    assert policy.network_allowed is False
    assert policy.llm_invocation_allowed is False
    assert policy.allow_live_deepseek is False
    assert policy.model_driven_executor_dispatch_allowed is False
    assert policy.receipt_required is True
    assert policy.ledger_event_required is True
    assert policy.default_decision == "REJECT_FAIL_CLOSED"
    assert policy.timeout_seconds == 120
    assert policy.max_stdout_bytes == 200_000
    assert policy.max_stderr_bytes == 200_000
    assert policy.max_total_output_bytes == 400_000


def test_command_spec_normalizes_argv_to_tuple():
    spec = TestCommandSpec(command_id="repo_context", argv=["python", "-m", "pytest", "tests/repo_context"])

    assert spec.command_id == "repo_context"
    assert spec.argv == ("python", "-m", "pytest", "tests/repo_context")
    assert spec.cwd_relative == "."
    assert spec.shell_allowed is False
    assert spec.network_allowed is False
    assert spec.llm_invocation_allowed is False


def test_run_request_requires_command_id_workspace_cwd_and_limits(tmp_path: Path):
    request = TestRunRequest(
        command_id="test_runner",
        workspace_root=tmp_path,
        cwd_relative=".",
        timeout_seconds=30,
        max_stdout_bytes=1024,
        max_stderr_bytes=1024,
        max_total_output_bytes=2048,
    )

    assert request.command_id == "test_runner"
    assert request.workspace_root == tmp_path
    assert request.cwd_relative == "."
    assert request.timeout_seconds == 30
    assert request.raw_command is None
    assert request.argv is None
    assert request.shell is False


def test_completed_process_model_records_bytes_and_exit_code():
    completed = CompletedTestProcess(exit_code=7, stdout=b"out", stderr=b"err")

    assert completed.exit_code == 7
    assert completed.stdout == b"out"
    assert completed.stderr == b"err"
