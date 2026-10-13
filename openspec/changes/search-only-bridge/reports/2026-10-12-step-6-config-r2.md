# Step 6.2 (round 2) — the living context against the corrected implementation

- Change: `search-only-bridge` · Branch: `feature/search-only-bridge` · Agent: DeepSeek
- Date: 2026-10-12 · Python: `.venv\Scripts\python` (3.11.15)
- Round 1 review item: task 6.2 reopened because the claimed fail-closed scope contradicted the actual
  full-mode environment fallback.

## Verification

`openspec/config.yaml`, `plugin.yaml`, `README.md`, `README.es.md` and `docs/technical-manual.md` were read
line by line against the corrected implementation.

| Statement | Implementation after the B01 correction |
|---|---|
| `CITED_BRIDGE_TOOLS` selects full (default) or search | `config.bridge_mode_of`, `plugin.register` (the fallback helper no longer exists) |
| Search registers only `cited_search` over `/api/chassis/mcp` | `plugin._register_search`, `tools.search_only`, `client.call_tool_search` |
| with a profile-scoped `CITED_SEARCH_TOKEN` | `config.search_settings_for`, `config.active_scope` |
| a missing, non-mapping or unreadable scope fails closed | `config.host_is_present`, `config.active_scope`, `plugin.register`, `config.settings_for` |
| no environment fallback while Hermes is present | `plugin.register` refuses on a scope error; only an absent `agent` package selects `os.environ` |
| no hooks, commands, skill or local writes | `test_search_registers_exactly_one_tool_and_nothing_else`, `test_search_writes_nothing_under_the_home_on_success_and_on_error` |
| H6 applies to both modes | the shared redirect refusal and reflection check of `client.py` |
| Full keeps `/api/mcp`, the modes, the verifier and the audit log | `plugin._register_full`; the H0-H18 suite is green (875 passed) |

## Drift found and corrected

- `hermes_cited/__init__.py` declared `__version__ = "0.1.0"` while `plugin.yaml`, the delivered fixture and
  `docs/technical-manual.md` state `0.2.0`. The package version is now `0.2.0`.
- `openspec/config.yaml` did not state the fail-closed scope rule that D2 makes normative. One sentence was
  added to the living context: a missing, non-mapping or unreadable scope fails closed at registration and
  at every call, with no fallback to the process environment while `agent` is present.
- The historical `reports/2026-10-12-step-6-docs.md` still names `plugin._register_without_scope`. It is
  preserved as the historical evidence of round 1 and is superseded by this report; the helper was removed
  by the B01 correction.

## Structural validation

```powershell
openspec validate --all --strict
# ✓ spec/hermes-plugin
# ✓ change/search-only-bridge
# Totals: 2 passed, 0 failed (2 items)
# exit code 0
```

## Verdict

PASS. No silent drift remains: the living context, the manifest, both READMEs and the manual match the
corrected implementation, and the package version matches the manifest.
