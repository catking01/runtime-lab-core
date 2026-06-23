from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PatchProposalRequest:
    proposal_id: str
    base_commit: str
    target_files: tuple[str, ...]
    unified_diff: str
    risk_class: str
    change_summary: str
    validation_plan: tuple[str, ...]
    rollback_plan: str
    human_approval_required: bool = True
    apply_allowed: bool = False
    apply_performed: bool = False
    workspace_mutation_performed: bool = False
    test_execution_allowed: bool = False
    test_execution_performed: bool = False


@dataclass(frozen=True)
class ParsedUnifiedDiff:
    target_files: tuple[str, ...]
    binary_patch_detected: bool = False
    mode_change_detected: bool = False
    rename_or_copy_detected: bool = False
    delete_detected: bool = False
