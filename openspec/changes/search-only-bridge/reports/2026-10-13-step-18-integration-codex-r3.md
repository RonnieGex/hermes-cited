# Step 18: independent bridge2 round 3 HTTP and installation evidence

Agent: Codex. Date: 2026-10-13. Branch: `feature/search-only-bridge`.
Reviewed delivery: `cbf4e03ea016319c5ef4d6804d63b9322c6f0ceb`.
Product tested after the local correction: `2ebf7c550e392081b2ea5c1fc9dc21638d8df3b6`.
This is validation evidence required by instruction 1b. Review prose, probes and raw logs remain outside
the repository at `C:/Users/Franc/Documents/katalis-dev/tasks/`. No browser frontend exists.

## Commands and results

All Python commands below use `.venv/Scripts/python` from the repository, Python 3.11.15,
`PYTHONDONTWRITEBYTECODE=1`, temporary homes and synthetic inputs. Full suites set
`CITED_DOCS_REPO=C:/Users/Franc/Documents/katalis-dev/community-hermes`, read-only SHA
`2c5b5d380085cf75923132d58d53390b385a274b`.

| Command | Result |
| --- | --- |
| `python -m pytest -q -ra -p no:cacheprovider` on the delivery | 937 passed, 1 skipped in 383.42s (0:06:23) |
| Same full command after the product correction | 937 passed, 1 skipped in 459.92s (0:07:39) |
| `python -m pytest -q -s -p no:cacheprovider ../tasks/test_bridge2_codex_r3.py` | 12 passed in 35.81s |
| `python ../tasks/bridge2-codex-r3-curl.py` | 8/8 cases passed, port closed, identical home inventory |
| `python ../tasks/bridge2-codex-r3-install.py` | 1 passed, 29 deselected in 433.51s (0:07:13); container removed |
| `openspec validate --all --strict` | 2 passed, 0 failed |

The full suite's only skip is the real Linux install without its HERMES_TEST prerequisites; that same
integration was executed separately below. This is local validation of the workflow test command,
not an assertion that remote CI has run. No plugin database exists; state means the complete home inventory.

## Agent-executed curl, task 5.1

The external supervisor starts the delivered `tests/fakes/chassis_surface.py` as a real child process with
`--port 53719 --record <temporary-workspace>/http.jsonl`. PID **30272** terminated, a fresh socket connection
proved port **53719** closed, and the synthetic authorization file was removed. Ports 3240/3241 were not used.

Each case executes this exact argument pattern, with request and authorization held in temporary files:

```text
curl.exe --silent --show-error --max-time 10 --request POST http://127.0.0.1:53719<path>
  --header "Content-Type: application/json" --data-binary @<case.json>
  --output <result.json> --write-out %{http_code} --header @<authorization.txt>
```

The unauthenticated case omits the last header. Each curl also has an external 15-second timeout.
The request id is `r3-compound`. Cases use 500 repetitions of `e` plus U+0301 (1000 code points),
that query plus `x` (1001), unauthenticated bytes FF FE, paths `/api%2fchassis/mcp` and
`/api/chassis/mcp;transport=json`, a null method, arguments without a tool name, and query
`north` + U+2028 + `south` + U+2029 + `east`. These are new cases for this round.

| Case | HTTP | Error code | Result |
| --- | --- | --- | --- |
| combining-1000 | 200 | None | PASS |
| combining-1001 | 200 | -32602 | PASS |
| unauth-invalid-utf8 | 401 | unauthorized | PASS |
| encoded-path-separator | 404 | None | PASS |
| path-segment-parameter | 404 | None | PASS |
| null-method-valid-id | 400 | -32600 | PASS |
| missing-tool-name | 200 | -32601 | PASS |
| unicode-line-separator-query | 200 | None | PASS |

Both complete inventories are `[["witness.bin", 256, "cd6816b77f68d70001fc3eaa4d42bdd67cb5973b3151cc5292ecc02a3daac6ab"]]`. No file was excluded.
The exact argv, request bytes/digests, parsed responses and cleanup results are retained in external
`bridge2-codex-r3-curl.json`; the executable source is `bridge2-codex-r3-curl.py`.

## Real offline installation, tasks 5.3, 11.4 and 13.4

The external supervisor creates a fresh local mirror and canonical tar/lock. It runs the existing D9
installation test using the provisioned runner in image
`sha256:4d1caded1f729ae443eb803f26ffde7b61e696aeaef62f099abb6dd6b14257c7`,
with `--network none`, 2 CPUs, 4 GiB, 300 processes, temporary runtime/home directories and read-only
mounts for the mirror, repository, host venv, archives, cache and wheelhouse. It publishes no ports.
The loopback build index used port 40663. The route table is empty and an external connection was refused.
No personal Hermes executable, home or service is used. The container is `bridge2-codex-r3-install`.

```text
/opt/chassis/.venv/bin/python -m pytest -vv -s --showlocals -p no:cacheprovider
  tests/test_profile_install.py -k a_fresh_real_profile_installs

/opt/chassis/.venv/bin/hermes --profile bridge-probe plugins install
  file:///release/hermes-cited.git --ref 2ebf7c550e392081b2ea5c1fc9dc21638d8df3b6 --enable --yes-deps
```

Host pin: `dce1e9b37581dd62e480a9064dc04a709c2940d3`, tracked tree clean. The test verifies both host HEAD and bridge HEAD.
Bridge canonical `git archive --format=tar` has **2160640 bytes**, SHA-256
`c9f42b6a862c4bdcce8d87610ff54f7bce12991a831ed5a27fb2c4e32be5db2c`. This is a review artifact, not a final archived release lock.

Provisioned managed CPython `3.14.7+20260901`, archive SHA-256
`0ab3305457051cd3e7c031857e005f1bda17c218a1990567dacaaac6dd1d14f0`, and uv `0.12.3`, archive SHA-256
`600cf9a742aca00d292673b16b5acffaa7b8c269a364ad0c2e79498dcb1fe101`.
`HERMES_RUNTIME_DIR=/opt/runtime` points at content-addressed `fetch-<sha256>` entries.
The runner validates these against the pinned host lock and provisions the build-backend wheels locally.
Test interpreter: Python 3.12.14. Installation completed without a download failure and reached the real
loader/catalog/scoped dispatch assertions. No skip was accepted in this selected integration.

Catalog: hermes-cited 0.2.0 enabled, one cited_search tool, zero hooks and zero commands; scoped dispatch
returns the unsealed search model envelope. After setup, all **275** regular files retain
path, size and SHA-256 (`assert after == baseline`); `cited/` is absent. The compact sorted inventory JSON
has SHA-256 `ac5d2e425ac0da1eab8e35855f49ca262bab3697d0e234f15d3bf36f5ff9bdbf`. Complete facts/inventory are in external `bridge2-codex-r3-install.log` and the
extracted `bridge2-codex-r3-integration-facts.json`. Supervisor result: `[{"exit": 0, "seconds": 542.61}, {"container_removed": true}]`.

## SDD reconciliation

Proposal, design D1-D10, specs, fixtures and wire-contract are byte-identical to Fable's `f59ab76`.
There is one active change; 17 modified requirement IDs match the base, four added IDs do not collide,
and the composed specification retains unique H0-H22. The consumer's wire schema and fixture remain
byte-identical. The external audit retains task blocks and the report inventory with SHA-256.

Tasks 1.3/2.3 are backed by their historical RED reports, the corrected registration/identity regressions,
the full suite and the new independent probes. Tasks 6.2/9.8 are backed by the documentation/configuration
diff inspection, the suite's documentation checks, unchanged normative files and strict validation.
This execution supports reconciling those stale flags with their completed successor tasks. Tasks 7.1-7.4
remain open for final independent approval, remote CI and authorized release operations.

The new two-line identity correction is measured here, not independently approved by its own author.
Fable retains final review. D10 excludes Ledger R10; no holdout was run. The real Harness service and a
complete LLM conversation are outside this fake-based bridge acceptance evidence.
