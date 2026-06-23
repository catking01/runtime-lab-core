"""Deterministic JSON and text hashing helpers."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def stable_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
