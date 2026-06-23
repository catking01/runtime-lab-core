from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from runtime_lab.patch_proposal.diff_parser import parse_unified_diff
from runtime_lab.patch_proposal.errors import PatchProposalPolicyError
from runtime_lab.patch_proposal.path_policy import resolve_patch_target_path
from runtime_lab.patch_proposal.receipts import canonical_hash, sha256_bytes


@dataclass(frozen=True)
class PatchProposalPolicy:
    max_patch_size_bytes: int = 200_000
    allow_new_files: bool = False
    allow_delete_files: bool = False
    receipt_required: bool = True
    ledger_event_required: bool = True
    redact_secret_like_patterns: bool = True
    denied_path_patterns: tuple[str, ...] = field(
        default_factory=lambda: (
            ".git",
            ".env",
            ".codex/sessions",
            ".codex/archived_sessions",
            "id_rsa",
            "id_dsa",
            "id_ecdsa",
            "id_ed25519",
            ".pem",
            ".key",
            ".p12",
            ".pfx",
            "keychain",
            "keychain-dump",
        )
    )


REQUIRED_FIELDS = (
    "proposal_id",
    "base_commit",
    "target_files",
    "unified_diff",
    "risk_class",
    "change_summary",
    "validation_plan",
    "rollback_plan",
)

FORBIDDEN_FIELD_CODES = {
    "shell_command": "SHELL_EXECUTION_REQUEST_REJECTED",
    "shell_execution_requested": "SHELL_EXECUTION_REQUEST_REJECTED",
    "network_instruction": "NETWORK_EXECUTION_REQUEST_REJECTED",
    "network_execution_requested": "NETWORK_EXECUTION_REQUEST_REJECTED",
    "llm_invocation_requested": "LLM_INVOCATION_REQUEST_REJECTED",
    "executor_dispatch_requested": "EXECUTOR_DISPATCH_REQUEST_REJECTED",
    "workspace_mutation_requested": "WORKSPACE_MUTATION_REQUEST_REJECTED",
}


def _base_result(*, accepted: bool, rejection_codes: list[str] | None = None) -> dict[str, Any]:
    return {
        "accepted": accepted,
        "rejection_codes": list(dict.fromkeys(rejection_codes or [])),
        "artifact_only": True,
        "apply_allowed": False,
        "apply_performed": False,
        "workspace_mutation_performed": False,
        "test_execution_allowed": False,
        "test_execution_performed": False,
        "llm_invocation_performed": False,
        "model_driven_executor_dispatch_performed": False,
        "shell_execution_performed": False,
        "network_execution_performed": False,
    }


def _reject(codes: list[str]) -> dict[str, Any]:
    return _base_result(accepted=False, rejection_codes=codes)


def _string_list(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    if not all(isinstance(item, str) and item for item in value):
        return None
    return list(value)


def _hash_existing_targets(workspace_root: Path, target_files: list[str]) -> tuple[dict[str, str], list[str]]:
    hashes: dict[str, str] = {}
    errors: list[str] = []
    for target in target_files:
        try:
            resolved = resolve_patch_target_path(workspace_root=workspace_root, target_path=target)
        except PatchProposalPolicyError as exc:
            errors.append(exc.code)
            continue
        if not resolved.is_file():
            errors.append("TARGET_FILE_MISSING")
            continue
        hashes[target] = sha256_bytes(resolved.read_bytes())
    return hashes, errors


def validate_patch_proposal_request(
    request: Any,
    *,
    workspace_root: Any,
    policy: PatchProposalPolicy | None = None,
) -> dict[str, Any]:
    policy = policy or PatchProposalPolicy()
    if not policy.receipt_required:
        return _reject(["RECEIPT_CONTRACT_REQUIRED"])
    if not policy.ledger_event_required:
        return _reject(["LEDGER_EVENT_REQUIRED"])
    if not isinstance(request, Mapping):
        return _reject(["PATCH_PROPOSAL_REQUEST_MALFORMED"])

    request_map = dict(request)
    errors: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in request_map:
            errors.append("PATCH_PROPOSAL_REQUEST_MISSING_REQUIRED_FIELD")

    proposal_id = request_map.get("proposal_id")
    if not isinstance(proposal_id, str) or not proposal_id:
        errors.append("PROPOSAL_ID_REQUIRED")

    base_commit = request_map.get("base_commit")
    if not isinstance(base_commit, str) or not base_commit:
        errors.append("BASE_COMMIT_REQUIRED")

    target_files = _string_list(request_map.get("target_files"))
    if not target_files:
        errors.append("TARGET_FILES_REQUIRED")
        target_files = []

    unified_diff = request_map.get("unified_diff")
    if not isinstance(unified_diff, str) or not unified_diff:
        errors.append("UNIFIED_DIFF_REQUIRED")
        unified_diff = ""
    elif len(unified_diff.encode("utf-8")) > policy.max_patch_size_bytes:
        errors.append("PATCH_SIZE_LIMIT_EXCEEDED")

    if request_map.get("apply_allowed") is not False:
        errors.append("PATCH_APPLICATION_ALLOWED_REJECTED")
    if request_map.get("apply_performed") is not False:
        errors.append("PATCH_APPLICATION_CLAIM_REJECTED")
    if request_map.get("workspace_mutation_performed") is not False:
        errors.append("WORKSPACE_MUTATION_CLAIM_REJECTED")
    if request_map.get("test_execution_allowed") is not False:
        errors.append("TEST_EXECUTION_ALLOWED_REJECTED")
    if request_map.get("test_execution_performed") is not False:
        errors.append("TEST_EXECUTION_CLAIM_REJECTED")
    if request_map.get("human_approval_required") is not True:
        errors.append("HUMAN_APPROVAL_REQUIRED")

    for field, code in FORBIDDEN_FIELD_CODES.items():
        if request_map.get(field):
            errors.append(code)

    parsed_targets: list[str] = []
    if unified_diff and "PATCH_SIZE_LIMIT_EXCEEDED" not in errors:
        try:
            parsed = parse_unified_diff(unified_diff)
            parsed_targets = list(parsed.target_files)
        except PatchProposalPolicyError as exc:
            errors.append(exc.code)

    if parsed_targets and target_files and parsed_targets != target_files:
        errors.append("TARGET_FILES_DIFF_MISMATCH")

    root = Path(workspace_root).expanduser().resolve()
    target_hashes, target_errors = _hash_existing_targets(root, target_files)
    errors.extend(target_errors)

    if errors:
        return _reject(errors)

    result = _base_result(accepted=True)
    result.update(
        {
            "proposal_id": proposal_id,
            "base_commit": base_commit,
            "target_files": target_files,
            "target_file_hashes": target_hashes,
            "target_file_hashes_recorded": bool(target_hashes),
            "unified_diff_hash": canonical_hash(unified_diff),
            "human_approval_required": True,
        }
    )
    return result
