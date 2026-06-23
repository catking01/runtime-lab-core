from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RepoContextAuthority:
    task_id: str
    allowed_executors: tuple[str, ...]

    def allows(self, executor_id: str) -> bool:
        return executor_id in self.allowed_executors


@dataclass(frozen=True)
class ResolvedRepoPath:
    path: Path
    relative_path: str
    path_allowed: bool = True
