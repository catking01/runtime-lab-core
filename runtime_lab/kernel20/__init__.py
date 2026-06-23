"""Kernel20 primitive registry and binding utilities."""

from .coverage import (
    DESCRIPTOR_SPINE_BINDING_12,
    KERNEL20_PRIMITIVE_ORDER,
    KERNEL20_PRIMITIVE_SET,
    MINIMAL_KERNEL_BINDING_12,
    MINIMAL_SPINE_KERNEL_RELEVANT_FIELDS,
    describe_kernel20_coverage,
    full_kernel20_coverage,
    minimal_kernel_binding_coverage,
)
from .primitives import KERNEL20_PRIMITIVE_REGISTRY, Kernel20Primitive, kernel20_primitives_by_name
from .status import ALLOWED_PRIMITIVE_STATUSES

__all__ = [
    "ALLOWED_PRIMITIVE_STATUSES",
    "Kernel20Primitive",
    "KERNEL20_PRIMITIVE_ORDER",
    "KERNEL20_PRIMITIVE_REGISTRY",
    "kernel20_primitives_by_name",
    "KERNEL20_PRIMITIVE_SET",
    "DESCRIPTOR_SPINE_BINDING_12",
    "MINIMAL_KERNEL_BINDING_12",
    "MINIMAL_SPINE_KERNEL_RELEVANT_FIELDS",
    "describe_kernel20_coverage",
    "full_kernel20_coverage",
    "minimal_kernel_binding_coverage",
]
