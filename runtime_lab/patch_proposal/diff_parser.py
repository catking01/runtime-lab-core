from __future__ import annotations

from runtime_lab.patch_proposal.errors import PatchProposalPolicyError
from runtime_lab.patch_proposal.models import ParsedUnifiedDiff


def _strip_diff_path(raw_path: str) -> str:
    path = raw_path.strip().split("\t", 1)[0]
    if path == "/dev/null":
        return path
    if path.startswith(("a/", "b/")):
        return path[2:]
    return path


def parse_unified_diff(diff_text: str) -> ParsedUnifiedDiff:
    if not isinstance(diff_text, str) or not diff_text.strip():
        raise PatchProposalPolicyError("MALFORMED_UNIFIED_DIFF")

    lines = diff_text.splitlines()
    targets: list[str] = []
    index = 0
    saw_hunk = False

    for line in lines:
        lowered = line.lower()
        if line.startswith("Binary files ") or line.startswith("GIT binary patch"):
            raise PatchProposalPolicyError("BINARY_PATCH_REJECTED")
        if line.startswith("new file mode"):
            raise PatchProposalPolicyError("NEW_FILE_REJECTED")
        if line.startswith("deleted file mode"):
            raise PatchProposalPolicyError("DELETE_FILE_REJECTED")
        if line.startswith(("old mode ", "new mode ")):
            raise PatchProposalPolicyError("MODE_CHANGE_REJECTED")
        if line.startswith(("rename from ", "rename to ", "copy from ", "copy to ")):
            raise PatchProposalPolicyError("RENAME_OR_COPY_REJECTED")
        if "git apply" in lowered or " patch " in f" {lowered} ":
            raise PatchProposalPolicyError("SHELL_EXECUTION_REQUEST_REJECTED")

    while index < len(lines):
        line = lines[index]
        if line.startswith(("diff --git ", "index ")):
            index += 1
            continue
        if not line.startswith("--- "):
            index += 1
            continue
        if index + 1 >= len(lines) or not lines[index + 1].startswith("+++ "):
            raise PatchProposalPolicyError("MALFORMED_UNIFIED_DIFF")

        old_path = _strip_diff_path(line[4:])
        new_path = _strip_diff_path(lines[index + 1][4:])
        if old_path == "/dev/null":
            raise PatchProposalPolicyError("NEW_FILE_REJECTED")
        if new_path == "/dev/null":
            raise PatchProposalPolicyError("DELETE_FILE_REJECTED")
        if old_path != new_path:
            raise PatchProposalPolicyError("TARGET_PATH_MISMATCH")
        targets.append(new_path)
        index += 2

        file_has_hunk = False
        while index < len(lines):
            current = lines[index]
            if current.startswith("--- "):
                break
            if current.startswith("@@ "):
                file_has_hunk = True
                saw_hunk = True
            index += 1
        if not file_has_hunk:
            raise PatchProposalPolicyError("MALFORMED_UNIFIED_DIFF")

    if not targets or not saw_hunk:
        raise PatchProposalPolicyError("MALFORMED_UNIFIED_DIFF")
    return ParsedUnifiedDiff(target_files=tuple(dict.fromkeys(targets)))
