from __future__ import annotations

import pytest

from runtime_lab.test_runner.allowlist import DEFAULT_ALLOWLIST, resolve_command_spec, validate_command_spec
from runtime_lab.test_runner.errors import TestRunnerPolicyError
from runtime_lab.test_runner.models import TestCommandSpec


def test_default_allowlist_contains_only_r127_initial_command_ids():
    assert set(DEFAULT_ALLOWLIST) == {
        "kernel_descriptors",
        "llm_provider_offline",
        "repo_context",
        "patch_proposal",
        "patch_apply",
        "test_runner",
    }
    assert DEFAULT_ALLOWLIST["kernel_descriptors"].argv == (
        "python",
        "-m",
        "pytest",
        "tests/kernel20",
        "tests/descriptors",
    )
    assert DEFAULT_ALLOWLIST["llm_provider_offline"].argv == (
        "python",
        "-m",
        "pytest",
        "tests/llm_provider",
        "-m",
        "not live_deepseek",
    )


def test_resolve_command_spec_returns_validated_allowlisted_spec():
    spec = resolve_command_spec("patch_apply", allowlist=DEFAULT_ALLOWLIST)

    assert spec.command_id == "patch_apply"
    assert spec.argv == ("python", "-m", "pytest", "tests/patch_apply")


def test_resolve_command_spec_rejects_unknown_command_id():
    with pytest.raises(TestRunnerPolicyError, match="UNKNOWN_COMMAND_ID"):
        resolve_command_spec("run_anything", allowlist=DEFAULT_ALLOWLIST)


@pytest.mark.parametrize(
    ("argv", "code"),
    [
        (("pytest",), "PYTEST_TARGET_REQUIRED"),
        (("python", "-m", "pytest"), "PYTEST_TARGET_REQUIRED"),
        (("python", "-m", "pytest", "-k", "anything"), "PYTEST_K_EXPRESSION_REJECTED"),
        (("python", "-m", "pytest", "tests/llm_provider", "-m", "live_deepseek"), "LIVE_DEEPSEEK_REJECTED"),
        (("bash", "-lc", "pytest tests/test_runner"), "DISALLOWED_COMMAND_FAMILY"),
        (("sh", "-c", "pytest tests/test_runner"), "DISALLOWED_COMMAND_FAMILY"),
        (("zsh", "-c", "pytest tests/test_runner"), "DISALLOWED_COMMAND_FAMILY"),
        (("python", "-c", "print(1)"), "PYTHON_C_REJECTED"),
        (("curl", "https://example.com"), "DISALLOWED_COMMAND_FAMILY"),
        (("git", "status"), "DISALLOWED_COMMAND_FAMILY"),
        (("make", "test"), "DISALLOWED_COMMAND_FAMILY"),
        (("npm", "test"), "DISALLOWED_COMMAND_FAMILY"),
    ],
)
def test_validate_command_spec_rejects_disallowed_argv(argv: tuple[str, ...], code: str):
    spec = TestCommandSpec(command_id="bad", argv=argv)

    with pytest.raises(TestRunnerPolicyError, match=code):
        validate_command_spec(spec)


def test_validate_command_spec_rejects_shell_enabled_spec():
    spec = TestCommandSpec(command_id="bad", argv=("python", "-m", "pytest", "tests/test_runner"), shell_allowed=True)

    with pytest.raises(TestRunnerPolicyError, match="SHELL_SPEC_REJECTED"):
        validate_command_spec(spec)
