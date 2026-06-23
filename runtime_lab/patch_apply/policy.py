from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from runtime_lab.patch_apply.approval import validate_approval_packet
from runtime_lab.patch_apply.diff_apply import parse_unified_diff
from runtime_lab.patch_apply.errors import PatchApplyPolicyError
from runtime_lab.patch_apply.models import PatchApplyPolicy
from runtime_lab.patch_apply.path_policy import resolve_patch_apply_target_path
from runtime_lab.patch_apply.receipts import canonical_hash, sha256_bytes


FORBIDDEN_REQUEST_FIELD_CODES = {
    "shell_command": "SHELL_EXECUTION_REQUEST_REJECTED",
    "shell_execution_requested": "SHELL_EXECUTION_REQUEST_REJECTED",
    "network_instruction": "NETWORK_EXECUTION_REQUEST_REJECTED",
    "network_execution_requested": "NETWORK_EXECUTION_REQUEST_REJECTED",
    "llm_invocation_requested": "LLM_INVOCATION_REQUEST_REJECTED",
    "executor_dispatch_requested": "EXECUTOR_DISPATCH_REQUEST_REJECTED",
    "tests_run": "TEST_EXECUTION_REQUEST_REJECTED",
    "test_execution_requested": "TEST_EXECUTION_REQUEST_REJECTED",
}

FORBIDDEN_PROPOSAL_CLAIM_CODES = {
    "apply_allowed": "PROPOSAL_APPLICATION_ALLOWED_REJECTED",
    "apply_performed": "PROPOSAL_APPLICATION_CLAIM_REJECTED",
    "workspace_mutation_performed": "PROPOSAL_WORKSPACE_MUTATION_CLAIM_REJECTED",
    "test_execution_allowed": "PROPOSAL_TEST_EXECUTION_ALLOWED_REJECTED",
    "test_execution_performed": "PROPOSAL_TEST_EXECUTION_CLAIM_REJECTED",
}


def _base_result(*, accepted: bool, rejection_codes: list[str] | None = None) -> dict[str, Any]:
    return {
        "accepted": accepted,
        "rejection_codes": list(dict.fromkeys(rejection_codes or [])),
        "approval_verified": False,
        "preimage_verified": False,
        "postimage_verified": False,
        "rollback_artifact_written": False,
        "receipt_written": False,
        "apply_performed": False,
        "workspace_mutation_performed": False,
        "tests_run": False,
        "llm_invocation_performed": False,
        "executor_dispatch_performed": False,
        "shell_execution_performed": False,
        "network_execution_performed": False,
    }


def _mapping(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    return dict(value)


def _string_list(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    if not all(isinstance(item, str) and item for item in value):
        return None
    return list(value)


def _target_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise PatchApplyPolicyError("TARGET_FILE_READ_FAILED") from exc


def _is_text_bytes(value: bytes) -> bool:
    if b"\x00" in value:
        return False
    try:
        value.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def validate_patch_apply_request(
    request: Any,
    *,
    workspace_root: Any,
    policy: PatchApplyPolicy | None = None,
) -> dict[str, Any]:
    policy = policy or PatchApplyPolicy()
    if not policy.receipt_required:
        return _base_result(accepted=False, rejection_codes=["RECEIPT_CONTRACT_REQUIRED"])
    if not policy.ledger_event_required:
        return _base_result(accepted=False, rejection_codes=["LEDGER_EVENT_REQUIRED"])

    request_map = _mapping(request)
    if request_map is None:
        return _base_result(accepted=False, rejection_codes=["PATCH_APPLY_REQUEST_MALFORMED"])

    errors: list[str] = []
    transaction_id = request_map.get("transaction_id")
    if not isinstance(transaction_id, str) or not transaction_id or "/" in transaction_id:
        errors.append("TRANSACTION_ID_REQUIRED")

    proposal = _mapping(request_map.get("proposal"))
    if proposal is None:
        errors.append("PROPOSAL_REQUIRED")
        proposal = {}
    approval_packet = request_map.get("approval_packet")
    if approval_packet is None:
        errors.append("APPROVAL_PACKET_REQUIRED")

    for field, code in FORBIDDEN_REQUEST_FIELD_CODES.items():
        if request_map.get(field):
            errors.append(code)

    for field, code in FORBIDDEN_PROPOSAL_CLAIM_CODES.items():
        expected = False
        if proposal.get(field) is not expected:
            errors.append(code)

    if proposal.get("artifact_only") is not True:
        errors.append("PROPOSAL_ARTIFACT_ONLY_REQUIRED")
    if proposal.get("human_approval_required") is not True:
        errors.append("PROPOSAL_HUMAN_APPROVAL_REQUIRED")
    if request_map.get("base_commit") != proposal.get("base_commit"):
        errors.append("BASE_COMMIT_MISMATCH")

    target_files = _string_list(proposal.get("target_files"))
    if not target_files:
        errors.append("TARGET_FILES_REQUIRED")
        target_files = []
    if len(target_files) > policy.max_files_allowed:
        errors.append("POLICY_MAX_FILES_EXCEEDED")

    diff_text = proposal.get("unified_diff")
    if not isinstance(diff_text, str) or not diff_text:
        errors.append("UNIFIED_DIFF_REQUIRED")
        diff_text = ""
    if len(diff_text.encode("utf-8")) > policy.max_bytes_allowed:
        errors.append("PATCH_SIZE_LIMIT_EXCEEDED")

    parsed_targets: list[str] = []
    if diff_text:
        try:
            parsed_targets = [patch.target_path for patch in parse_unified_diff(diff_text)]
        except PatchApplyPolicyError as exc:
            errors.append(exc.code)
    if parsed_targets and target_files and parsed_targets != target_files:
        errors.append("TARGET_FILES_DIFF_MISMATCH")

    approval_result = validate_approval_packet(approval_packet, proposal=proposal, workspace_root=workspace_root)
    if not approval_result["accepted"]:
        errors.extend(approval_result["rejection_codes"])

    preimage_hashes: dict[str, str] = {}
    target_paths: dict[str, str] = {}
    proposal_hashes = proposal.get("target_file_hashes")
    if not isinstance(proposal_hashes, Mapping):
        errors.append("PREIMAGE_HASHES_REQUIRED")
        proposal_hashes = {}

    for target in target_files:
        try:
            path = resolve_patch_apply_target_path(workspace_root=workspace_root, target_path=target, policy=policy)
        except PatchApplyPolicyError as exc:
            errors.append(exc.code)
            continue
        if not path.exists():
            errors.append("TARGET_FILE_MISSING")
            continue
        if not path.is_file():
            errors.append("TARGET_FILE_NOT_REGULAR")
            continue
        if path.stat().st_size > policy.max_target_file_bytes:
            errors.append("TARGET_SIZE_LIMIT_EXCEEDED")
            continue
        data = _target_bytes(path)
        if not _is_text_bytes(data):
            errors.append("BINARY_TARGET_REJECTED")
            continue
        current_hash = sha256_bytes(data)
        preimage_hashes[target] = current_hash
        target_paths[target] = str(path)
        expected_hash = proposal_hashes.get(target)
        if not expected_hash:
            errors.append("PREIMAGE_HASH_MISSING")
        elif expected_hash != current_hash:
            errors.append("PREIMAGE_HASH_MISMATCH")

    if errors:
        return _base_result(accepted=False, rejection_codes=errors)

    result = _base_result(accepted=True)
    result.update(
        {
            "transaction_id": transaction_id,
            "proposal_id": proposal["proposal_id"],
            "proposal_hash": canonical_hash(proposal),
            "approval_id": approval_result["approval_id"],
            "approval_hash": approval_result["approval_hash"],
            "base_commit": proposal["base_commit"],
            "workspace_root_hash": approval_result["workspace_root_hash"],
            "target_files": target_files,
            "target_paths": target_paths,
            "preimage_hashes": preimage_hashes,
            "unified_diff_hash": proposal["unified_diff_hash"],
            "approval_verified": True,
            "preimage_verified": True,
        }
    )
    return result
