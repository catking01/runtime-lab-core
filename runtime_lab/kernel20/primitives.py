"""Kernel20 primitive registry used by evidence and claim-boundary checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .status import is_allowed_status


@dataclass(frozen=True)
class Kernel20Primitive:
    """Static descriptor for a Kernel20 primitive and its evidence status."""

    name: str
    status: str
    descriptor_binding_fields: list[str]
    evidence_path: str | None
    test_path: str | None
    gap_reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("Kernel20 primitive name must be non-empty")
        if not is_allowed_status(self.status):
            raise ValueError(f"Invalid Kernel20 primitive status: {self.status}")
        if self.status in {"descriptor_only", "noop_only", "implemented"} and not self.evidence_path:
            raise ValueError(f"Evidence path required for {self.name} with status {self.status}")
        if self.status in {"descriptor_only", "implemented", "noop_only"} and not self.test_path:
            raise ValueError(f"Test path required for {self.name} with status {self.status}")
        if self.status in {"planned", "unsupported"} and not self.gap_reason:
            raise ValueError(f"Gap reason required for {self.name} with status {self.status}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "descriptor_binding_fields": list(self.descriptor_binding_fields),
            "evidence_path": self.evidence_path,
            "test_path": self.test_path,
            "gap_reason": self.gap_reason,
        }


def _primitive(
    name: str,
    status: str,
    descriptor_binding_fields: list[str],
    evidence_path: str | None,
    test_path: str | None,
    gap_reason: str | None = None,
) -> Kernel20Primitive:
    return Kernel20Primitive(
        name=name,
        status=status,
        descriptor_binding_fields=list(descriptor_binding_fields),
        evidence_path=evidence_path,
        test_path=test_path,
        gap_reason=gap_reason,
    )


KERNEL20_PRIMITIVE_REGISTRY: tuple[Kernel20Primitive, ...] = (
    _primitive(
        name="Schema",
        status="descriptor_only",
        descriptor_binding_fields=["descriptor_version", "notes", "compatibility_refs", "identity_fields"],
        evidence_path="runtime_lab/descriptors/schema.py",
        test_path="tests/descriptors/test_stage_b1_descriptor_schema.py",
    ),
    _primitive(
        name="Task",
        status="descriptor_only",
        descriptor_binding_fields=["task_ref"],
        evidence_path="runtime_lab/descriptors/validator.py",
        test_path="tests/descriptors/test_stage_b1_descriptor_schema.py",
    ),
    _primitive(
        name="Identity",
        status="descriptor_only",
        descriptor_binding_fields=["identity_binding"],
        evidence_path="runtime_lab/descriptors/validator.py",
        test_path="tests/descriptors/test_r111_s2_spine_contract.py",
    ),
    _primitive(
        name="Authority",
        status="descriptor_only",
        descriptor_binding_fields=["authority_binding", "capability_boundary"],
        evidence_path="runtime_lab/descriptors/validator.py",
        test_path="tests/descriptors/test_stage_b1_descriptor_schema.py",
    ),
    _primitive(
        name="Actor Lifecycle",
        status="descriptor_only",
        descriptor_binding_fields=["state_ref", "transition_intent"],
        evidence_path="runtime_lab/descriptors/spine_adapter.py",
        test_path="tests/descriptors/test_r111_s3_spine_adapter.py",
    ),
    _primitive(
        name="State",
        status="descriptor_only",
        descriptor_binding_fields=["state_ref"],
        evidence_path="runtime_lab/descriptors/spine_adapter.py",
        test_path="tests/descriptors/test_r111_s3_spine_adapter.py",
    ),
    _primitive(
        name="Transition",
        status="descriptor_only",
        descriptor_binding_fields=["transition_intent"],
        evidence_path="runtime_lab/descriptors/spine_adapter.py",
        test_path="tests/descriptors/test_r111_s3_spine_adapter.py",
    ),
    _primitive(
        name="Audit",
        status="descriptor_only",
        descriptor_binding_fields=["audit_binding"],
        evidence_path="runtime_lab/descriptors/spine_adapter.py",
        test_path="tests/descriptors/test_r111_s3_spine_adapter.py",
    ),
    _primitive(
        name="Clock",
        status="descriptor_only",
        descriptor_binding_fields=["logical_clock"],
        evidence_path="runtime_lab/descriptors/schema.py",
        test_path="tests/descriptors/test_stage_b1_descriptor_schema.py",
    ),
    _primitive(
        name="Scheduler",
        status="unsupported",
        descriptor_binding_fields=["minimal_spine"],
        evidence_path=None,
        test_path=None,
        gap_reason="Kernel20 scheduler primitive has not been implemented in this repository stage.",
    ),
    _primitive(
        name="Handoff",
        status="unsupported",
        descriptor_binding_fields=["handoff"],
        evidence_path=None,
        test_path=None,
        gap_reason="Kernel20 handoff primitive is out-of-scope in R112 and remains unresolved.",
    ),
    _primitive(
        name="Tool",
        status="planned",
        descriptor_binding_fields=["capability_boundary", "notes"],
        evidence_path=None,
        test_path=None,
        gap_reason="Tool primitive requires a registered tool invocation layer not introduced in R112.",
    ),
    _primitive(
        name="LLM",
        status="planned",
        descriptor_binding_fields=["notes", "non_claims"],
        evidence_path=None,
        test_path=None,
        gap_reason="LLM primitive requires model invocation capability excluded in current scope.",
    ),
    _primitive(
        name="Executor",
        status="noop_only",
        descriptor_binding_fields=["executor_eligibility", "governance_requirements"],
        evidence_path="runtime_lab/descriptors/noop_bridge.py",
        test_path="tests/descriptors/test_r111_s4d_noop_bridge.py",
    ),
    _primitive(
        name="Workspace",
        status="descriptor_only",
        descriptor_binding_fields=["workspace_boundary"],
        evidence_path="runtime_lab/descriptors/validator.py",
        test_path="tests/descriptors/test_stage_b1_descriptor_schema.py",
    ),
    _primitive(
        name="Resource",
        status="unsupported",
        descriptor_binding_fields=["resource_refs"],
        evidence_path=None,
        test_path=None,
        gap_reason="Resource primitive requires artifact store and runtime state plumbing not introduced in R112.",
    ),
    _primitive(
        name="Security",
        status="unsupported",
        descriptor_binding_fields=["identity_binding", "capability_boundary"],
        evidence_path=None,
        test_path=None,
        gap_reason="Security primitive requires runtime enforcement and policy evaluator not introduced in R112.",
    ),
    _primitive(
        name="Artifact",
        status="descriptor_only",
        descriptor_binding_fields=["artifact_expectation", "validation_requirements"],
        evidence_path="runtime_lab/descriptors/schema.py",
        test_path="tests/descriptors/test_stage_b1_descriptor_schema.py",
    ),
    _primitive(
        name="Validation",
        status="descriptor_only",
        descriptor_binding_fields=["validation_requirements"],
        evidence_path="runtime_lab/descriptors/schema.py",
        test_path="tests/descriptors/test_stage_b1_descriptor_schema.py",
    ),
    _primitive(
        name="Governance",
        status="descriptor_only",
        descriptor_binding_fields=["governance_requirements"],
        evidence_path="runtime_lab/descriptors/schema.py",
        test_path="tests/descriptors/test_stage_b1_descriptor_schema.py",
    ),
)


def kernel20_primitives_by_name() -> dict[str, Kernel20Primitive]:
    return {primitive.name: primitive for primitive in KERNEL20_PRIMITIVE_REGISTRY}
