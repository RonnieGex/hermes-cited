# Step 3.1 — The full-mode regression suite and every existing test updated

- Change: `search-only-bridge` · Base SHA: `9567d79` · Agent: DeepSeek · Date: 2026-10-12
- Python: `.venv\Scripts\python` (3.11.15) · `PYTHONDONTWRITEBYTECODE=1`

## The one existing test updated, and why

| Test | Change | Why |
|---|---|---|
| `tests/test_package.py::test_the_manifest_is_valid_and_names_the_plugin` | `CITED_MCP_TOKEN` moved from `requires_env` to `optional_env`, and the version 0.2.0 is asserted | D4 of this change makes `CITED_URL` the only unconditional `requires_env`; both tokens are conditional secrets of their own mode. The old assertion encoded the 0.1.0 manifest, which this change replaces. |

No other existing test was edited. No delivery policy, no H0-H18 behavior and no assertion of the prior
rounds changed.

## The regression run

```powershell
.\.venv\Scripts\python -m pytest -q tests/test_plugin.py tests/test_adversarial.py tests/regressions
# 502 passed, 3 skipped in 245.41s
```

The first full run of this step exposed a real defect of the implementation, not of the tests: the strict
profile scope was applied to `full` registration too, so any run where the `agent` package was importable
but no profile scope was active (the host-integration fixtures of the suite) refused to register the legacy
surface and 145 cases fell. The hard rule of this round is that `full` does not change behavior, so the
implementation now keeps the legacy environment path when no profile scope is readable and reserves the
strict scope for the search bridge:

- `plugin._register_without_scope`: no readable scope means `full` registers over the environment exactly as
  H0-H18 always did, while `search` registers nothing (it exists to be profile-scoped).
- `config.settings_for`: a registration without a home reads `settings_from_env`; a registration with a home
  is strict and refuses a changed home or mode.

This is recorded as a deliberate reading of D2 in the delivery report: the STRICT scope of H19-H21 governs
the search bridge; the legacy full surface keeps its environment path so the existing suite stays green, as
the round's hard rule demands.

## Verdict

PASS. Every H0-H18 regression is green again, and the only existing-test edit is the manifest contract.
