from __future__ import annotations

from runtime_lab.agent_loop.receipts import build_agent_loop_receipt, verify_agent_loop_receipt


def test_agent_loop_receipt_verifies():
    receipt = build_agent_loop_receipt(
        task_id="task-1",
        run_id="run-1",
        base_commit="abc123",
        workspace_root_hash="sha256:workspace",
        policy_hash="sha256:policy",
        state_transition_hash_chain="sha256:states",
        artifact_hashes={"proposal": "sha256:proposal"},
        executor_receipt_hashes={"test": "sha256:test"},
        final_result="SUCCESS",
        non_claims={"remote_sealed_pass": False},
    )

    assert receipt["receipt_hash"].startswith("sha256:")
    assert verify_agent_loop_receipt(receipt) is True


def test_agent_loop_receipt_detects_tamper():
    receipt = build_agent_loop_receipt(
        task_id="task-1",
        run_id="run-1",
        base_commit="abc123",
        workspace_root_hash="sha256:workspace",
        policy_hash="sha256:policy",
        state_transition_hash_chain="sha256:states",
        artifact_hashes={},
        executor_receipt_hashes={},
        final_result="SUCCESS",
        non_claims={"remote_sealed_pass": False},
    )
    receipt["final_result"] = "REMOTE_SEALED_PASS"

    assert verify_agent_loop_receipt(receipt) is False
