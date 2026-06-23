from __future__ import annotations

from runtime_lab.test_runner.receipts import build_test_run_receipt, canonical_hash, sha256_bytes, verify_test_run_receipt


def test_receipt_records_argv_output_hashes_and_non_claims():
    receipt = build_test_run_receipt(
        command_id="patch_apply",
        argv=("python", "-m", "pytest", "tests/patch_apply"),
        cwd_relative=".",
        workspace_root="/workspace",
        timeout_seconds=120,
        started_at_utc="2026-06-20T15:00:00Z",
        ended_at_utc="2026-06-20T15:00:01Z",
        elapsed_ms=1000,
        exit_code=0,
        stdout=b"ok",
        stderr=b"",
        stdout_truncated=False,
        stderr_truncated=False,
        result="SUCCESS",
    )

    assert receipt["receipt_type"] == "ALLOWLISTED_TEST_RUNNER_RECEIPT"
    assert receipt["milestone"] == "R127_ALLOWLISTED_TEST_RUNNER_LOCAL_VALIDATION"
    assert receipt["argv_hash"] == canonical_hash(["python", "-m", "pytest", "tests/patch_apply"])
    assert receipt["stdout_hash"] == sha256_bytes(b"ok")
    assert receipt["stderr_hash"] == sha256_bytes(b"")
    assert receipt["stdout_recorded"] is False
    assert receipt["stderr_recorded"] is False
    assert receipt["shell_used"] is False
    assert receipt["network_allowed"] is False
    assert receipt["llm_invocation_allowed"] is False
    assert receipt["non_claims"]["remote_sealed_pass"] is False
    assert verify_test_run_receipt(receipt) is True


def test_receipt_verification_rejects_tampering():
    receipt = build_test_run_receipt(
        command_id="repo_context",
        argv=("python", "-m", "pytest", "tests/repo_context"),
        cwd_relative=".",
        workspace_root="/workspace",
        timeout_seconds=120,
        started_at_utc="2026-06-20T15:00:00Z",
        ended_at_utc="2026-06-20T15:00:01Z",
        elapsed_ms=1000,
        exit_code=1,
        stdout=b"",
        stderr=b"failed",
        stdout_truncated=False,
        stderr_truncated=False,
        result="FAILED_EXIT_CODE",
    )

    tampered = dict(receipt)
    tampered["exit_code"] = 0

    assert verify_test_run_receipt(tampered) is False
