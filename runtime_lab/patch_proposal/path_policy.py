from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime_lab.patch_proposal.errors import PatchProposalPolicyError


DEFAULT_DENIED_PATH_PATTERNS = (
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


def _as_root(workspace_root: Any) -> Path:
    if workspace_root is None:
        raise PatchProposalPolicyError("WORKSPACE_ROOT_MISSING")
    root = Path(workspace_root).expanduser()
    if not str(root):
        raise PatchProposalPolicyError("WORKSPACE_ROOT_MISSING")
    return root.resolve()


def _is_network_path(raw_path: str) -> bool:
    return raw_path.lower().startswith(("http://", "https://", "ssh://", "git://"))


def _denied_path_patterns(policy: Any) -> tuple[str, ...]:
    if policy is None:
        return DEFAULT_DENIED_PATH_PATTERNS
    return tuple(getattr(policy, "denied_path_patterns", DEFAULT_DENIED_PATH_PATTERNS))


def _has_denied_pattern(relative_path: str, policy: Any) -> bool:
    parts = Path(relative_path).parts
    lowered = relative_path.lower()
    for pattern in _denied_path_patterns(policy):
        pattern_lower = pattern.lower()
        if pattern_lower in {part.lower() for part in parts}:
            return True
        if pattern_lower in lowered:
            return True
    return False


def resolve_patch_target_path(
    *,
    workspace_root: Any,
    target_path: str,
    policy: Any = None,
) -> Path:
    if _is_network_path(target_path):
        raise PatchProposalPolicyError("NETWORK_URL_REJECTED")
    candidate = Path(target_path)
    if candidate.is_absolute():
        raise PatchProposalPolicyError("ABSOLUTE_PATH_REJECTED")

    root = _as_root(workspace_root)
    lexical = root / candidate
    relative_lexical = lexical.relative_to(root).as_posix()
    if relative_lexical.startswith("../") or relative_lexical == ".." or "/../" in f"/{relative_lexical}/":
        raise PatchProposalPolicyError("PATH_TRAVERSAL_REJECTED")
    if _has_denied_pattern(relative_lexical, policy):
        raise PatchProposalPolicyError("DENIED_PATH_PATTERN")

    resolved = lexical.resolve(strict=False)
    try:
        relative_resolved = resolved.relative_to(root).as_posix()
    except ValueError as exc:
        code = "SYMLINK_ESCAPE_REJECTED" if lexical.exists() else "PATH_TRAVERSAL_REJECTED"
        raise PatchProposalPolicyError(code) from exc
    if lexical.exists() and resolved != lexical.absolute() and not str(resolved).startswith(str(root)):
        raise PatchProposalPolicyError("SYMLINK_ESCAPE_REJECTED")
    if _has_denied_pattern(relative_resolved, policy):
        raise PatchProposalPolicyError("DENIED_PATH_PATTERN")
    return resolved
