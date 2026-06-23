from __future__ import annotations

from runtime_lab.test_runner.redaction import contains_secret_like_value, redact_environment


def test_redact_environment_allows_only_named_keys_and_redacts_secret_values():
    env, meta = redact_environment(
        {
            "PATH": "/bin",
            "PYTHONPATH": "/repo",
            "DEEPSEEK_API_KEY": "secret-value",
            "Authorization": "Bearer secret-token",
            "UNRELATED": "drop-me",
        },
        allowed_env_keys=("PATH", "PYTHONPATH", "DEEPSEEK_API_KEY", "Authorization"),
        redacted_env_keys=("DEEPSEEK_API_KEY", "Authorization"),
    )

    assert env == {
        "PATH": "/bin",
        "PYTHONPATH": "/repo",
        "DEEPSEEK_API_KEY": "<REDACTED>",
        "Authorization": "<REDACTED>",
    }
    assert meta["redacted_keys"] == ["Authorization", "DEEPSEEK_API_KEY"]
    assert meta["dropped_keys"] == ["UNRELATED"]
    assert meta["secret_like_values_present"] is False


def test_secret_like_detector_flags_bearer_and_common_api_key_names():
    assert contains_secret_like_value({"Authorization": "Bearer abc.def"}) is True
    assert contains_secret_like_value({"DEEPSEEK_API_KEY": "abc"}) is True
    assert contains_secret_like_value({"PATH": "/bin"}) is False
