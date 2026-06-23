"""Canonicalization helpers for R114 authority packets."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from runtime_lab.common.deterministic import stable_json, sha256_text


def canonical_hash(payload: Mapping[str, Any]) -> str:
    """Return a deterministic sha256 hash for a mapping payload."""

    return f"sha256:{sha256_text(stable_json(dict(payload)))}"


def packet_hash_payload(packet: Mapping[str, Any]) -> dict[str, Any]:
    """Return the authority-packet fields covered by payload_hash."""

    candidate = dict(packet)
    candidate.pop("packet_id", None)
    candidate.pop("payload_hash", None)
    return candidate
