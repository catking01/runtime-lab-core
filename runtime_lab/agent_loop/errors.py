from __future__ import annotations


class AgentLoopPolicyError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code
