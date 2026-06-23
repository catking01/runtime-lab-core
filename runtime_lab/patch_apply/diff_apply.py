from __future__ import annotations

import re

from runtime_lab.patch_apply.errors import PatchApplyPolicyError
from runtime_lab.patch_apply.models import DiffHunk, DiffLine, FilePatch


HUNK_RE = re.compile(r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? \+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@")


def _strip_diff_path(raw_path: str) -> str:
    path = raw_path.strip().split("\t", 1)[0]
    if path == "/dev/null":
        return path
    if path.startswith(("a/", "b/")):
        return path[2:]
    return path


def _scan_unsupported(lines: list[str]) -> None:
    for line in lines:
        lowered = line.lower()
        if line.startswith("Binary files ") or line.startswith("GIT binary patch"):
            raise PatchApplyPolicyError("BINARY_PATCH_REJECTED")
        if line.startswith("new file mode"):
            raise PatchApplyPolicyError("NEW_FILE_REJECTED")
        if line.startswith("deleted file mode"):
            raise PatchApplyPolicyError("DELETE_FILE_REJECTED")
        if line.startswith(("old mode ", "new mode ")):
            raise PatchApplyPolicyError("MODE_CHANGE_REJECTED")
        if line.startswith(("rename from ", "rename to ", "copy from ", "copy to ")):
            raise PatchApplyPolicyError("RENAME_OR_COPY_REJECTED")
        if "git apply" in lowered or " patch " in f" {lowered} ":
            raise PatchApplyPolicyError("SHELL_EXECUTION_REQUEST_REJECTED")


def _parse_hunk_header(header: str) -> tuple[int, int, int, int]:
    match = HUNK_RE.match(header)
    if match is None:
        raise PatchApplyPolicyError("MALFORMED_UNIFIED_DIFF")
    old_start = int(match.group("old_start"))
    old_count = int(match.group("old_count") or "1")
    new_start = int(match.group("new_start"))
    new_count = int(match.group("new_count") or "1")
    return old_start, old_count, new_start, new_count


def parse_unified_diff(diff_text: str) -> list[FilePatch]:
    if not isinstance(diff_text, str) or not diff_text.strip():
        raise PatchApplyPolicyError("MALFORMED_UNIFIED_DIFF")

    lines = diff_text.splitlines()
    _scan_unsupported(lines)
    patches: list[FilePatch] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        if line.startswith(("diff --git ", "index ")):
            index += 1
            continue
        if not line.startswith("--- "):
            index += 1
            continue
        if index + 1 >= len(lines) or not lines[index + 1].startswith("+++ "):
            raise PatchApplyPolicyError("MALFORMED_UNIFIED_DIFF")

        old_path = _strip_diff_path(line[4:])
        new_path = _strip_diff_path(lines[index + 1][4:])
        if old_path == "/dev/null":
            raise PatchApplyPolicyError("NEW_FILE_REJECTED")
        if new_path == "/dev/null":
            raise PatchApplyPolicyError("DELETE_FILE_REJECTED")
        if old_path != new_path:
            raise PatchApplyPolicyError("TARGET_PATH_MISMATCH")
        index += 2

        hunks: list[DiffHunk] = []
        while index < len(lines):
            current = lines[index]
            if current.startswith("--- "):
                break
            if current.startswith(("diff --git ", "index ")):
                index += 1
                continue
            if not current.startswith("@@ "):
                raise PatchApplyPolicyError("MALFORMED_UNIFIED_DIFF")
            old_start, old_count, new_start, new_count = _parse_hunk_header(current)
            index += 1

            hunk_lines: list[DiffLine] = []
            while index < len(lines):
                hunk_line = lines[index]
                if hunk_line.startswith("@@ ") or hunk_line.startswith("--- "):
                    break
                if hunk_line.startswith("\\"):
                    index += 1
                    continue
                if not hunk_line or hunk_line[0] not in {" ", "-", "+"}:
                    raise PatchApplyPolicyError("MALFORMED_UNIFIED_DIFF")
                hunk_lines.append(DiffLine(kind=hunk_line[0], text=hunk_line[1:]))
                index += 1
            if not hunk_lines:
                raise PatchApplyPolicyError("MALFORMED_UNIFIED_DIFF")
            hunks.append(
                DiffHunk(
                    old_start=old_start,
                    old_count=old_count,
                    new_start=new_start,
                    new_count=new_count,
                    lines=tuple(hunk_lines),
                )
            )

        if not hunks:
            raise PatchApplyPolicyError("MALFORMED_UNIFIED_DIFF")
        patches.append(FilePatch(target_path=new_path, hunks=tuple(hunks)))

    if not patches:
        raise PatchApplyPolicyError("MALFORMED_UNIFIED_DIFF")
    return patches


def apply_file_patch_to_text(original_text: str, file_patch: FilePatch) -> str:
    original_lines = original_text.splitlines(keepends=True)
    output: list[str] = []
    cursor = 0

    for hunk in file_patch.hunks:
        old_index = hunk.old_start - 1
        if old_index < cursor or old_index > len(original_lines):
            raise PatchApplyPolicyError("HUNK_CONTEXT_MISMATCH")
        output.extend(original_lines[cursor:old_index])
        position = old_index

        for diff_line in hunk.lines:
            expected = f"{diff_line.text}\n"
            if diff_line.kind == " ":
                if position >= len(original_lines) or original_lines[position] != expected:
                    raise PatchApplyPolicyError("HUNK_CONTEXT_MISMATCH")
                output.append(original_lines[position])
                position += 1
            elif diff_line.kind == "-":
                if position >= len(original_lines) or original_lines[position] != expected:
                    raise PatchApplyPolicyError("HUNK_CONTEXT_MISMATCH")
                position += 1
            elif diff_line.kind == "+":
                output.append(expected)
        cursor = position

    output.extend(original_lines[cursor:])
    return "".join(output)


def apply_unified_diff_to_text(original_text: str, *, target_path: str, diff_text: str) -> str:
    patches = parse_unified_diff(diff_text)
    matches = [patch for patch in patches if patch.target_path == target_path]
    if len(matches) != 1:
        raise PatchApplyPolicyError("TARGET_PATH_MISMATCH")
    return apply_file_patch_to_text(original_text, matches[0])
