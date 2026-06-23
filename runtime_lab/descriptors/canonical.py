from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from runtime_lab.common.deterministic import sha256_text, stable_json

DERIVED_FIELDS = {"descriptor_id", "canonical_hash", "descriptor_hash"}


def _strip_derived(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _strip_derived(nested) for key, nested in value.items() if key not in DERIVED_FIELDS}
    if isinstance(value, list):
        return [_strip_derived(item) for item in value]
    return value


def canonical_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return _strip_derived(dict(payload))


def canonical_hash(payload: Mapping[str, Any]) -> str:
    return sha256_text(stable_json(canonical_payload(payload)))


def descriptor_id(payload: Mapping[str, Any]) -> str:
    return f"b1-desc-{canonical_hash(payload)[:12]}"
