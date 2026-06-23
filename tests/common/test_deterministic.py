from __future__ import annotations

import pytest

from runtime_lab.common.deterministic import sha256_text, stable_json


def test_stable_json_sorts_keys_and_uses_compact_separators() -> None:
    payload = {"b": 2, "a": 1, "nested": {"z": 0, "m": 3}}

    assert stable_json(payload) == '{"a":1,"b":2,"nested":{"m":3,"z":0}}'


def test_stable_json_uses_ascii_escaping() -> None:
    assert stable_json({"name": "cafe\u00e9"}) == '{"name":"cafe\\u00e9"}'


def test_sha256_text_returns_known_lowercase_hex_digest() -> None:
    assert sha256_text("runtime-lab-core") == "d6fd1bbf80455b91d68fbd218e54d242a25cdb267b61224ee756dd06ab8c4578"


def test_public_helper_matches_legacy_private_helper_outputs_when_available() -> None:
    legacy_module = ".".join(["research_" + "runtime", "kernel_spine", "runtime_stage_a_common"])
    legacy = pytest.importorskip(legacy_module)
    payload = {"b": ["z", "a"], "a": {"unicode": "\u0394"}}
    text = legacy.stable_json(payload)

    assert stable_json(payload) == text
    assert sha256_text(text) == legacy.sha256_text(text)
