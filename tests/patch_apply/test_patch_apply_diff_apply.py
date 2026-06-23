from __future__ import annotations

import pytest

from runtime_lab.patch_apply.diff_apply import apply_unified_diff_to_text, parse_unified_diff
from runtime_lab.patch_apply.errors import PatchApplyPolicyError


def test_apply_unified_diff_to_text_replaces_matching_old_lines():
    diff = (
        "--- a/docs/example.md\n"
        "+++ b/docs/example.md\n"
        "@@ -1,3 +1,3 @@\n"
        " one\n"
        "-old\n"
        "+new\n"
        " three\n"
    )

    patched = apply_unified_diff_to_text("one\nold\nthree\n", target_path="docs/example.md", diff_text=diff)

    assert patched == "one\nnew\nthree\n"


def test_parse_unified_diff_returns_ordered_file_patches():
    diff = (
        "--- a/docs/a.md\n+++ b/docs/a.md\n@@ -1 +1 @@\n-old a\n+new a\n"
        "--- a/docs/b.md\n+++ b/docs/b.md\n@@ -1 +1 @@\n-old b\n+new b\n"
    )

    parsed = parse_unified_diff(diff)

    assert [patch.target_path for patch in parsed] == ["docs/a.md", "docs/b.md"]


@pytest.mark.parametrize(
    ("diff_text", "code"),
    [
        ("Binary files a/a.bin and b/a.bin differ\n", "BINARY_PATCH_REJECTED"),
        ("old mode 100644\nnew mode 100755\n", "MODE_CHANGE_REJECTED"),
        ("rename from docs/a.md\nrename to docs/b.md\n", "RENAME_OR_COPY_REJECTED"),
        ("copy from docs/a.md\ncopy to docs/b.md\n", "RENAME_OR_COPY_REJECTED"),
        ("--- /dev/null\n+++ b/docs/new.md\n@@ -0,0 +1 @@\n+new\n", "NEW_FILE_REJECTED"),
        ("--- a/docs/example.md\n+++ /dev/null\n@@ -1 +0,0 @@\n-old\n", "DELETE_FILE_REJECTED"),
        ("--- a/docs/example.md\n@@ -1 +1 @@\n-old\n+new\n", "MALFORMED_UNIFIED_DIFF"),
    ],
)
def test_parse_unified_diff_rejects_unsupported_features(diff_text: str, code: str):
    with pytest.raises(PatchApplyPolicyError) as exc:
        parse_unified_diff(diff_text)

    assert exc.value.code == code


def test_apply_unified_diff_rejects_hunk_context_mismatch():
    diff = "--- a/docs/example.md\n+++ b/docs/example.md\n@@ -1 +1 @@\n-old\n+new\n"

    with pytest.raises(PatchApplyPolicyError) as exc:
        apply_unified_diff_to_text("different\n", target_path="docs/example.md", diff_text=diff)

    assert exc.value.code == "HUNK_CONTEXT_MISMATCH"
