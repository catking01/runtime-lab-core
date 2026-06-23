# Validation

Run the public validation profile from the repository root:

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

Live provider tests are outside the default public validation profile.
