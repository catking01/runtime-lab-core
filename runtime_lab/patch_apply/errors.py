from __future__ import annotations


class PatchApplyPolicyError(ValueError):
    def __init__(self, code: str, message: str | None = None):
        super().__init__(message or code)
        self.code = code
        self.apply_performed = False
        self.workspace_mutation_performed = False
