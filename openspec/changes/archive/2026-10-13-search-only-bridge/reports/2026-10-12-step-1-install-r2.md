# Step 1.4 / 5.3 (round 2) — the profile installation runner and the blocked VM

- Change: `search-only-bridge` · Branch: `feature/search-only-bridge` · Agent: DeepSeek
- Date: 2026-10-12 · Python: `.venv\Scripts\python` (3.11.15) · `PYTHONDONTWRITEBYTECODE=1`
- Round 1 review item: **M01** (BROKEN, Major) — the installation test passed the Hermes SHA as the bridge
  ref and never verified the digest, the effective catalog or a scoped call.

## What was wrong

`tests/test_profile_install.py` used `PIN = dce1e9b…` (the Hermes host commit) as the `--ref` of
`plugins install`, a commit that does not exist in this repository; after the install it only checked that
a directory existed and that the text `cited_search` appeared in `plugin.yaml`, which the full-mode manifest
also carries. It never wrote the search configuration before discovery, never loaded the catalog, never
called the handler and never verified the installed digest.

## What was changed

- `HOST_PIN` (the Hermes commit) and `HERMES_TEST_BRIDGE_REF` (this repository's full commit) are separate.
- `_check_bridge_ref` accepts only a full lowercase 40-hex commit and rejects the host pin.
- `_install_argv` builds design D4's exact argv with the bridge commit in a separate `--ref`.
- The skipped VM test now:
  1. verifies the bridge ref is a `commit` in the read-only local mirror;
  2. writes `CITED_URL`, `CITED_BRIDGE_TOOLS=search` and `CITED_SEARCH_TOKEN` into the profile `.env`
     **before** discovery;
  3. installs with D4's flags (`--profile`, `file://…/hermes-cited.git`, `--ref <bridge>`, `--enable`,
     `--yes-deps`);
  4. checks `git rev-parse HEAD` equals the bridge ref and the installed tree is clean;
  5. reads the installed manifest (version 0.2.0, `cited_search` provided, only `CITED_URL` required);
  6. loads the installed plugin under the real `agent.secret_scope` profile scope, asserts one tool and no
     hooks, commands or skill, and calls the handler against a guarded loopback fake;
  7. asserts the request reached `/api/chassis/mcp` with the profile's search bearer and that the profile
     `.env` never names `CITED_MCP_TOKEN`.

## RED — the runner helpers did not exist

```powershell
.\.venv\Scripts\python -m pytest -q -p no:cacheprovider tests/test_profile_install.py
# FAILED test_the_install_argv_passes_the_bridge_ref_and_never_the_host_pin
# FAILED test_the_host_pin_is_never_accepted_as_the_bridge_ref
# FAILED test_a_bridge_ref_that_is_not_a_full_lowercase_sha_is_rejected[...] (5 cases)
# 7 failed, 7 passed, 1 skipped in 0.35s
# exit code 1
```

## GREEN

```powershell
.\.venv\Scripts\python -m pytest -q -p no:cacheprovider tests/test_profile_install.py -rs
# ..............s                                                          [100%]
# SKIPPED [1] tests\test_profile_install.py:199: the disposable VM is not available in this run:
#   HERMES_TEST_CLI, HERMES_TEST_MIRROR, HERMES_TEST_BRIDGE_REF are not all set
# 14 passed, 1 skipped in 0.24s
# exit code 0
```

## 5.3 BLOCKED — the disposable VM does not exist in this run

```powershell
wsl -l -v
#   NAME              STATE      VERSION
# * docker-desktop    Running    2
docker ps -a --format '{{.Names}} {{.Image}}'
# only the personal Postiz, CRM, mail and RAG containers; no D4 disposable VM, no pinned Hermes CLI
# and no local read-only mirror for the installation.
```

The real E2E therefore remains **BLOCKED** and is not faked: the test is skipped with that explicit reason,
and no green is claimed for a profile installation that was never executed. The structural half of the
runner (separate pins, ref validation, D4 argv) is executed here and green.

## Verdict

PASS for the runner correction; **BLOCKED** for the isolated E2E of 5.3.
