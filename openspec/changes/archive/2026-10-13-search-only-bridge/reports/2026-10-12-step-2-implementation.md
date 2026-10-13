# Step 2.1–2.4 — The search-only implementation (GREEN)

- Change: `search-only-bridge` · Base SHA: `9567d79` · Agent: DeepSeek · Date: 2026-10-12
- Python: `.venv\Scripts\python` (3.11.15) · `PYTHONDONTWRITEBYTECODE=1` · every run with a timeout

## 2.1 `hermes_cited/config.py`

- `bridge_mode_of`: absent/empty selects `full`, `search` selects the bridge, anything else raises a
  redacted sentence that names `CITED_BRIDGE_TOOLS` and not the value.
- `ProfileScope` keeps the mapping **as it arrived** (never copied), so a spy mapping can prove that the
  search path never requests `CITED_MCP_TOKEN`; `has`/`get` take the documented default and never fall
  back to the process environment.
- `active_scope()` imports `agent` first: absent means a run outside Hermes and reads `os.environ`; present
  means `agent.secret_scope` is required and any missing/failing accessor fails closed with the redacted
  `SCOPE_SENTENCE`.
- `Registration(mode, home, explicit)` freezes the mode and the canonical home; `settings_for` and
  `search_settings_for` read URL, selected token and timeout freshly and refuse a changed home or mode.
- `chassis_endpoint_of` accepts an explicit http/https origin with no userinfo, path (trailing slash
  included), query or fragment and appends exactly `/api/chassis/mcp`; `search_timeout_of` accepts an
  integer from 1 through 120000 only.

## 2.2 `hermes_cited/client.py` and `hermes_cited/tools.py`

- `call_tool_search(settings, arguments)`: the wire v1 request, the dedicated bearer, no redirect is ever
  followed and a response is validated against the pinned schema (`id`, `content`, `structuredContent`,
  sequential `n`, `document`, `heading`, `position`, `excerpt`, the recomposed content block) before a
  passage is exposed.
- `tools.validate_search_arguments`: no coercion, no trimming, no unknown property; booleans, floats,
  numeric strings and out-of-range limits are refused before any request.
- `tools.search_model_envelope` returns the JSON string of the model envelope (`cited_tool`, `query`,
  `text`, `passages` with `lines`), never the RPC wrapper and never a `pid`.
- `tools.search`/`tools.ask` now accept an injected `Settings`; with none they read the environment, so the
  full-mode behavior of H0-H18 is unchanged under pytest.

## 2.3 `hermes_cited/plugin.py`

- `register` resolves the scope and the mode once; an unknown mode or an unreadable scope registers
  nothing and prints a redacted sentence to `stderr`/the logger.
- Search registers exactly one tool, `cited_search`, with the wire schema and the description
  `Search unsealed document passages.`, and no command, hook, skill or log writer.
- Full keeps its three tools, three hooks, two commands and the skill, with each evidence handler bound to
  its own registration.

## 2.4 `plugin.yaml`

Version `0.2.0`, byte-for-byte semantics of `fixtures/plugin-search.yaml`: `CITED_URL` is the only
unconditional `requires_env`, `CITED_SEARCH_TOKEN` and `CITED_MCP_TOKEN` are conditional secrets,
`CITED_BRIDGE_TOOLS` defaults to full and both catalogs are potential, not effective.

## GREEN

```powershell
.\.venv\Scripts\python -m pytest -q tests/test_search_guard.py tests/test_search_only_mode.py `
  tests/test_profile_scope.py tests/test_search_wire.py tests/test_manifest_modes.py `
  tests/test_profile_install.py
# 130 passed, 1 skipped, 1 failed in 42.37s
# the one failure is test_the_readme_documents_the_per_profile_install, which step 6.1 satisfies
# the one skip is the disposable-VM install of step 5.3, with its explicit reason
```

Three defects found by this GREEN step were defects of the test apparatus, not of the contract, and were
corrected: the fake recorded every request already redacted, so the in-memory header comparison could not
see the bearer (now only the `--record` file and `recorded` are redacted); the manifest reader did not
treat `python_dependencies: []` as a list; and the temporary spec copy has no `H6` because this change
cites H6 instead of redefining it.

## Verdict

PASS for H19-H21 and the manifest. The README/manual pair of H22 is delivered by step 6.1.

## Secrets

No real token is used anywhere: the fake bearer is a synthetic constant and every recorded row is written
as `<search-token>`. No report, log or commit carries a secret.

Delivery commit of this task: `396912f` (`feat(search): implement the search-only bridge mode`).
