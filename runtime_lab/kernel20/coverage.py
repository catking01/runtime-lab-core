"""Kernel20 coverage helpers for descriptor/runtime boundary assertions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


KERNEL20_PRIMITIVE_ORDER = (
    "Schema",
    "Task",
    "Identity",
    "Authority",
    "Actor Lifecycle",
    "State",
    "Transition",
    "Audit",
    "Clock",
    "Scheduler",
    "Handoff",
    "Tool",
    "LLM",
    "Executor",
    "Workspace",
    "Resource",
    "Security",
    "Artifact",
    "Validation",
    "Governance",
)

KERNEL20_PRIMITIVE_SET = frozenset(KERNEL20_PRIMITIVE_ORDER)

DESCRIPTOR_SPINE_BINDING_12 = frozenset(
    {
        "Task",
        "Identity",
        "Authority",
        "State",
        "Transition",
        "Audit",
        "Executor",
        "Workspace",
        "Artifact",
        "Validation",
        "Governance",
        "Replay",
    }
)

MINIMAL_KERNEL_BINDING_12 = DESCRIPTOR_SPINE_BINDING_12

MINIMAL_SPINE_KERNEL_RELEVANT_FIELDS = (
    "Task",
    "Identity",
    "Authority",
    "State",
    "Transition",
    "Audit",
    "Executor",
    "Workspace",
    "Artifact",
    "Validation",
    "Governance",
    "Replay",
)


def _is_mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


def _kernel_20_binding_from_payload(payload: Any) -> set[str]:
    if not _is_mapping(payload):
        return set()
    return {str(item) for item in payload.get("coverage", []) if isinstance(item, str)}


def minimal_kernel_binding_coverage(binding: Mapping[str, Any] | None) -> bool:
    """Return true when a payload's kernel binding satisfies minimal spine coverage."""

    if not _is_mapping(binding):
        return False
    if binding.get("kernel") != "Kernel 20":
        return False
    return MINIMAL_KERNEL_BINDING_12.issubset(_kernel_20_binding_from_payload(binding))


def full_kernel20_coverage(binding: Mapping[str, Any] | None) -> bool:
    """Return true only when all required Kernel20 primitives are declared in coverage."""

    if not _is_mapping(binding):
        return False
    if binding.get("kernel") != "Kernel 20":
        return False
    return KERNEL20_PRIMITIVE_SET.issubset(_kernel_20_binding_from_payload(binding))


def describe_kernel20_coverage(binding: Mapping[str, Any] | None) -> dict[str, Any]:
    """Provide a compact coverage report for kernel-binding diagnostics."""

    coverage = _kernel_20_binding_from_payload(binding) if _is_mapping(binding) else set()
    declared_missing_minimal = sorted(MINIMAL_KERNEL_BINDING_12 - coverage)
    declared_missing_full = sorted(KERNEL20_PRIMITIVE_SET - coverage)
    return {
        "kernel_name": binding.get("kernel") if _is_mapping(binding) else None,
        "minimal_coverage": MINIMAL_KERNEL_BINDING_12.issubset(coverage),
        "full_coverage": KERNEL20_PRIMITIVE_SET.issubset(coverage),
        "declared_coverage": sorted(coverage),
        "missing_minimal": declared_missing_minimal,
        "missing_full": declared_missing_full,
    }
