from __future__ import annotations

import pytest

from runtime_lab.patch_proposal.diff_parser import parse_unified_diff
from runtime_lab.patch_proposal.errors import PatchProposalPolicyError


def test_parse_valid_text_only_unified_diff():
    parsed = parse_unified_diff(
        "--- a/docs/example.md\n"
        "+++ b/docs/example.md\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "+new\n"
    )

    assert parsed.target_files == ("docs/example.md",)
    assert parsed.binary_patch_detected is False
    assert parsed.mode_change_detected is False
    assert parsed.rename_or_copy_detected is False
    assert parsed.delete_detected is False


@pytest.mark.parametrize(
    ("diff_text", "code"),
    [
        ("Binary files a/a.bin and b/a.bin differ\n", "BINARY_PATCH_REJECTED"),
        ("GIT binary patch\nliteral 0\n", "BINARY_PATCH_REJECTED"),
        ("old mode 100644\nnew mode 100755\n", "MODE_CHANGE_REJECTED"),
        ("rename from a.txt\nrename to b.txt\n", "RENAME_OR_COPY_REJECTED"),
        ("copy from a.txt\ncopy to b.txt\n", "RENAME_OR_COPY_REJECTED"),
        ("--- a/a.txt\n+++ /dev/null\n@@ -1 +0,0 @@\n-old\n", "DELETE_FILE_REJECTED"),
        ("--- /dev/null\n+++ b/a.txt\n@@ -0,0 +1 @@\n+new\n", "NEW_FILE_REJECTED"),
        ("--- a/a.txt\n@@ -1 +1 @@\n-old\n+new\n", "MALFORMED_UNIFIED_DIFF"),
        ("--- a/a.txt\n+++ b/b.txt\n@@ -1 +1 @@\n-old\n+new\n", "TARGET_PATH_MISMATCH"),
    ],
)
def test_parse_rejects_unsupported_diff_features(diff_text: str, code: str):
    with pytest.raises(PatchProposalPolicyError) as exc:
        parse_unified_diff(diff_text)

    assert exc.value.code == code
