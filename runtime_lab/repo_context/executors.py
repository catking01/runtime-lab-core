"""Read-only repository context executors for R124.

The module exposes bounded file listing, file reading, and regex search. Each
executor returns receipt and ledger metadata while preserving the no-shell,
no-network, no-LLM, and no-workspace-mutation boundary.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from runtime_lab.repo_context.errors import RepoContextPolicyError
from runtime_lab.repo_context.models import RepoContextAuthority
from runtime_lab.repo_context.path_policy import resolve_workspace_path
from runtime_lab.repo_context.policy import RepoContextPolicy
from runtime_lab.repo_context.receipts import build_repo_context_receipt, canonical_hash, sha256_text


EXECUTORS = ("list_files", "read_file", "grep")
SECRET_LIKE_RE = re.compile(r"(sk-[A-Za-z0-9_-]{20,}|gho_[A-Za-z0-9_]{20,}|Authorization:\s*Bearer\s+\S+)")
SHELL_PATTERN_RE = re.compile(r"(;|&&|\$\(|`|\|)")


def _base_result(executor_id: str) -> dict[str, Any]:
    return {
        "executor_id": executor_id,
        "read_only": True,
        "transport_started": False,
        "workspace_mutation_started": False,
        "shell_execution_started": False,
        "network_execution_started": False,
        "llm_invocation_started": False,
        "model_driven_executor_dispatch_started": False,
    }


def _ledger_event(executor_id: str, receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_type": f"repo_context.{executor_id}",
        "receipt_hash": receipt["receipt_hash"],
        "read_only": True,
    }


def _reject(
    *,
    executor_id: str,
    workspace_root: Any,
    requested_path: str | None,
    code: str,
    resolved_path_relative: str | None = None,
) -> dict[str, Any]:
    receipt = build_repo_context_receipt(
        executor_id=executor_id,
        workspace_root=str(workspace_root or ""),
        requested_path=requested_path,
        resolved_path_relative=resolved_path_relative,
        path_allowed=False,
        result="REJECT_FAIL_CLOSED",
        rejection_codes=[code],
    )
    result = _base_result(executor_id)
    result.update(
        {
            "accepted": False,
            "rejection_codes": [code],
            "receipt": receipt,
            "ledger_event": _ledger_event(executor_id, receipt),
        }
    )
    return result


def _validate_policy_contract(executor_id: str, workspace_root: Any, policy: RepoContextPolicy) -> dict[str, Any] | None:
    if not policy.receipt_required:
        return _reject(executor_id=executor_id, workspace_root=workspace_root, requested_path=None, code="RECEIPT_CONTRACT_REQUIRED")
    if not policy.ledger_event_required:
        return _reject(executor_id=executor_id, workspace_root=workspace_root, requested_path=None, code="LEDGER_EVENT_REQUIRED")
    return None


def _validate_authority(
    *,
    executor_id: str,
    workspace_root: Any,
    authority: RepoContextAuthority | None,
) -> dict[str, Any] | None:
    if authority is None:
        return _reject(executor_id=executor_id, workspace_root=workspace_root, requested_path=None, code="AUTHORITY_MISSING")
    if not authority.allows(executor_id):
        return _reject(executor_id=executor_id, workspace_root=workspace_root, requested_path=None, code="EXECUTOR_NOT_AUTHORIZED")
    return None


def _is_binary(data: bytes) -> bool:
    return b"\x00" in data


def _read_text_file(path: Path, *, max_size: int, allow_binary: bool) -> tuple[str, bytes]:
    if not path.exists() or not path.is_file():
        raise RepoContextPolicyError("FILE_NOT_FOUND")
    size = path.stat().st_size
    if size > max_size:
        raise RepoContextPolicyError("FILE_TOO_LARGE")
    data = path.read_bytes()
    if not allow_binary and _is_binary(data):
        raise RepoContextPolicyError("BINARY_FILE_REJECTED")
    return data.decode("utf-8", errors="replace"), data


def _redact(value: str, enabled: bool) -> tuple[str, bool]:
    if not enabled:
        return value, False
    redacted = SECRET_LIKE_RE.sub("<REDACTED_SECRET_LIKE_VALUE>", value)
    return redacted, redacted != value


def _iter_candidate_files(root: Path, policy: RepoContextPolicy):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError:
            continue
        if not policy.include_hidden and any(part.startswith(".") for part in Path(relative).parts):
            continue
        try:
            resolve_workspace_path(workspace_root=root, requested_path=relative, policy=policy)
        except RepoContextPolicyError:
            continue
        yield path, relative


def _grep_candidate_files(root: Path, workspace_root: Path, policy: RepoContextPolicy) -> tuple[list[tuple[Path, str]], int]:
    candidates: list[tuple[Path, str]] = []
    skipped = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        try:
            relative = path.relative_to(workspace_root).as_posix()
        except ValueError:
            skipped += 1
            continue
        if not policy.include_hidden and any(part.startswith(".") for part in Path(relative).parts):
            skipped += 1
            continue
        try:
            resolve_workspace_path(workspace_root=workspace_root, requested_path=relative, policy=policy)
        except RepoContextPolicyError:
            skipped += 1
            continue
        candidates.append((path, relative))
    return candidates, skipped


def list_files(
    *,
    workspace_root: Any,
    authority: RepoContextAuthority | None,
    policy: RepoContextPolicy | None = None,
) -> dict[str, Any]:
    """List policy-allowed files in a workspace without reading file contents."""

    executor_id = "list_files"
    policy = policy or RepoContextPolicy()
    for rejection in (_validate_policy_contract(executor_id, workspace_root, policy), _validate_authority(executor_id=executor_id, workspace_root=workspace_root, authority=authority)):
        if rejection is not None:
            return rejection
    try:
        root = resolve_workspace_path(workspace_root=workspace_root, requested_path="", policy=RepoContextPolicy(include_hidden=True)).path
    except RepoContextPolicyError as exc:
        return _reject(executor_id=executor_id, workspace_root=workspace_root, requested_path=None, code=exc.code)

    files = []
    truncated = False
    for _path, relative in _iter_candidate_files(Path(root), policy):
        if len(files) >= policy.max_files_returned:
            truncated = True
            break
        files.append(relative)

    receipt = build_repo_context_receipt(
        executor_id=executor_id,
        workspace_root=str(root),
        requested_path=None,
        resolved_path_relative=None,
        path_allowed=True,
        bytes_read=0,
        content_hash=canonical_hash(files),
        result="SUCCESS_TRUNCATED" if truncated else "SUCCESS",
    )
    result = _base_result(executor_id)
    result.update(
        {
            "accepted": True,
            "files": files,
            "truncated": truncated,
            "receipt": receipt,
            "ledger_event": _ledger_event(executor_id, receipt),
        }
    )
    return result


def read_file(
    *,
    workspace_root: Any,
    requested_path: str,
    authority: RepoContextAuthority | None,
    policy: RepoContextPolicy | None = None,
    write_intent: bool = False,
) -> dict[str, Any]:
    """Read one policy-allowed text file and redact configured secret patterns."""

    executor_id = "read_file"
    policy = policy or RepoContextPolicy()
    if write_intent:
        return _reject(executor_id=executor_id, workspace_root=workspace_root, requested_path=requested_path, code="WRITE_INTENT_REJECTED")
    for rejection in (_validate_policy_contract(executor_id, workspace_root, policy), _validate_authority(executor_id=executor_id, workspace_root=workspace_root, authority=authority)):
        if rejection is not None:
            return rejection
    try:
        resolved = resolve_workspace_path(workspace_root=workspace_root, requested_path=requested_path, policy=policy)
        content, raw = _read_text_file(
            Path(resolved.path),
            max_size=policy.max_file_size_bytes,
            allow_binary=policy.allow_binary_files,
        )
    except RepoContextPolicyError as exc:
        return _reject(executor_id=executor_id, workspace_root=workspace_root, requested_path=requested_path, code=exc.code)

    content, redaction_applied = _redact(content, policy.redact_secret_like_patterns)
    receipt = build_repo_context_receipt(
        executor_id=executor_id,
        workspace_root=str(Path(workspace_root).resolve()),
        requested_path=requested_path,
        resolved_path_relative=resolved.relative_path,
        path_allowed=True,
        bytes_read=len(raw),
        content_hash=sha256_text(raw.decode("utf-8", errors="replace")),
        redaction_applied=redaction_applied,
        result="SUCCESS",
    )
    result = _base_result(executor_id)
    result.update(
        {
            "accepted": True,
            "content": content,
            "receipt": receipt,
            "ledger_event": _ledger_event(executor_id, receipt),
        }
    )
    return result


def grep(
    *,
    workspace_root: Any,
    pattern: str,
    authority: RepoContextAuthority | None,
    policy: RepoContextPolicy | None = None,
    requested_path: str | None = None,
) -> dict[str, Any]:
    """Search policy-allowed files with Python regex matching only."""

    executor_id = "grep"
    policy = policy or RepoContextPolicy()
    if SHELL_PATTERN_RE.search(pattern):
        return _reject(executor_id=executor_id, workspace_root=workspace_root, requested_path=requested_path, code="SHELL_PATTERN_REJECTED")
    for rejection in (_validate_policy_contract(executor_id, workspace_root, policy), _validate_authority(executor_id=executor_id, workspace_root=workspace_root, authority=authority)):
        if rejection is not None:
            return rejection
    try:
        root_resolved = resolve_workspace_path(workspace_root=workspace_root, requested_path=requested_path or "", policy=RepoContextPolicy(include_hidden=True))
    except RepoContextPolicyError as exc:
        return _reject(executor_id=executor_id, workspace_root=workspace_root, requested_path=requested_path, code=exc.code)

    root = Path(workspace_root).resolve()
    start = Path(root_resolved.path)
    if start.is_file():
        candidates = [(start, root_resolved.relative_path)]
        skipped_count = 0
    else:
        candidates, skipped_count = _grep_candidate_files(start, root, policy)
    try:
        compiled = re.compile(pattern)
    except re.error:
        return _reject(executor_id=executor_id, workspace_root=workspace_root, requested_path=requested_path, code="INVALID_GREP_PATTERN")
    matches: list[dict[str, Any]] = []
    truncated = False

    for path, _relative in candidates:
        try:
            relative = path.relative_to(root).as_posix()
            text, _raw = _read_text_file(
                path,
                max_size=policy.max_grep_file_size_bytes,
                allow_binary=policy.allow_binary_files,
            )
        except Exception:
            skipped_count += 1
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if compiled.search(line):
                redacted_line, _redacted = _redact(line, policy.redact_secret_like_patterns)
                matches.append({"path": relative, "line_number": line_number, "line": redacted_line})
                if len(matches) >= policy.max_grep_matches:
                    truncated = True
                    break
        if truncated:
            break

    receipt = build_repo_context_receipt(
        executor_id=executor_id,
        workspace_root=str(root),
        requested_path=requested_path,
        resolved_path_relative=root_resolved.relative_path,
        path_allowed=True,
        bytes_read=0,
        content_hash=canonical_hash(matches),
        result="SUCCESS_TRUNCATED" if truncated else "SUCCESS",
    )
    result = _base_result(executor_id)
    result.update(
        {
            "accepted": True,
            "matches": matches,
            "skipped_count": skipped_count,
            "truncated": truncated,
            "receipt": receipt,
            "ledger_event": _ledger_event(executor_id, receipt),
        }
    )
    return result


def execute_repo_context(
    *,
    executor_id: str,
    workspace_root: Any,
    authority: RepoContextAuthority | None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Dispatch a named read-only repo-context executor from the fixed allowlist."""

    if executor_id not in EXECUTORS:
        return _reject(executor_id=executor_id, workspace_root=workspace_root, requested_path=None, code="UNKNOWN_EXECUTOR_ID")
    if executor_id == "list_files":
        return list_files(workspace_root=workspace_root, authority=authority, policy=kwargs.get("policy"))
    if executor_id == "read_file":
        return read_file(
            workspace_root=workspace_root,
            requested_path=kwargs["requested_path"],
            authority=authority,
            policy=kwargs.get("policy"),
            write_intent=kwargs.get("write_intent", False),
        )
    return grep(
        workspace_root=workspace_root,
        pattern=kwargs["pattern"],
        authority=authority,
        policy=kwargs.get("policy"),
        requested_path=kwargs.get("requested_path"),
    )
