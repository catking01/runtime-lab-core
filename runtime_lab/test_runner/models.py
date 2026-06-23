from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping


DEFAULT_ALLOWED_ENV_KEYS = (
    "PATH",
    "PYTHONPATH",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
    "CONDA_PREFIX",
    "VIRTUAL_ENV",
    "HOME",
    "LANG",
    "LC_ALL",
)

DEFAULT_REDACTED_ENV_KEYS = (
    "DEEPSEEK_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "Authorization",
    "AUTHORIZATION",
    "Bearer",
)


@dataclass(frozen=True)
class TestRunnerPolicy:
    __test__ = False

    shell_allowed: bool = False
    network_allowed: bool = False
    llm_invocation_allowed: bool = False
    allow_live_deepseek: bool = False
    model_driven_executor_dispatch_allowed: bool = False
    timeout_seconds: int = 120
    max_stdout_bytes: int = 200_000
    max_stderr_bytes: int = 200_000
    max_total_output_bytes: int = 400_000
    allowed_env_keys: tuple[str, ...] = DEFAULT_ALLOWED_ENV_KEYS
    redacted_env_keys: tuple[str, ...] = DEFAULT_REDACTED_ENV_KEYS
    receipt_required: bool = True
    ledger_event_required: bool = True
    default_decision: str = "REJECT_FAIL_CLOSED"


@dataclass(frozen=True)
class TestCommandSpec:
    __test__ = False

    command_id: str
    argv: tuple[str, ...]
    cwd_relative: str = "."
    timeout_seconds: int = 120
    max_stdout_bytes: int = 200_000
    max_stderr_bytes: int = 200_000
    max_total_output_bytes: int = 400_000
    allowed_env_keys: tuple[str, ...] = DEFAULT_ALLOWED_ENV_KEYS
    redacted_env_keys: tuple[str, ...] = DEFAULT_REDACTED_ENV_KEYS
    receipt_required: bool = True
    ledger_event_required: bool = True
    shell_allowed: bool = False
    network_allowed: bool = False
    llm_invocation_allowed: bool = False
    allow_live_deepseek: bool = False
    model_driven_executor_dispatch_allowed: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "argv", tuple(str(part) for part in self.argv))
        object.__setattr__(self, "allowed_env_keys", tuple(str(key) for key in self.allowed_env_keys))
        object.__setattr__(self, "redacted_env_keys", tuple(str(key) for key in self.redacted_env_keys))


@dataclass(frozen=True)
class TestRunRequest:
    __test__ = False

    command_id: str
    workspace_root: Path
    cwd_relative: str
    timeout_seconds: int | None
    max_stdout_bytes: int | None
    max_stderr_bytes: int | None
    max_total_output_bytes: int | None
    allowed_env_keys: tuple[str, ...] = DEFAULT_ALLOWED_ENV_KEYS
    redacted_env_keys: tuple[str, ...] = DEFAULT_REDACTED_ENV_KEYS
    env: Mapping[str, str] = field(default_factory=dict)
    raw_command: str | None = None
    argv: tuple[str, ...] | None = None
    shell: bool = False
    network_allowed: bool = False
    llm_invocation_requested: bool = False
    model_driven_executor_dispatch_requested: bool = False
    allow_live_deepseek: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "workspace_root", Path(self.workspace_root))
        object.__setattr__(self, "allowed_env_keys", tuple(str(key) for key in self.allowed_env_keys))
        object.__setattr__(self, "redacted_env_keys", tuple(str(key) for key in self.redacted_env_keys))
        if self.argv is not None:
            object.__setattr__(self, "argv", tuple(str(part) for part in self.argv))
        object.__setattr__(self, "env", {str(key): str(value) for key, value in dict(self.env).items()})


@dataclass(frozen=True)
class CompletedTestProcess:
    exit_code: int
    stdout: bytes = b""
    stderr: bytes = b""
