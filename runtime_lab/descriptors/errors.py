from __future__ import annotations


class DescriptorValidationError(Exception):
    """Raised when a Stage B1 descriptor fails fail-closed validation."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code
