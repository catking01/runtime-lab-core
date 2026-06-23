# Runtime Lab Test Navigation

This file is navigation-only. It does not define pytest configuration, change
markers, alter fixtures, or change test collection.

## Focused Suites

| Suite | Expected count | Purpose | Boundary |
| --- | ---: | --- | --- |
| `tests/kernel20 tests/descriptors` | 196 | Kernel20 registry and descriptor validation | Offline only; descriptor fixture files are test inputs and must not be rewritten in no-behavior hygiene batches. |
| `tests/llm_provider -m "not live_deepseek"` | 22 | DeepSeek test-provider policy, redaction, receipts, fake transport, and negative cases | Offline by default; the `live_deepseek` marker remains explicitly excluded unless a separate live gate authorizes it. |
| `tests/repo_context` | 32 | Read-only repo context path policy, file reads, grep, receipts, and negative cases | No shell, subprocess, network, or write behavior. |
| `tests/patch_proposal` | 49 | Patch proposal artifact-only validation and receipts | Does not apply patches or run tests from production code. |
| `tests/patch_apply` | 79 | Human-approved patch apply transaction controls | Mutates only pytest temporary workspaces created by fixtures. |
| `tests/test_runner` | 78 | Allowlisted command-ID test runner policy, receipts, redaction, and fake execution | Keeps live DeepSeek rejected by default. |
| `tests/agent_loop` | 63 | Supervised local agent-loop policy, authority, receipts, replay, and dry-run integration | No autonomous/general coding-agent claim and no live provider by default. |

## Fixture Hygiene Rules

Allowed in no-behavior hygiene batches:

- comments or docstrings that clarify existing fixtures
- navigation metadata such as this file
- fixture naming notes that do not rename fixtures
- documentation of temporary-workspace or secret-boundary usage

Forbidden without a separate higher-risk milestone:

- assertion changes
- expected-value changes
- skip or xfail additions
- marker behavior changes
- fixture return-value changes
- subprocess command changes
- live DeepSeek default changes
- production code changes
