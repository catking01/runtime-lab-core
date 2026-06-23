from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime_lab.repo_context.errors import RepoContextPolicyError
from runtime_lab.repo_context.models import ResolvedRepoPath
from runtime_lab.repo_context.policy import RepoContextPolicy


def _as_root(workspace_root: Any) -> Path:
    if workspace_root is None:
        raise RepoContextPolicyError("WORKSPACE_ROOT_MISSING")
    root = Path(workspace_root).expanduser()
    if not str(root):
        raise RepoContextPolicyError("WORKSPACE_ROOT_MISSING")
    return root.resolve()


def _is_network_path(raw_path: str) -> bool:
    lowered = raw_path.lower()
    return lowered.startswith(("http://", "https://", "ssh://", "git://"))


def _relative_to(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _has_denied_pattern(relative_path: str, policy: RepoContextPolicy) -> bool:
    parts = Path(relative_path).parts
    lowered = relative_path.lower()
    for pattern in policy.denied_path_patterns:
        pattern_lower = pattern.lower()
        if pattern_lower in {part.lower() for part in parts}:
            return True
        if pattern_lower in lowered:
            return True
    return False


def _has_hidden_part(relative_path: str) -> bool:
    return any(part.startswith(".") for part in Path(relative_path).parts)


def resolve_workspace_path(
    *,
    workspace_root: Any,
    requested_path: str,
    policy: RepoContextPolicy | None = None,
) -> ResolvedRepoPath:
    policy = policy or RepoContextPolicy()
    if _is_network_path(requested_path):
        raise RepoContextPolicyError("NETWORK_URL_REJECTED")

    candidate = Path(requested_path)
    if candidate.is_absolute():
        raise RepoContextPolicyError("ABSOLUTE_PATH_REJECTED")

    root = _as_root(workspace_root)
    lexical = root / candidate
    relative_lexical = lexical.relative_to(root).as_posix()
    if relative_lexical == ".":
        relative_lexical = ""
    if relative_lexical.startswith("../") or relative_lexical == ".." or "/../" in f"/{relative_lexical}/":
        raise RepoContextPolicyError("PATH_TRAVERSAL_REJECTED")

    if _has_denied_pattern(relative_lexical, policy):
        raise RepoContextPolicyError("DENIED_PATH_PATTERN")
    if not policy.include_hidden and _has_hidden_part(relative_lexical):
        raise RepoContextPolicyError("HIDDEN_PATH_REJECTED")

    resolved = lexical.resolve(strict=False)
    try:
        relative_resolved = _relative_to(resolved, root)
    except ValueError as exc:
        code = "SYMLINK_ESCAPE_REJECTED" if lexical.exists() else "PATH_TRAVERSAL_REJECTED"
        raise RepoContextPolicyError(code) from exc

    if not policy.allow_symlink_escape and lexical.exists() and resolved != lexical.absolute() and not str(resolved).startswith(str(root)):
        raise RepoContextPolicyError("SYMLINK_ESCAPE_REJECTED")
    if _has_denied_pattern(relative_resolved, policy):
        raise RepoContextPolicyError("DENIED_PATH_PATTERN")
    if not policy.include_hidden and _has_hidden_part(relative_resolved):
        raise RepoContextPolicyError("HIDDEN_PATH_REJECTED")

    return ResolvedRepoPath(path=resolved, relative_path=relative_resolved, path_allowed=True)
