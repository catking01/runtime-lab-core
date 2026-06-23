"""Admission-layer errors and error codes for deterministic descriptor gates."""

from __future__ import annotations


class AdmissionError(Exception):
    """Base error type for admission failures."""

    code: str
    detail: str | None

    def __init__(self, code: str, detail: str | None = None):
        message = code if detail is None else f"{code}: {detail}"
        super().__init__(message)
        self.code = code
        self.detail = detail


class AdmissionDeserializationError(AdmissionError):
    """Raised when admission input is not a descriptor mapping."""


class AdmissionValidationError(AdmissionError):
    """Raised when policy-level admission checks reject a valid descriptor."""


ADMISSION_DESERIALIZATION_ERROR = "ADMISSION_DESERIALIZATION_ERROR"
ADMISSION_VALIDATION_ERROR = "ADMISSION_VALIDATION_ERROR"
ADMISSION_DESCRIPTOR_VALIDATION_ERROR = "ADMISSION_DESCRIPTOR_VALIDATION_ERROR"
