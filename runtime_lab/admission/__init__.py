"""Admission-controller package for descriptor intake validation."""

from .controller import admit_descriptor_payload, evaluate_admission, evaluate_authorized_admission
from .errors import (
    ADMISSION_DESERIALIZATION_ERROR,
    ADMISSION_VALIDATION_ERROR,
    ADMISSION_DESCRIPTOR_VALIDATION_ERROR,
)
from .result import AdmissionReceipt, verify_admission_receipt

__all__ = [
    "ADMISSION_DESERIALIZATION_ERROR",
    "ADMISSION_VALIDATION_ERROR",
    "ADMISSION_DESCRIPTOR_VALIDATION_ERROR",
    "AdmissionReceipt",
    "admit_descriptor_payload",
    "evaluate_admission",
    "evaluate_authorized_admission",
    "verify_admission_receipt",
]
