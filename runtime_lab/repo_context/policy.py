from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RepoContextPolicy:
    max_file_size_bytes: int = 200_000
    max_files_returned: int = 5_000
    max_grep_matches: int = 1_000
    max_grep_file_size_bytes: int = 200_000
    allow_binary_files: bool = False
    allow_symlink_escape: bool = False
    include_hidden: bool = False
    redact_secret_like_patterns: bool = True
    receipt_required: bool = True
    ledger_event_required: bool = True
    default_decision: str = "REJECT_FAIL_CLOSED"
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
            "keychain",
            "keychain-dump",
        )
    )
