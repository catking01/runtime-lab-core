from __future__ import annotations

from collections.abc import Mapping
import re


SECRET_KEY_RE = re.compile(r"(api[_-]?key|authorization|bearer|token|secret)", re.IGNORECASE)
SECRET_VALUE_RE = re.compile(r"(Bearer\s+\S+|sk-[A-Za-z0-9_-]{20,}|gho_[A-Za-z0-9_]{20,})")


def contains_secret_like_value(env: Mapping[str, str]) -> bool:
    for key, value in env.items():
        if str(value) == "<REDACTED>":
            continue
        if SECRET_KEY_RE.search(str(key)):
            return True
        if SECRET_VALUE_RE.search(str(value)):
            return True
    return False


def redact_environment(
    env: Mapping[str, str],
    *,
    allowed_env_keys: tuple[str, ...],
    redacted_env_keys: tuple[str, ...],
) -> tuple[dict[str, str], dict[str, object]]:
    allowed = set(allowed_env_keys)
    redacted = set(redacted_env_keys)
    safe_env: dict[str, str] = {}
    dropped: list[str] = []
    redacted_keys: list[str] = []

    for key in sorted(str(k) for k in env):
        value = str(env[key])
        if key not in allowed:
            dropped.append(key)
            continue
        if key in redacted or SECRET_KEY_RE.search(key):
            safe_env[key] = "<REDACTED>"
            redacted_keys.append(key)
            continue
        safe_env[key] = value

    return safe_env, {
        "dropped_keys": sorted(dropped),
        "redacted_keys": sorted(redacted_keys),
        "secret_like_values_present": contains_secret_like_value(safe_env),
    }
