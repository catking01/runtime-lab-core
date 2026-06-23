# Runtime Lab Core

Runtime Lab Core is a curated public-core extraction of Runtime Lab's local runtime boundary work. It contains deterministic helper utilities, authority and descriptor checks, read-only repository context tools, patch proposal and human-approved patch application surfaces, an allowlisted test runner, and a supervised local agent-loop validation surface.

## What This Repository Is

- A small public validation corpus for Runtime Lab Core modules.
- A reproducible offline test surface for descriptor, authority, patch, runner, and agent-loop boundaries.
- A reference package for public review of the selected R135 public-core extraction.

## What This Repository Is Not

- It is not the private `runtime_lab` repository as a whole.
- It is not production readiness evidence.
- It is not an autonomous or general coding-agent capability claim.
- It is not equivalent to Codex, Claude Code, or any hosted coding-agent product.
- It does not include private evidence records, sessions, shell snapshots, credentials, private roadmap material, or enterprise/private runtime surfaces.

## Quick Validation

```bash
python -m compileall runtime_lab
python -m pytest tests/common tests/kernel20 tests/descriptors -q
python -m pytest tests/llm_provider -m 'not live_deepseek' -q
python -m pytest tests/repo_context -q
python -m pytest tests/patch_proposal -q
python -m pytest tests/patch_apply -q
python -m pytest tests/test_runner -q
python -m pytest tests/agent_loop -q
```

## Architecture Map

- `runtime_lab/common`: deterministic JSON and SHA-256 helpers.
- `runtime_lab/admission`: descriptor admission policy and receipts.
- `runtime_lab/authority`: authority packet canonicalization and verification.
- `runtime_lab/descriptors`: descriptor schema, canonicalization, validation, and no-op evidence adapters.
- `runtime_lab/kernel20`: primitive and boundary status checks.
- `runtime_lab/llm_provider`: offline provider adapter tests with live-provider defaults disabled.
- `runtime_lab/repo_context`: bounded read-only repository context operations.
- `runtime_lab/patch_proposal`: patch proposal artifact and receipt surface.
- `runtime_lab/patch_apply`: human-approved patch apply transaction surface.
- `runtime_lab/test_runner`: allowlisted command-id test runner surface.
- `runtime_lab/agent_loop`: supervised local agent-loop orchestration surface.

## Included Tests

The included tests cover deterministic helpers, Kernel20 boundary fixtures, descriptor validation, offline provider behavior, read-only repository context operations, patch proposal artifacts, human-approved patch application, allowlisted test execution, and supervised agent-loop behavior.

## Provider And Live-Test Boundary

Live provider tests are not run by default. The public validation profile excludes the `live_deepseek` marker and expects offline/fake-transport validation unless a future maintainer explicitly enables live-provider gates in a separate private environment.

## Evidence Summary

This package is generated from the R135 public-core extraction manifest after the R135C dependency repair and R135E Apache-2.0 license approval record.

The public repository is published at `https://github.com/catking01/runtime-lab-core`. Public CI has passed for commit `f7756624e99b2786336529d870cf8b534ac91a39`, and annotated tag `public-core-r135g-s2` peels to that commit. No GitHub release has been published.

This evidence does not claim production readiness, autonomous or general coding-agent capability, Codex or Claude Code equivalence, security certification, patent clearance, or publication of the private `runtime_lab` repository as a whole.

## Maintainer Workflow

Start from a clean public checkout, run the validation commands, inspect the public manifests and CI result, and preserve the non-claim boundary. Creating a GitHub release requires a separate release authorization gate.

## License

Runtime Lab Core is licensed under the Apache License, Version 2.0. See `LICENSE`.

Copyright 2026 catking01
