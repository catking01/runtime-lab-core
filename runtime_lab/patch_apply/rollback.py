from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime_lab.patch_apply.receipts import seal_rollback_artifact, sha256_bytes


def build_rollback_artifact(
    *,
    transaction_id: str,
    workspace_root: Any,
    target_files: list[str],
) -> dict[str, Any]:
    root = Path(workspace_root).expanduser().resolve()
    preimage_texts: dict[str, str] = {}
    preimage_hashes: dict[str, str] = {}
    for target in target_files:
        data = (root / target).read_bytes()
        preimage_texts[target] = data.decode("utf-8")
        preimage_hashes[target] = sha256_bytes(data)

    return seal_rollback_artifact(
        {
            "schema_version": "1.0",
            "artifact_type": "PATCH_APPLY_ROLLBACK_ARTIFACT",
            "milestone": "R126_HUMAN_APPROVED_PATCH_APPLY_TRANSACTION_LOCAL_VALIDATION",
            "transaction_id": transaction_id,
            "target_files": target_files,
            "preimage_hashes": preimage_hashes,
            "preimage_texts": preimage_texts,
        }
    )


def restore_rollback_artifact(artifact: dict[str, Any], *, workspace_root: Any) -> None:
    root = Path(workspace_root).expanduser().resolve()
    for target, text in artifact.get("preimage_texts", {}).items():
        path = root / target
        temp_path = path.with_name(f"{path.name}.rollback.tmp")
        temp_path.write_text(text, encoding="utf-8")
        temp_path.replace(path)
