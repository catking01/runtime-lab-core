from __future__ import annotations

import sys
from pathlib import Path

from runtime_lab.test_runner.models import TestCommandSpec, TestRunRequest
from runtime_lab.test_runner.runner import run_allowlisted_test


def test_real_process_execution_runs_allowlisted_pytest_in_workspace(tmp_path: Path):
    workspace = tmp_path / "workspace"
    sample_tests = workspace / "sample_tests"
    sample_tests.mkdir(parents=True)
    (sample_tests / "test_sample.py").write_text(
        "def test_sample_passes():\n    assert 1 + 1 == 2\n",
        encoding="utf-8",
    )
    request = TestRunRequest(
        command_id="sample_pytest",
        workspace_root=workspace,
        cwd_relative=".",
        timeout_seconds=30,
        max_stdout_bytes=4000,
        max_stderr_bytes=4000,
        max_total_output_bytes=8000,
    )
    allowlist = {
        "sample_pytest": TestCommandSpec(
            command_id="sample_pytest",
            argv=(sys.executable, "-m", "pytest", "sample_tests", "-q"),
        )
    }

    result = run_allowlisted_test(request, allowlist=allowlist)

    assert result["accepted"] is True
    assert result["result"] == "SUCCESS"
    assert result["exit_code"] == 0
    assert result["receipt"]["shell_used"] is False
    assert result["receipt"]["cwd_relative"] == "."
    assert result["receipt"]["stdout_hash"].startswith("sha256:")
