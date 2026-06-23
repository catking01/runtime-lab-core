from __future__ import annotations


class TestRunnerPolicyError(ValueError):
    __test__ = False

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class TestRunnerTimeoutError(TimeoutError):
    __test__ = False

    pass
