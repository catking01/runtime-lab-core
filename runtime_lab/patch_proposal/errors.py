from __future__ import annotations


class PatchProposalPolicyError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code
        self.apply_performed = False
        self.workspace_mutation_performed = False
        self.test_execution_performed = False
