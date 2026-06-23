from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime_lab.patch_apply.errors import PatchApplyPolicyError
from runtime_lab.patch_apply.models import PatchApplyPolicy


DEFAULT_DENIED_PATH_PATTERNS = PatchApplyPolicy().denied_path_patterns


def _as_root(workspace_root: Any) -> Path:
    if workspace_root is None:
        raise PatchApplyPolicyError("WORKSPACE_ROOT_MISSING")
    root = Path(workspace_root).expanduser()
    if not str(root):
        raise PatchApplyPolicyError("WORKSPACE_ROOT_MISSING")
    return root.resolve()


def _is_network_path(raw_path: str) -> bool:
    return raw_path.lower().startswith(("http://", "https://", "ssh://", "git://"))


def _denied_path_patterns(policy: PatchApplyPolicy | None) -> tuple[str, ...]:
    if policy is None:
        return DEFAULT_DENIED_PATH_PATTERNS
    return tuple(policy.denied_path_patterns)


def _has_denied_pattern(relative_path: str, policy: PatchApplyPolicy | None) -> bool:
    parts = Path(relative_path).parts
    lowered = relative_path.lower()
    for pattern in _denied_path_patterns(policy):
        pattern_lower = pattern.lower()
        if pattern_lower in {part.lower() for part in parts}:
            return True
        if pattern_lower in lowered:
            return True
    return False


def resolve_patch_apply_target_path(
    *,
    workspace_root: Any,
    target_path: str,
    policy: PatchApplyPolicy | None = None,
) -> Path:
    if not isinstance(target_path, str) or not target_path:
        raise PatchApplyPolicyError("TARGET_PATH_REQUIRED")
    if _is_network_path(target_path):
        raise PatchApplyPolicyError("NETWORK_URL_REJECTED")

    candidate = Path(target_path)
    if candidate.is_absolute():
        raise PatchApplyPolicyError("ABSOLUTE_PATH_REJECTED")

    root = _as_root(workspace_root)
    lexical = root / candidate
    relative_lexical = lexical.relative_to(root).as_posix()
    if relative_lexical.startswith("../") or relative_lexical == ".." or "/../" in f"/{relative_lexical}/":
        raise PatchApplyPolicyError("PATH_TRAVERSAL_REJECTED")
    if _has_denied_pattern(relative_lexical, policy):
        raise PatchApplyPolicyError("DENIED_PATH_PATTERN")
    if lexical.is_symlink():
        raise PatchApplyPolicyError("SYMLINK_TARGET_REJECTED")

    resolved = lexical.resolve(strict=False)
    try:
        relative_resolved = resolved.relative_to(root).as_posix()
    except ValueError as exc:
        raise PatchApplyPolicyError("PATH_TRAVERSAL_REJECTED") from exc
    if _has_denied_pattern(relative_resolved, policy):
        raise PatchApplyPolicyError("DENIED_PATH_PATTERN")
    return resolved
