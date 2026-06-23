from __future__ import annotations

import copy
from pathlib import Path

from runtime_lab.patch_apply.receipts import verify_patch_apply_receipt
from runtime_lab.patch_apply.transaction import apply_patch_transaction

from .conftest import make_request, make_workspace


def test_patch_apply_receipt_is_hash_bound_and_tamper_sensitive(tmp_path: Path):
    workspace = make_workspace(tmp_path)
    result = apply_patch_transaction(make_request(workspace), workspace_root=workspace, transaction_dir=tmp_path / "tx")

    receipt = result["receipt"]

    assert verify_patch_apply_receipt(receipt) is True
    assert receipt["receipt_type"] == "HUMAN_APPROVED_PATCH_APPLY_TRANSACTION_RECEIPT"
    assert receipt["apply_performed"] is True
    assert receipt["workspace_mutation_performed"] is True
    assert receipt["human_approval_required"] is True
    assert receipt["human_approval_verified"] is True
    assert receipt["tests_run"] is False
    assert receipt["llm_invocation_performed"] is False
    assert receipt["executor_dispatch_performed"] is False
    assert receipt["shell_execution_performed"] is False
    assert receipt["network_execution_performed"] is False
    assert receipt["non_claims"]["autonomous_patching"] is False
    assert receipt["non_claims"]["remote_sealed_pass"] is False

    tampered = copy.deepcopy(receipt)
    tampered["tests_run"] = True
    assert verify_patch_apply_receipt(tampered) is False
