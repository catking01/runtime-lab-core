from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PatchApplyApprovalPacket:
    approval_id: str
    proposal_id: str
    proposal_hash: str
    approved_unified_diff_hash: str
    base_commit: str
    approved_target_files: tuple[str, ...]
    approved_by_actor_id: str
    approval_expires_at_utc: str
    authority_scope: str
    workspace_root_hash: str
    max_files_allowed: int
    max_bytes_allowed: int
    rollback_required: bool
    human_confirmation_text: str
    approval_nonce: str
    approval_signature_or_local_attestation: str
    approval_version: str = "patch_apply_approval.v1"


@dataclass(frozen=True)
class PatchApplyRequest:
    transaction_id: str
    proposal_id: str
    base_commit: str
    target_files: tuple[str, ...]
    tests_run: bool = False
    llm_invocation_requested: bool = False
    executor_dispatch_requested: bool = False
    shell_execution_requested: bool = False
    network_execution_requested: bool = False


@dataclass(frozen=True)
class PatchApplyPolicy:
    max_files_allowed: int = 10
    max_bytes_allowed: int = 200_000
    max_target_file_bytes: int = 200_000
    allow_new_files: bool = False
    allow_delete_files: bool = False
    receipt_required: bool = True
    ledger_event_required: bool = True
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


@dataclass(frozen=True)
class PatchApplyResult:
    accepted: bool = False
    apply_performed: bool = False
    workspace_mutation_performed: bool = False
    approval_verified: bool = False
    preimage_verified: bool = False
    postimage_verified: bool = False
    rollback_artifact_written: bool = False
    receipt_written: bool = False
    tests_run: bool = False
    llm_invocation_performed: bool = False
    executor_dispatch_performed: bool = False


@dataclass(frozen=True)
class DiffLine:
    kind: str
    text: str


@dataclass(frozen=True)
class DiffHunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: tuple[DiffLine, ...]


@dataclass(frozen=True)
class FilePatch:
    target_path: str
    hunks: tuple[DiffHunk, ...]
