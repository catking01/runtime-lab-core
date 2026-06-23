from __future__ import annotations

import json
from pathlib import Path

from runtime_lab.patch_apply.rollback import build_rollback_artifact, restore_rollback_artifact
from runtime_lab.patch_apply.receipts import verify_rollback_artifact

from .conftest import make_workspace


def test_rollback_artifact_restores_recorded_preimages(tmp_path: Path):
    workspace = make_workspace(tmp_path)
    target = workspace / "docs" / "example.md"
    artifact = build_rollback_artifact(
        transaction_id="R126-TX-001",
        workspace_root=workspace,
        target_files=["docs/example.md"],
    )
    target.write_text("new\n", encoding="utf-8")

    restore_rollback_artifact(artifact, workspace_root=workspace)

    assert target.read_text(encoding="utf-8") == "old\n"
    assert verify_rollback_artifact(artifact) is True
    assert json.loads(json.dumps(artifact))["rollback_artifact_hash"].startswith("sha256:")
