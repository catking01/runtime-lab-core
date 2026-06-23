from __future__ import annotations


class RepoContextPolicyError(Exception):
    """Fail-closed read-only repo context policy rejection."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code
        self.read_only = True
        self.workspace_mutation_started = False
        self.shell_execution_started = False
        self.network_execution_started = False
        self.llm_invocation_started = False
