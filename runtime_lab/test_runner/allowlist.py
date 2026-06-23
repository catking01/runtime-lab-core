from __future__ import annotations

from pathlib import Path

from runtime_lab.test_runner.errors import TestRunnerPolicyError
from runtime_lab.test_runner.models import TestCommandSpec


DEFAULT_ALLOWLIST = {
    "kernel_descriptors": TestCommandSpec(
        command_id="kernel_descriptors",
        argv=("python", "-m", "pytest", "tests/kernel20", "tests/descriptors"),
    ),
    "llm_provider_offline": TestCommandSpec(
        command_id="llm_provider_offline",
        argv=("python", "-m", "pytest", "tests/llm_provider", "-m", "not live_deepseek"),
    ),
    "repo_context": TestCommandSpec(
        command_id="repo_context",
        argv=("python", "-m", "pytest", "tests/repo_context"),
    ),
    "patch_proposal": TestCommandSpec(
        command_id="patch_proposal",
        argv=("python", "-m", "pytest", "tests/patch_proposal"),
    ),
    "patch_apply": TestCommandSpec(
        command_id="patch_apply",
        argv=("python", "-m", "pytest", "tests/patch_apply"),
    ),
    "test_runner": TestCommandSpec(
        command_id="test_runner",
        argv=("python", "-m", "pytest", "tests/test_runner"),
    ),
}

DISALLOWED_COMMANDS = {"bash", "sh", "zsh", "curl", "git", "make", "npm", "node", "nc", "ssh"}


def _command_name(first_argv: str) -> str:
    return Path(first_argv).name


def _pytest_index(argv: tuple[str, ...]) -> int | None:
    command = _command_name(argv[0])
    if command == "pytest":
        return 0
    if len(argv) >= 3 and _command_name(argv[0]).startswith("python") and argv[1] == "-m" and argv[2] == "pytest":
        return 2
    return None


def _has_pytest_target(argv: tuple[str, ...], pytest_index: int) -> bool:
    index = pytest_index + 1
    while index < len(argv):
        token = argv[index]
        if token in {"-m", "--maxfail", "--tb", "--disable-warnings", "-o"}:
            index += 2
            continue
        if token.startswith("-"):
            index += 1
            continue
        return True
    return False


def validate_command_spec(spec: TestCommandSpec) -> TestCommandSpec:
    if spec.shell_allowed:
        raise TestRunnerPolicyError("SHELL_SPEC_REJECTED")
    if spec.network_allowed:
        raise TestRunnerPolicyError("NETWORK_SPEC_REJECTED")
    if spec.llm_invocation_allowed:
        raise TestRunnerPolicyError("LLM_SPEC_REJECTED")
    if spec.model_driven_executor_dispatch_allowed:
        raise TestRunnerPolicyError("MODEL_DRIVEN_EXECUTOR_DISPATCH_SPEC_REJECTED")
    if spec.allow_live_deepseek:
        raise TestRunnerPolicyError("LIVE_DEEPSEEK_REJECTED")
    if not spec.argv:
        raise TestRunnerPolicyError("ARGV_REQUIRED")

    command = _command_name(spec.argv[0])
    if command in DISALLOWED_COMMANDS:
        raise TestRunnerPolicyError("DISALLOWED_COMMAND_FAMILY")
    if command.startswith("python") and "-c" in spec.argv:
        raise TestRunnerPolicyError("PYTHON_C_REJECTED")

    pytest_index = _pytest_index(spec.argv)
    if pytest_index is None:
        raise TestRunnerPolicyError("PYTEST_COMMAND_REQUIRED")
    if "-k" in spec.argv:
        raise TestRunnerPolicyError("PYTEST_K_EXPRESSION_REJECTED")
    if any("live_deepseek" in part and part.strip() != "not live_deepseek" for part in spec.argv):
        raise TestRunnerPolicyError("LIVE_DEEPSEEK_REJECTED")
    if not _has_pytest_target(spec.argv, pytest_index):
        raise TestRunnerPolicyError("PYTEST_TARGET_REQUIRED")
    return spec


def resolve_command_spec(
    command_id: str,
    *,
    allowlist: dict[str, TestCommandSpec] | None = None,
) -> TestCommandSpec:
    candidates = allowlist or DEFAULT_ALLOWLIST
    spec = candidates.get(command_id)
    if spec is None:
        raise TestRunnerPolicyError("UNKNOWN_COMMAND_ID")
    return validate_command_spec(spec)
