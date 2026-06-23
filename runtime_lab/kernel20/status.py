"""Kernel20 primitive status vocabulary."""

from __future__ import annotations

from collections.abc import Iterable


ALLOWED_PRIMITIVE_STATUSES = frozenset(
    {
        "implemented",
        "descriptor_only",
        "noop_only",
        "planned",
        "unsupported",
    }
)


def is_allowed_status(status: str) -> bool:
    """Return whether a primitive status label is valid."""

    return status in ALLOWED_PRIMITIVE_STATUSES


def all_statuses_present(statuses: Iterable[str]) -> bool:
    """Return whether all supplied statuses are valid."""

    return all(is_allowed_status(status) for status in statuses)
