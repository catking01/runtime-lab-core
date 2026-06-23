from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class AgentLoopMode(str, Enum):
    DRY_RUN = "DRY_RUN"
    SUPERVISED_APPLY = "SUPERVISED_APPLY"


def _default_non_claims() -> dict[str, bool]:
    return {
        "autonomous_agent": False,
        "general_coding_agent": False,
        "codex_equivalent": False,
        "claude_code_equivalent": False,
        "autonomous_operation": False,
        "arbitrary_shell": False,
        "arbitrary_command_execution": False,
        "network_execution": False,
        "live_llm_provider": False,
        "model_driven_executor_dispatch": False,
        "codex_equivalence": False,
        "claude_code_equivalence": False,
        "remote_sealed_pass": False,
        "production_readiness": False,
        "team_or_org_runtime": False,
    }


@dataclass(frozen=True)
class AgentLoopPolicy:
    max_iterations: int = 3
    max_context_reads: int = 20
    max_patch_proposals: int = 1
    max_patch_apply_transactions: int = 1
    max_test_runs: int = 2
    allow_live_llm_provider: bool = False
    allow_patch_apply: bool = True
    allow_test_runner: bool = True
    require_human_approval_for_apply: bool = True
    require_receipts: bool = True
    require_ledger_events: bool = True
    require_replay_bundle: bool = True
    require_final_report: bool = True
    default_decision: str = "REJECT_FAIL_CLOSED"
    non_claims: dict[str, bool] = field(default_factory=_default_non_claims)


@dataclass(frozen=True)
class AgentLoopAuthority:
    task_id: str
    actor_id: str
    allowed_modes: tuple[AgentLoopMode, ...] = (AgentLoopMode.DRY_RUN, AgentLoopMode.SUPERVISED_APPLY)
    supervision_required: bool = True
    allow_autonomous_mode: bool = False
    allow_model_driven_executor_dispatch: bool = False
    allow_patch_apply: bool = True
    allow_test_runner: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "allowed_modes", tuple(AgentLoopMode(mode) for mode in self.allowed_modes))

    def allows_mode(self, mode: AgentLoopMode | str) -> bool:
        return AgentLoopMode(mode) in self.allowed_modes


@dataclass(frozen=True)
class AgentLoopRequest:
    task_id: str
    run_id: str
    mode: AgentLoopMode | str
    base_commit: str
    workspace_root: Path | str
    run_artifact_dir: Path | str
    task_text: str
    target_files: tuple[str, ...] = ()
    context_requests: tuple[dict[str, Any], ...] = ()
    patch_proposal_request: dict[str, Any] | None = None
    approval_packet: dict[str, Any] | None = None
    test_command_id: str | None = None
    test_runner_executor: Any = None
    planner_output: dict[str, Any] | None = None
    allow_live_llm_provider: bool = False
    requested_initial_state: str | None = None
    requested_transition: str | None = None
    requested_iterations: int = 1
    patch_proposal_count: int = 1
    patch_apply_transaction_count: int = 1
    test_run_count: int = 1
    workspace_mutation_requested: bool = False
    test_run_result: dict[str, Any] | None = None
    model_driven_executor_dispatch_requested: bool = False
    raw_command: str | None = None
    force_missing_receipt: bool = False
    force_missing_ledger: bool = False
    force_missing_replay_manifest: bool = False
    force_ledger_hash_mismatch: bool = False
    force_replay_hash_mismatch: bool = False
    force_rollback_required: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "mode", AgentLoopMode(self.mode))
        object.__setattr__(self, "workspace_root", Path(self.workspace_root))
        object.__setattr__(self, "run_artifact_dir", Path(self.run_artifact_dir))
        object.__setattr__(self, "target_files", tuple(str(path) for path in self.target_files))
        object.__setattr__(self, "context_requests", tuple(dict(request) for request in self.context_requests))
        object.__setattr__(self, "metadata", dict(self.metadata))
