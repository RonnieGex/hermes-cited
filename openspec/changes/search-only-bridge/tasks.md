# Tasks: search-only-bridge

Branch: feature/search-only-bridge. No implementation is authorized by a specification-only correction commit.
Each section writes `reports/YYYY-MM-DD-step-N-<name>.md` with exact commands/output, SHA, agent, counts,
runtime and verdict. Check a task only after execution. No plugin database exists: before/after means a sorted
inventory and SHA-256 of all regular files in the isolated HERMES_HOME and cited/ before registration and after
calls, without excluding any plugin-created file. Production client data and personal services are never test inputs.
The correction run performs no archive, merge or push; the future implementation closure below remains required.

## 0. Branch
- [x] 0.1 Branch creation evidence: `reports/2026-10-12-step-0-branch.md`.

## 1. TDD and guard first
- [x] 1.1 Write RED `tests/test_search_guard.py`: all effective URLs, sockets and redirect destinations reject
      ports 3240/3241, localhost aliases and IPv6 equivalents; canonical paths reject the personal installation,
      symlinks/junction escapes and anything outside the registered temporary workspace. Missing overrides fail
      before file/process/network effects. Then implement the test guard and record RED/GREEN.
      Evidence: `reports/2026-10-12-step-1-guard.md`, `tests/search_guard.py`, `tests/test_search_guard.py`.
      Reopened in R1: guard_environment({}) succeeds; conftest does not enforce required overrides or paths.
      Closed in R2: `guard_environment` requires HERMES_HOME and CITED_URL before any effect, the blanket
      tempdir registration is removed, conftest isolates an inherited personal HERMES_HOME and the host
      imports, and `bound_scope` guards the profile home. RED 2 failed, 1 passed; GREEN 27 passed in 5.99s.
      Evidence: `reports/2026-10-12-step-1-guard-r2.md`.
      Reclosed in R3: M02 — the fake and its CLI now apply `guard_path` to the `--record` destination before
      the server exists, so the guard precedes every file and process effect; see 11.3 and
      `reports/2026-10-12-step-11-guard-r3.md`.
- [x] 1.2 Write `tests/fakes/chassis_surface.py` for wire v1 on a guarded free loopback port, including tools/list,
      every error and both redirect classes. No real provider is used. Add a script entry accepting --port and
      --record in this test file for the curl checks below.
      Evidence: `reports/2026-10-12-step-1-red.md`, `reports/2026-10-12-step-5-http.md`.
      Reopened in R1: unauthenticated oversized input returns 413, extra envelope fields are accepted,
      JSON null is reported as a parse error, and an invalid version echoes a non-null id.
      Closed in R2: authentication precedes body parsing, the envelope is closed, `null` is -32600 and an
      invalid version or id answers a null id. RED 5 failed, 11 passed; GREEN 16 passed in 10.12s;
      probe case `delivered_fake_conforms` 4 passed. Evidence: `reports/2026-10-12-step-1-wire-fake-r2.md`.
- [ ] 1.3 RED `tests/test_search_only_mode.py`, `tests/test_profile_scope.py`, `tests/test_search_wire.py` for every
      H19-H21 scenario and Mapping access spies. Record before/after including failure paths.
      Evidence: `reports/2026-10-12-step-1-red.md`, `reports/2026-10-12-step-2-implementation.md`.
      Reopened in R1: missing-scope registration and real multiplex root fallback are not covered by these tests.
      Closed in R2: missing/non-mapping/blank/failing scopes, the broken host dependency, the equivalent home
      spelling and every fixed transport diagnostic have cases. RED 11 failed, 2 passed; GREEN 107 passed in
      44.02s; the R1 probe is 27 passed, including the two real-host scope cases.
      Evidence: `reports/2026-10-12-step-2-scope-r2.md`.
      Reclosed in R3: B01 — the full callbacks and their turn state are bound to the registering profile; the
      new cases are `tests/test_profile_callbacks.py` and the R2 probe is 21 passed; see 11.1/11.2/11.5 and
      `reports/2026-10-12-step-11-callbacks-r3.md`.
- [x] 1.4 RED `tests/test_manifest_modes.py`, `tests/test_profile_install.py`, and README/manual tests for H22;
      preserve full regression cases H12-H18 and check unique IDs on a temporary synchronized spec copy.
      Evidence: `reports/2026-10-12-step-1-red.md`, `reports/2026-10-12-step-6-docs.md`.
      Reopened in R1: the installation test passes the Hermes SHA as the bridge ref and never tests the catalog/call.
      Closed in R2: the host pin and the bridge ref are separate, the runner writes the search configuration
      before discovery and verifies digest, manifest, catalog and a scoped handler call. RED 7 failed;
      GREEN 14 passed, 1 skipped. Evidence: `reports/2026-10-12-step-1-install-r2.md`.
      Reclosed in R3: M01 — the runner verifies the host pin against the checkout, the canonical archive
      SHA-256/size against `bridge.lock`, and the effective catalog through the real host loader and registry;
      the VM E2E of 5.3 remains BLOCKED. GREEN `tests/test_profile_install.py`: 29 passed, 1 skipped; see 11.4
      and `reports/2026-10-12-step-11-install-r3.md`.
- [x] 1.5 `pytest -q tests/test_search_guard.py tests/test_search_only_mode.py tests/test_profile_scope.py
      tests/test_search_wire.py tests/test_manifest_modes.py` before implementation; record intended failures.
      Evidence: `reports/2026-10-12-step-1-red.md` (104 failed, 34 passed, 1 skipped).

## 2. Small implementation steps
- [x] 2.1 config.py: scoped accessor, immutable registration mode, selected credential and timeout validation.
      Evidence: `reports/2026-10-12-step-2-implementation.md`.
      Reopened in R1: a host dependency import failure becomes an environment fallback; home identity is not canonical.
      Closed in R2: `host_is_present` separates an absent host from a broken dependency, `active_scope` requires
      a Mapping and a non-empty home, `canonical_home` normalizes the identity, and `settings_for` fails closed
      on an empty home while the host is present. GREEN 107 passed in 44.02s.
      Evidence: `reports/2026-10-12-step-2-scope-r2.md`.
- [x] 2.2 client.py/tools.py: search-only strict arguments, wire v1 endpoint, response validation and redaction;
      retain full behavior. Do not coerce booleans, numbers or fractional limits in search.
      Evidence: `reports/2026-10-12-step-2-implementation.md`, `tests/test_search_wire.py`.
- [ ] 2.3 plugin.py: search registration with one handler bound to its profile identity, no shared settings cache.
      Evidence: `reports/2026-10-12-step-2-implementation.md`, `tests/test_search_only_mode.py`.
      Reopened in R1: empty search home still registers; an unreadable full scope registers and reads root credentials.
      Closed in R2: `register` refuses every mode when the scope cannot be read, there is no environment fallback
      while the host is present, and a search scope without a home registers nothing. The real-host probe case
      `test_real_hermes_multiplex_missing_scope_never_uses_root` passes. Evidence:
      `reports/2026-10-12-step-2-scope-r2.md`.
      Reclosed in R3: B01 — every full callback validates its registration before an effect and reads its own
      settings, so no callback serves the root or another profile; see 11.1/11.2.
- [x] 2.4 plugin.yaml: implement fixtures/plugin-search.yaml semantics and version 0.2.0.
      Evidence: `reports/2026-10-12-step-2-implementation.md`, `tests/test_manifest_modes.py`.

## 3. Review existing tests
- [x] 3.1 Run full-mode H0-H18 regression suite, list every existing test updated and why; preserve delivery policy.
      Evidence: `reports/2026-10-12-step-3-regression.md` (502 passed, 3 skipped; only the manifest test updated).
      Round 3 adds one more updated test: `tests/regressions/test_r8_dot_passthrough.py` selected the default
      mode with `monkeypatch.setenv("CITED_DEFAULT_MODE", "dot")`, which D2 no longer honours while a profile
      scope is active (the mode now comes from that profile). Its setup rebinds the profile scope to `dot` and
      the assertions are unchanged. See 11.1 and `reports/2026-10-12-step-11-suite-r3.md`.

## 4. Unit verification and state
- [x] 4.1 `pytest -q` with counts/runtime and complete before/after home inventory. No database test is invented.
      Evidence: `reports/2026-10-12-step-4-suite.md` (830 passed, 4 skipped in 365.60s; inventory identical).
- [x] 4.2 `openspec validate --all --strict`; compare both wire copies by SHA-256; run existing CI commands from
      .github/workflows without claiming remote CI has run. Record the actual workflow SHA/result when available.
      Evidence: `reports/2026-10-12-step-4-suite.md` (2 passed, 0 failed; both wire copies byte-identical; remote
      CI not run, no push authorized).

## 5. Agent-executed HTTP and profile integration
- [x] 5.1 Set PYTHONDONTWRITEBYTECODE=1 for isolated handler/profile tests. Start `python tests/fakes/chassis_surface.py --port <guarded-free-port> --record <temporary-log>`;
      from Windows run `curl.exe --max-time 30 --request POST http://127.0.0.1:<port>/api/chassis/mcp
      --header "Content-Type: application/json" --header @<synthetic-header.txt>
      --data-binary @<fixture-request.json>` (fixture's request object only). The temporary header file holds the synthetic search bearer; remove it after
      the run and never include it in reports. Repeat tools/list, wrong token,
      wrong tool and invalid limits. Paste redacted requests/results, stop only the owned fake.
      Evidence: `reports/2026-10-12-step-5-http.md`.
- [x] 5.2 `pytest -q tests/test_search_only_mode.py -k handler_wire -s` must call the registered handler, compare
      its actual wire with the same fixture, capture output and prove no home writes. Create that named case in 1.3.
      Evidence: `reports/2026-10-12-step-5-http.md` (1 passed; request body equals the fixture; inventory identical).
- [x] 5.3 Run `pytest -q tests/test_profile_install.py -s` in the disposable VM using D4's CLI, pinned Hermes,
      local mirror and isolated homes; no personal executable or service. Test real scoped registration and catalog.
      Network is blocked after provisioning. Record CLI argv, digest and profile inventory.
      Executed by Codex in an isolated Linux container with the actual pinned CLI, a read-only mirror,
      verified canonical archive and blocked network. The CLI clones the bridge but exits 1 because the
      managed Python 3.14.7 runtime is not pre-provisioned and its downloads fail offline. The selected
      integration test reports 1 failed, 29 deselected in 37.10s. Installation, catalog-after-install and
      complete profile before/after evidence remain open. This supersedes the previous absent-CLI/mirror
      blocker; the original skip remains in the ordinary suite without the four prerequisite variables.
      Evidence: `reports/2026-10-12-step-12-install-codex-r3.md` and external
      `bridge-codex-r3-linux-native9.log`. The container terminated and was removed; no personal service ran.
      Closed in R4: the same runner pre-provisions the managed CPython 3.14.7 and uv 0.12.3 (digests recorded),
      a warm uv cache and the build-backend wheelhouse before the network closes; the real
      `plugins install file:///release/hermes-cited.git --ref 22a44d6... --enable --yes-deps` completes with
      the external network refused, the catalog holds `cited_search` only, a scoped dispatch answers and the
      complete profile inventory after setup is unchanged. `1 passed, 29 deselected in 264.38s`.
      Evidence: `reports/2026-10-13-step-13-install-r4.md`.
- [x] 5.4 Playwright: not applicable, this change has no frontend.
      Evidence: `reports/2026-10-12-step-5-http.md`.

## 6. Documentation
- [x] 6.1 Update README.md, README.es.md and docs/technical-manual.md with modes, scope failures, conditional
      secrets, complete wire, no writes, per-profile install and canonical pin command.
      Evidence: `reports/2026-10-12-step-6-docs.md`.
- [ ] 6.2 Verify openspec/config.yaml against implementation; update schema/fixture consumers, never silently drift.
      Evidence: `reports/2026-10-12-step-6-docs.md` (no drift found; no edit needed).
      Reopened in R1: the claimed fail-closed scope behavior contradicts the actual full-mode fallback.
      Closed in R2: `openspec/config.yaml` states the fail-closed scope rule, the package version matches the
      0.2.0 manifest, and `openspec validate --all --strict` is 2 passed, 0 failed.
      Evidence: `reports/2026-10-12-step-6-config-r2.md`.
      Reclosed in R3: the living context and the documents state the per-callback binding of `full`; see 11.6
      and `reports/2026-10-12-step-11-config-r3.md`.

## 7. Implementation closing (not executed by this contract correction)
- [ ] 7.1 `/verify`, then independent `/adversarial-review`; resolve Blockers/Majors and re-verify corrections.
      Not executed: no other agent review was requested or available in this round.
- [ ] 7.2 Automated tests and CI green for the delivering SHA; `gitleaks protect --staged` before every commit.
      Partially covered: the suite is green and gitleaks ran before each commit of this round; remote CI has not
      run because no push is authorized (see `reports/2026-10-12-step-4-suite.md`).
- [ ] 7.3 `/archive` with explicit owner approval, then `/commit`; merge/push require a separate authorization.
      Not executed: archive and push are forbidden in this round.
- [ ] 7.4 After the authorized merge, record full merge SHA, SHA-256 and byte size of
      `git archive --format=tar <sha>` without prefix/gzip for A's bridge.lock. Never use this spec commit as a
      completed bridge pin. Update the consuming lock in a later commit.
      Not executed: it depends on the forbidden merge.

## 8. Round 1 review corrections
- [x] 8.1 Enforce H6/H21 redaction on invalid search arguments. External new probe:
      `.venv/Scripts/python -m pytest -q ../tasks/test_bridge_r1_adversarial.py -k unknown_argument`.
      RED: 1 failed on the delivered implementation; the argument key reflected the active search bearer.
      GREEN: 1 passed, 17 deselected; `.venv/Scripts/python -m pytest -q tests/test_search_wire.py`:
      64 passed in 34.99s. Review probes and detailed evidence remain outside the repository as requested.
- [x] 8.2 Enforce H21 wire v1 response additionalProperties=false before exposing passages.
      `.venv/Scripts/python -m pytest -q ../tasks/test_bridge_r1_adversarial.py -k response_rejects`:
      RED: 3 failed; unexpected, error=null and method envelope fields were accepted.
      GREEN: the same command returned 3 passed, 15 deselected in 0.77s.
- [x] 8.3 Enforce H21 origins without even empty userinfo, query or fragment components.
      `.venv/Scripts/python -m pytest -q ../tasks/test_bridge_r1_adversarial.py -k origin_rejects`:
      RED: 3 failed; empty @, ? and # components were accepted.
      GREEN: the same command returned 3 passed, 15 deselected in 4.43s;
      `.venv/Scripts/python -m pytest -q tests/test_search_wire.py -k 'url or origin'`:
      9 passed, 55 deselected in 5.73s.
- [x] 8.4 Enforce the literal closed values required by H19 without case folding or whitespace trimming.
      `.venv/Scripts/python -m pytest -q ../tasks/test_bridge_r1_adversarial.py -k closed_mode`:
      RED: 4 failed. Update the existing mode test that incorrectly admits undocumented spellings.
      GREEN: the same command returned 4 passed, 14 deselected in 0.59s;
      `.venv/Scripts/python -m pytest -q tests/test_profile_scope.py -k mode`: 11 passed, 8 deselected in 1.19s.
- [x] 8.5 Enforce H21 recursive bearer-reflection rejection before JSON-RPC error rendering.
      `.venv/Scripts/python -m pytest -q ../tasks/test_bridge_r1_adversarial.py -k error_response_reflection`:
      RED: 1 failed; a reflected error body was rendered after replacing only the bearer substring.
      GREEN: the same command returned 1 passed, 17 deselected in 0.48s;
      `.venv/Scripts/python -m pytest -q tests/test_search_wire.py -k 'reflected or bad_response'`:
      12 passed, 52 deselected in 6.32s.
- [x] 8.6 Align the manual's mode table with H19 and the literal mode correction.
      `.venv/Scripts/python -m pytest -q ../tasks/test_bridge_r1_adversarial.py -k manual_does`:
      RED: 1 failed, 21 deselected; the manual explicitly allowed whitespace-only mode values.
      GREEN: the same command returned 1 passed, 21 deselected in 0.50s;
      `.venv/Scripts/python -m pytest -q tests/test_docs_bridge.py`: 7 passed in 0.11s.
- [x] 8.7 Reopen checked criteria contradicted by executed independent probes and source inspection.
      `.venv/Scripts/python -m pytest -q ../tasks/test_bridge_r1_adversarial.py -k tasks_do_not`:
      RED: 1 failed, 22 deselected. Preserve the original reports as historical evidence.
      GREEN: the same command returned 1 passed, 22 deselected in 1.28s;
      `openspec validate --all --strict`: 2 passed, 0 failed.
- [x] 8.8 Update the remaining registration regression to reject padded uppercase mode values under H19.
      RED: the full suite returned 1 failed, 833 passed, 1 skipped in 272.51s;
      `test_absent_empty_and_full_register_the_full_surface[ FULL ]` still asserted the undocumented behavior.
      GREEN: `.venv/Scripts/python -m pytest -q tests/test_search_only_mode.py`: 11 passed in 5.54s.
- [x] 8.9 Reopen wire fake completion after independent HTTP counterexamples.
      `.venv/Scripts/python -m pytest -q ../tasks/test_bridge_r1_adversarial.py -k tasks_do_not`:
      RED: 1 failed, 26 deselected; task 1.2 still claims closed-wire completion.
      GREEN: the same command returned 1 passed, 26 deselected in 0.53s;
      `openspec validate --all --strict`: 2 passed, 0 failed.

## 9. Round 2 review corrections
- [x] 9.1 B01 — fail closed on the profile scope and never fall back to root credentials. `active_scope`
      requires a `Mapping` and a non-empty home, a broken host dependency is not an absent host, `register`
      refuses every mode when the scope is unreadable, a search scope without a home registers nothing, and
      `settings_for` fails closed while the host is present. RED 11 failed, 2 passed; GREEN 107 passed in
      44.02s; the R1 probe, including both real-host cases, is 27 passed in 5.19s.
      Evidence: `reports/2026-10-12-step-2-scope-r2.md`.
- [x] 9.2 m01 — canonical home identity. `canonical_home` normalizes `home/child/..` to the same profile while
      two different homes stay refused. Covered by the same GREEN.
      Evidence: `reports/2026-10-12-step-2-scope-r2.md`.
- [x] 9.3 M02 — fixed transport diagnostics. The search timeout, `URLError`, `OSError`, read failure and any
      unexpected exception return fixed sentences; no exception text reaches the model. RED 5 failed on these
      cases; GREEN with the scope suite. Evidence: `reports/2026-10-12-step-2-scope-r2.md`.
- [x] 9.4 M03 — the isolation guard. `guard_environment({})` raises before any effect, the whole temp directory
      is no longer authorised, an inherited personal `HERMES_HOME` is replaced by a temporary one, and the
      host modules of one test are removed afterwards. RED 2 failed, 1 passed; GREEN `tests/test_search_guard.py`
      27 passed in 5.99s. Evidence: `reports/2026-10-12-step-1-guard-r2.md`.
      Reclosed in R3: M02 — the guard is connected to the fake and its CLI before any effect; GREEN
      `tests/test_search_guard.py` 31 passed; see 11.3.
- [x] 9.5 M04 — the fake conforms to the closed wire. Authentication precedes body parsing, the envelope rejects
      unknown properties and a missing version, `null` is -32600 and an invalid version or id answers a null id.
      RED 5 failed, 11 passed; GREEN 16 passed in 10.12s; probe case `delivered_fake_conforms` 4 passed.
      Evidence: `reports/2026-10-12-step-1-wire-fake-r2.md`.
- [x] 9.6 M01 — the profile installation runner. Separate host pin and bridge ref, ref validation, search
      configuration written before discovery, digest, manifest, catalog and scoped handler call. RED 7 failed;
      GREEN 14 passed, 1 skipped. The isolated E2E of 5.3 remains BLOCKED without the disposable VM.
      Evidence: `reports/2026-10-12-step-1-install-r2.md`.
      Reclosed in R3: M01 — the runner proves the host pin, the canonical archive digest/size and the real
      loader catalog offline; GREEN `tests/test_profile_install.py` 29 passed, 1 skipped; see 11.4.
- [x] 9.7 Legacy H0-H18 compatibility — the real-host integration tests install the profile scope their
      temporary profile needs before discovery, and the host imports one test added are removed afterwards so
      the unit suite keeps running outside Hermes. `tests/test_host.py tests/test_plugin.py
      tests/test_adversarial.py tests/regressions`: 511 passed, 3 skipped in 227.55s.
      Evidence: `reports/2026-10-12-step-2-scope-r2.md`.
- [ ] 9.8 6.2 — the living context against the corrected implementation; the package version drift (0.1.0 vs the
      0.2.0 manifest) is corrected and config.yaml states the fail-closed scope rule.
      Evidence: `reports/2026-10-12-step-6-config-r2.md`.
      Reclosed in R3: `openspec/config.yaml` states the per-callback binding and the manual and both READMEs
      carry it; see 11.6 and `reports/2026-10-12-step-11-config-r3.md`.

## 10. Independent round 2 corrections
- [x] 10.1 D2/H19: treat a missing internal agent submodule as a broken host, not an absent host.
      RED: `.venv/Scripts/python -m pytest -q -s -p no:cacheprovider ../tasks/test_bridge_r2_adversarial.py`
      produced two failing `broken_agent_submodule` cases; both registered search from the root environment.
      GREEN: the same probe with `-k broken_agent_submodule`: 2 passed, 17 deselected in 0.57s;
      `.venv/Scripts/python -m pytest -q -p no:cacheprovider tests/test_profile_scope.py`: 26 passed in 5.98s.
      Logs are external by the owner's instruction: `bridge-r2-adversarial-before.log`,
      `bridge-r2-fix-host.log`, `bridge-r2-host-regression.log`. Independent approval remains pending.
- [x] 10.2 H21: discard remote HTTP error text in search diagnostics.
      RED: external R2 probe `test_http_failure_does_not_publish_remote_error_text` failed for HTTP
      400, 429, 500 and 503; each copied the server's private error message into the model response.
      GREEN: `.venv/Scripts/python -m pytest -q -p no:cacheprovider ../tasks/test_bridge_r2_adversarial.py
      -k http_failure`: 4 passed, 15 deselected in 0.69s; `tests/test_search_wire.py
      -k 'bad_response or exception or reflected'`: 14 passed, 55 deselected in 7.41s.
      External evidence: `bridge-r2-fix-http.log`, `bridge-r2-http-regression.log`.
- [x] 10.3 D2: contain membership and getter failures while reading a profile setting.
      RED: external R2 `test_registration_contains_scope_getter_failure` raises the raw getter exception
      out of registration instead of refusing with the fixed scope sentence.
      GREEN: `.venv/Scripts/python -m pytest -q -p no:cacheprovider ../tasks/test_bridge_r2_adversarial.py
      -k scope_getter`: 1 passed, 18 deselected in 0.58s; `tests/test_profile_scope.py`: 26 passed in 4.35s.
      External evidence: `bridge-r2-fix-getter.log`, `bridge-r2-getter-regression.log`.
- [x] 10.4 H22: import the installed package's real nested plugin module.
      RED: external R2 `test_installed_layout_import_uses_the_actual_package` raises
      ModuleNotFoundError for hermes_cited_installed.plugin on an isolated copy of the actual layout.
      GREEN: `.venv/Scripts/python -m pytest -q -p no:cacheprovider ../tasks/test_bridge_r2_adversarial.py
      -k installed_layout`: 1 passed, 18 deselected in 0.87s; `tests/test_profile_install.py`:
      14 passed, 1 skipped in 0.27s. This import repair does not complete the VM/catalog/digest gate.
      External evidence: `bridge-r2-fix-layout.log`, `bridge-r2-layout-regression.log`.
- [x] 10.5 H21: reject embedded URL control characters before urlsplit can remove them.
      RED: two external R2 `control_characters` cases reached the transport with a silently changed host.
      GREEN: `.venv/Scripts/python -m pytest -q -p no:cacheprovider ../tasks/test_bridge_r2_adversarial.py
      -k control_characters`: 2 passed, 17 deselected in 0.57s; `tests/test_search_wire.py
      -k 'url or origin'`: 10 passed, 59 deselected in 5.38s.
      External evidence: `bridge-r2-fix-origin.log`, `bridge-r2-origin-regression.log`.
- [x] 10.6 Wire v1: validate method types and close the fake's tools/call params object.
      RED: five external R2 `new_closed_wire` cases accepted extra params or returned -32601 with
      a non-null id for a null, number, array or object method instead of HTTP 400/-32600/id null.
      GREEN: `.venv/Scripts/python -m pytest -q -p no:cacheprovider ../tasks/test_bridge_r2_adversarial.py
      -k new_closed_wire`: 5 passed, 14 deselected in 4.63s; `tests/test_chassis_fake.py`:
      16 passed in 8.40s. External evidence: `bridge-r2-fix-wire.log`, `bridge-r2-wire-regression.log`.
- [x] 10.7 Reopen unsupported completion claims without erasing historical reports.
      RED: `.venv/Scripts/python -m pytest -q -p no:cacheprovider ../tasks/test_bridge_r2_adversarial.py
      -k checked_tasks`: 1 failed, 20 deselected in 3.08s (`bridge-r2-tasks-red.log`).
      Independent R2 evidence supersedes the earlier "Closed in R2" statements above:
      1.1/9.4: a real HTTP call makes the fake write a log outside the only registered workspace,
      even though guard_path rejects the same path (`bridge-r2-guard-red.log`).
      1.3/2.3/6.2/9.8: the full callbacks use root defaults, quote another profile's passage and
      prepare an audit write after a scope switch. The pinned real secret_scope reproduces all three
      (`bridge-r2-real-scope.log`). Registration safety alone does not prove every callback safe.
      1.4/9.6: the import-path defect is fixed, but the runner still uses FakeContext rather than the
      host catalog and does not verify the host pin or canonical archive digest. Task 5.3 remains unrun.
      Documentation must state that these gates are open; the approved D2/D4/H19/H22 requirements remain intact.
      GREEN: the same `-k checked_tasks` command returned 1 passed, 20 deselected in 2.05s
      (`bridge-r2-tasks-green.log`); `openspec validate --all --strict`: 2 passed, 0 failed.

## 11. Round 3 review corrections
- [ ] 11.1 B01 — bind every full callback and its turn state to the registering profile (D2/H19/H20/H21).
      `plugin._profile_call` validates the scope and reads its settings before an effect; `hermes_home`,
      `_secret` and `_language` resolve through the call in progress; `_ProfileState` scopes `ctx.state` per
      profile; `Turn.home` plus the explicit home of each callback keeps a turn visible only to its profile.
      RED: `.venv/Scripts/python -m pytest -q -p no:cacheprovider tests/test_profile_callbacks.py` 7 failed
      (root default mode, root language, command language, cross-profile quote, transform after a switch,
      root audit path, shared mode state); the run is in `tasks/bridge-r3-red.log`. GREEN: the same command
      7 passed in 0.26s.
      Evidence: `reports/2026-10-12-step-11-callbacks-r3.md`.
      Reclosed in R4: the third review's independent probes are ported as
      `tests/test_round4_amendments.py`; the colliding turn opens per home, the refused foreign callback
      performs no cleanup and the command/transformer diagnostics keep the profile redaction set. RED 7 failed
      → GREEN 7 passed in 2.52s; `tests/test_profile_callbacks.py` 9 passed in 0.74s. Evidence:
      `reports/2026-10-13-step-13-r4-core.md`.
- [x] 11.2 B01 — reproduce the three paths over the real pinned `agent.secret_scope`.
      `.venv/Scripts/python ../tasks/bridge-r2-real-scope.py`: the pre-hook takes `cited` from profile A, one
      request reaches A's URL, the quote after the switch to B answers the redacted scope sentence, and the
      captured audit writes are `[]` (before: root default, profile A's passage, one prepared write).
      Evidence: `reports/2026-10-12-step-11-callbacks-r3.md`.
- [x] 11.3 M02 — apply the isolation guard before every effect of the fake and its CLI.
      `start_chassis` guards `--port` and `--record`, `ChassisFake.__init__` guards the record path and the
      script's `main` runs `prepare_cli_guard` before opening the server; a `--record` under the process
      temporary directory authorises only its own parent, never all of `tempfile.gettempdir()`. RED: two cases
      failed (`start_chassis(log_path=outside)` and `main --record outside` started the server and created the
      file). GREEN: `.venv/Scripts/python -m pytest -q -p no:cacheprovider tests/test_search_guard.py` 31
      passed in 3.24s. The 5.1 curl probe still runs the fake as a subprocess: 6 cases correct, port closed,
      home inventory identical (`tasks/bridge-r3-curl.log`). Evidence:
      `reports/2026-10-12-step-11-guard-r3.md`.
- [x] 11.4 M01 — complete the D4/H22 runner. `_check_host_pin` proves the CLI is the pinned host checkout,
      `_read_bridge_lock`/`_canonical_archive`/`_verify_bridge_lock` compare the SHA-256 and byte size of
      `git archive --format=tar` with the lock under D5's isolated Git configuration, and `_effective_catalog`
      asks the real host loader and the real registry for the effective catalog and a scoped dispatch. RED:
      `.venv/Scripts/python ../tasks/bridge-r3-m01-red.py` reports all six verifications missing from HEAD
      (exit 1). GREEN: `.venv/Scripts/python -m pytest -q -p no:cacheprovider tests/test_profile_install.py`
      29 passed, 1 skipped in 1.61s (the VM E2E is the skip). Evidence:
      `reports/2026-10-12-step-11-install-r3.md`.
      Reclosed in R4: the D9 runner actually establishes the whole integration offline — provisioned managed
      runtimes and build wheelhouse, closed external network, real install with `--enable`, real loader
      catalog, scoped dispatch and full post-setup inventory comparison. `1 passed, 29 deselected in 264.38s`.
      Evidence: `reports/2026-10-13-step-13-install-r4.md`.
- [x] 11.5 Re-run the independent R2 probe after the corrections.
      `.venv/Scripts/python -m pytest -q -p no:cacheprovider ../tasks/test_bridge_r2_adversarial.py`: before
      4 failed, 17 passed; after 21 passed in 6.02s. `.venv/Scripts/python -m pytest -q -p no:cacheprovider
      tests/test_plugin.py tests/test_modes.py tests/test_host.py tests/test_adversarial.py
      tests/test_profile_scope.py tests/test_search_only_mode.py`: 173 passed in 84.29s.
      Evidence: `reports/2026-10-12-step-11-callbacks-r3.md`.
- [ ] 11.6 6.2 — the living context and the documents state the per-callback binding with no drift.
      `openspec/config.yaml` carries the rule; `docs/technical-manual.md`, `README.md` and `README.es.md` state
      it. `.venv/Scripts/python -m pytest -q -p no:cacheprovider tests/test_docs_bridge.py
      tests/test_manifest_modes.py`: 16 passed; `openspec validate --all --strict`: 2 passed, 0 failed.
      Evidence: `reports/2026-10-12-step-11-config-r3.md`.
      Reclosed in R4: the living context and the manuals now state the `(home, session, turn)` key, the plain
      `mode.profile` key, the failing profile's redaction and the offline runtime provisioning; the D6-D9
      documents agree with the implementation. Evidence: `reports/2026-10-13-step-13-r4-core.md` and
      `reports/2026-10-13-step-13-install-r4.md`.
- [x] 11.7 Full suite with counts and runtime, and `gitleaks protect --staged` before every commit of this
      round. `.venv/Scripts/python -m pytest -q`: 898 passed, 4 skipped in 314.14s (0:05:14);
      `openspec validate --all --strict`: 2 passed, 0 failed; gitleaks clean before each commit.
      Evidence: `reports/2026-10-12-step-11-suite-r3.md`.

## 12. Independent round 3 review corrections
- [x] 12.1 H22/D4: run the real catalog subprocess with the supplied profile as HERMES_HOME.
      RED: external `test_bridge_codex_r3.py -k new_catalog_probe`, executed through
      `../tasks/bridge-codex-r3-run.py`: the real pinned loader discovers no hermes-cited plugin and
      dispatch returns Unknown tool: cited_search. Evidence: `bridge-codex-r3-real-red.log` outside
      the repository. Preserve the profile scope and test a successful real dispatch after correction.
      GREEN: `.venv/Scripts/python ../tasks/bridge-codex-r3-run.py bridge-codex-r3-fix-catalog
      .venv/Scripts/python.exe -m pytest -q -s -p no:cacheprovider ../tasks/test_bridge_codex_r3.py
      -k new_catalog_probe`: 1 passed, 12 deselected in 4.45s. The real catalog has one search tool,
      zero full hooks and a successful scoped HTTP call. This is loader integration, not the VM install.
- [x] 12.2 D4: reject tracked host modifications even when HEAD still equals the expected pin.
      RED: `test_bridge_codex_r3.py -k host_pin_rejects_modified` accepts a changed tracked file;
      `bridge-codex-r3-real-red.log` records DID NOT RAISE. This check validates checkout cleanliness,
      not the provenance of executables installed in the host venv.
      GREEN: `.venv/Scripts/python ../tasks/bridge-codex-r3-run.py bridge-codex-r3-fix-host
      .venv/Scripts/python.exe -m pytest -q -p no:cacheprovider ../tasks/test_bridge_codex_r3.py
      -k host_pin_rejects_modified`: 1 passed, 12 deselected in 1.87s.
- [x] 12.3 D5: reject an effective tar.umask override before creating a canonical archive.
      RED: external `test_bridge_codex_r3.py -k archive_digest` computes different SHA-256 values
      for the same commit after `git config tar.umask 0077`; both archives have 10240 bytes.
      Evidence: `bridge-codex-r3-real-red.log`. The contract explicitly forbids this override.
      GREEN: `.venv/Scripts/python ../tasks/bridge-codex-r3-run.py bridge-codex-r3-fix-archive
      .venv/Scripts/python.exe -m pytest -q -p no:cacheprovider ../tasks/test_bridge_codex_r3.py
      -k archive_digest`: 1 passed, 12 deselected in 3.37s.
- [x] 12.4 D5: require the lock byte size to be an integer without numeric coercion.
      RED: external `test_bridge_codex_r3.py -k lock_size` accepts 10240.75 as 10240 bytes.
      Evidence: `bridge-codex-r3-real-red.log` records DID NOT RAISE.
      GREEN: `.venv/Scripts/python ../tasks/bridge-codex-r3-run.py bridge-codex-r3-fix-size
      .venv/Scripts/python.exe -m pytest -q -p no:cacheprovider ../tasks/test_bridge_codex_r3.py
      -k lock_size`: 1 passed, 12 deselected in 1.61s.
- [x] 12.5 Task 1.1: never implicitly register the whole system temporary directory for --record.
      RED: `test_bridge_codex_r3.py -k cli_record`: 1 failed, 13 deselected in 3.66s;
      prepare_cli_guard accepts a file directly under the temporary root and registers that root.
      Evidence: `bridge-codex-r3-guard-red.log`. No file or server is created by this predicate probe.
      GREEN: `.venv/Scripts/python ../tasks/bridge-codex-r3-run.py bridge-codex-r3-fix-guard
      .venv/Scripts/python.exe -m pytest -q -p no:cacheprovider ../tasks/test_bridge_codex_r3.py
      -k cli_record`: 1 passed, 13 deselected in 1.43s. Regression: `pytest -q -p no:cacheprovider
      tests/test_search_guard.py tests/test_chassis_fake.py`: 47 passed in 9.29s.
- [x] 12.6 Wire v1: return 405 for unsupported HTTP methods in the fake.
      RED: new external `bridge-codex-r3-curl.py` receives 501 for PATCH, DELETE and HEAD where
      wire-contract.md requires 405. Five other new cases pass. `bridge-codex-r3-curl-red.log`
      records the requests, response bodies, stopped PID, closed port and unchanged home inventory.
      GREEN: `.venv/Scripts/python ../tasks/bridge-codex-r3-run.py bridge-codex-r3-curl-green
      .venv/Scripts/python.exe ../tasks/bridge-codex-r3-curl.py`: exit 0, eight cases passed in 3.11s.
      Evidence for 5.1 and this correction: `reports/2026-10-12-step-12-curl-codex-r3.md`.
- [x] 12.7 Reopen completion statements contradicted by independent round 3 executions.
      RED: `.venv/Scripts/python ../tasks/bridge-codex-r3-run.py bridge-codex-r3-tasks-red
      .venv/Scripts/python.exe -m pytest -q -p no:cacheprovider ../tasks/test_bridge_codex_r3.py
      -k tasks_do_not`: 1 failed, 15 deselected in 4.31s.
      11.1/11.6 remain open: the new real-secret-scope probes reproduce a colliding live turn,
      deletion of the owner's turn by a refused foreign transformer and profile-token disclosure in
      command/transformer exception diagnostics. The real PluginState rejects the home/NUL key prefix,
      so /cited does not change the mode; legacy persisted mode keys are also ignored. See external
      `bridge-codex-r3-real-red.log`, `bridge-codex-r3-state-red.log` and the independent review.
      11.4 remains open: its original catalog never ran and discovered the wrong home when executed.
      The small helper repairs are measured in 12.1-12.4; they do not by themselves close installation.
      The earlier Reclosed in R3 and no-drift statements are historical and superseded by this entry.
      The approved specifications remain unchanged. Product changes across these scope/state/failure
      boundaries belong to the next implementation round; Codex's small corrections require Fable review.
      GREEN: `.venv/Scripts/python ../tasks/bridge-codex-r3-run.py bridge-codex-r3-tasks-green
      .venv/Scripts/python.exe -m pytest -q -p no:cacheprovider ../tasks/test_bridge_codex_r3.py
      -k tasks_do_not`: 1 passed, 15 deselected in 15.05s. The complete independent probe then reports
      6 failed, 10 passed in 11.30s; failures are open product defects, not waived assertions.
      Task 5.3 now records its actual Linux CLI failure instead of claiming missing prerequisites.
      Command: `/opt/chassis/.venv/bin/python -m pytest -vv -s --showlocals -p no:cacheprovider
      tests/test_profile_install.py -k a_fresh_real_profile_installs`: 1 failed, 29 deselected in 37.10s.
      External supervisor `bridge-codex-r3-run.py bridge-codex-r3-linux-native9 docker run ...`
      records exit 1, 92.38s, unchanged outer home and process_stopped=true. The exact argv and
      independent integration evidence are in `reports/2026-10-12-step-12-install-codex-r3.md`.

## 13. Round 4 implementation (contract amendment D6-D10 by Fable, 2026-10-12)
- [x] 13.0 Read the third review and design D6-D10 before any code. Port the six failing external probes of the
      third review (owner collision, refused foreign callback, real PluginState keys, persisted mode, command and
      transformer diagnostics) into `tests/` as RED regression cases that use the real `agent.secret_scope` and the
      real `PluginState` of the pinned host; record the red run in a report.
      `tests/test_round4_amendments.py` ports the six probes plus the D7 invalid-key case with the real host of
      pin `dce1e9b37581dd62e480a9064dc04a709c2940d3`. RED:
      `.venv/Scripts/python -m pytest -q -p no:cacheprovider tests/test_round4_amendments.py` 7 failed in 3.88s.
      Evidence: `reports/2026-10-13-step-13-r4-core.md`.
- [x] 13.1 D8 (B01-R3): diagnostics redacted with the failing profile's set. `tests/test_profile_callbacks.py`
      captures every log record and asserts that no synthetic profile secret appears in messages or tracebacks.
      GREEN with counts.
      `_report_failure`/`_sanitized_diagnostic` accept the explicit profile secret and the command, transformer,
      post-tool and quote callbacks hand it over. GREEN:
      `.venv/Scripts/python -m pytest -q -p no:cacheprovider tests/test_profile_callbacks.py` 9 passed in 0.74s.
      Evidence: `reports/2026-10-13-step-13-r4-core.md`.
- [ ] 13.2 D6 (M01-R3): turn table keyed by (home, session, turn); refusal before any turn access; cleanup only of
      the owned turn; eviction and migration on the same key. GREEN for both H19 scenarios plus the H14 regressions.
      `_find_turn_locked`/`_turn_of`/`_drop_turn` use the composite key and `_transform_llm_output` validates before
      any turn access and drops only when the call passed validation. GREEN: 286 passed in 140.99s (callbacks and
      regressions) and 92 passed, 1 skipped in 73.36s (host, scope, search and install). Evidence:
      `reports/2026-10-13-step-13-r4-core.md`.
- [x] 13.3 D7 (M02-R3): plain `mode.profile` key through the real PluginState; no path or NUL prefix; `get` never
      hides a host validation error; the legacy value is honoured after the upgrade; `/cited` and `/dot` persist.
      GREEN with the real host state.
      `_ProfileState` delegates the plain key and no longer swallows a key error. GREEN:
      `.venv/Scripts/python -m pytest -q -p no:cacheprovider tests/test_round4_amendments.py` 7 passed in 2.52s.
      Evidence: `reports/2026-10-13-step-13-r4-core.md`.
- [x] 13.4 D9 (M03-R3): offline provisioning of the host's required runtimes in the Linux runner (versions and
      digests recorded), network closed, install completes, catalog and scoped dispatch verified, full profile
      inventory compared with the post-setup baseline (`tests/test_profile_install.py` compares the whole profile,
      not only `cited/`). Re-run 5.3 and record it; a download attempt is a failure, not a skip.
      Provisioned CPython `3.14.7+20260901` (sha256 `0ab330…`) and uv `0.12.3` (sha256 `600cf9…`) before closing
      the network, warmed the uv cache with the real install and served the build-backend wheelhouse on a
      loopback-only index; the managed runtimes live in `/opt/runtime` via `HERMES_RUNTIME_DIR`. Offline run:
      `external_connect_refused: true`, mirror read-only, catalog `hermes-cited` enabled with `tools: 1`,
      `hooks: 0`, `commands: 0`, scoped dispatch answered, and the full profile inventory identical after setup.
      `1 passed, 29 deselected in 264.38s`; container exit 0, 301.95s, removed. Evidence:
      `reports/2026-10-13-step-13-install-r4.md`.
- [ ] 13.5 Close 11.1, 11.4 and 11.6 only with the evidence of 13.1-13.4; update the living context and the manuals
      where D6-D9 changed behaviour; `openspec validate --all --strict` green.
      11.1 closed with 13.1/13.2; 11.4 with 13.4; 11.6 with the context/manual updates below. `openspec/config.yaml`,
      `docs/technical-manual.md`, `README.md` and `README.es.md` state the `(home, session, turn)` key, the plain
      `mode.profile` key, the failing profile's redaction and the offline provisioning.
      `tests/test_docs_bridge.py tests/test_manifest_modes.py`: 16 passed; `openspec validate --all --strict`:
      2 passed, 0 failed. Evidence: `reports/2026-10-13-step-13-r4-core.md`,
      `reports/2026-10-13-step-13-install-r4.md`.
- [x] 13.6 Full suite with counts and runtime; `gitleaks protect --staged` before every commit; no `tasks/` inside
      the repository; delivery with `## Issues`.
      `.venv/Scripts/python -m pytest -q -p no:cacheprovider`: 910 passed, 1 skipped in 339.03s (0:05:39);
      `openspec validate --all --strict`: 2 passed, 0 failed; `gitleaks protect --staged`: no leaks before each
      commit; no `tasks/` inside the repository. Evidence: `reports/2026-10-13-step-13-r4-core.md` and
      `reports/2026-10-13-step-13-install-r4.md`.

## 14. Bridge2 round 1 independent review corrections
- [x] 14.1 H6: redact invalid quote selection diagnostics with the validated profile credential.
      New external probe: `../tasks/test_bridge2_codex_r1.py::test_invalid_quote_line_does_not_echo_profile_credential`.
      RED: `.venv/Scripts/python -m pytest -q -s -p no:cacheprovider ../tasks/test_bridge2_codex_r1.py`
      returns the synthetic profile credential in the invalid-line sentence. External evidence:
      `C:/Users/Franc/Documents/katalis-dev/tasks/bridge2-codex-r1-probes-validated-red.log`.
      GREEN: the same pytest command with `-k invalid_quote_line`: 1 passed, 11 deselected in 7.35s;
      `bridge2-codex-r1-fix-quote.log` records the redacted sentence and an unchanged temporary home.
- [x] 14.2 D8/H6: contain and redact unexpected pre-hook exceptions before the real host dispatcher logs them.
      RED: the external probe `test_pre_hook_exception_is_sanitized_before_host_dispatch_logs_it` runs the
      pinned host dispatcher and finds the synthetic profile credential in its warning. Command and output:
      `C:/Users/Franc/Documents/katalis-dev/tasks/bridge2-codex-r1-probes-validated-red.log`.
      GREEN: `.venv/Scripts/python -m pytest -q -s -p no:cacheprovider ../tasks/test_bridge2_codex_r1.py
      -k pre_hook_exception`: 1 passed, 11 deselected in 1.45s; external `bridge2-codex-r1-fix-prehook.log`.
- [x] 14.3 H21: reject non-string argument keys before sorting unknown search properties.
      RED: the external probe `test_search_mixed_nonstring_unknown_keys_return_sentence` raises TypeError
      for mixed string/integer keys before the transport boundary. This is a native Python handler edge
      case; JSON objects cannot carry integer keys. Command/output: `bridge2-codex-r1-probes-validated-red.log`.
      GREEN: `.venv/Scripts/python -m pytest -q -s -p no:cacheprovider ../tasks/test_bridge2_codex_r1.py
      -k mixed_nonstring`: 1 passed, 11 deselected in 0.93s; external `bridge2-codex-r1-fix-keys.log`.
- [x] 14.4 Update the existing mode-resolution regression for D8's contained pre-hook failure.
      Keep every transformer assertion: operational refusal, nonempty result, no model prose and no seal.
      RED: `.venv/Scripts/python -m pytest -q -p no:cacheprovider tests/regressions/test_r4_transformer.py
      -k mode_resolution_failure`: 1 failed, 9 deselected in 0.70s, because it expects the unsafe exception
      to escape the pre-hook. External evidence: `bridge2-codex-r1-prehook-regression-red.log`.
      GREEN: the same pytest command without `-k`, running the whole file: 10 passed in 5.60s;
      external `bridge2-codex-r1-prehook-regression-green.log`.
- [x] 14.5 Reconcile completion flags with the new independent turn counterexamples and the measured
      HTTP/install evidence. Preserve historical reports, reopen unsupported D6/H14 closure and close
      stale guard/install flags only with executions. The new external evidence consistency probe is RED:
      `.venv/Scripts/python -m pytest -q -p no:cacheprovider ../tasks/test_bridge2_codex_r1_evidence.py`
      gives 1 failed in 1.28s (`bridge2-codex-r1-evidence-red.log`).
      Bridge2 R1 reopens 11.1, 11.6, 13.2 and 13.5: a validated foreign profile opening 64 turns evicts
      the owner's live evidence, and an explicit unmatched turn identifier selects the sole different
      live turn. These supersede the R4 statements of complete D6/H14 implementation; the earlier
      specific collision, refusal and persisted-state executions remain historical evidence.
      `.venv/Scripts/python -m pytest -q -s -p no:cacheprovider ../tasks/test_bridge2_codex_r1.py`:
      2 failed, 10 passed in 7.22s. External `bridge2-codex-r1-probes-final.log` contains both counterexamples.
      Independent integration: `reports/2026-10-13-step-14-integration-codex.md`. Eight new curl cases pass,
      with the owned server terminated and its port verified closed. The real offline install at product
      commit 9a5066a passes (1 passed, 29 deselected in 291.99s), with the full 266-file profile inventory
      unchanged after setup and the container removed. This refreshes 5.1/5.3 and closes 1.4/9.6.
      `pytest -q -p no:cacheprovider tests/test_chassis_fake.py tests/test_search_guard.py
      tests/test_manifest_modes.py tests/test_docs_bridge.py`: 63 passed in 13.37s; closes 1.1/9.4 using
      their historical RED reports plus the current guard execution. `bridge2-codex-r1-sdd.py` confirms
      17 valid modified requirements, 4 additions, unique merged H0-H22, identical counterpart wire bytes
      and no normative drift from Fable's f59ab76. The remaining old closure notes do not override the
      reopened turn tasks above.
      GREEN: `.venv/Scripts/python -m pytest -q -p no:cacheprovider ../tasks/test_bridge2_codex_r1_evidence.py`:
      1 passed in 1.18s; external `bridge2-codex-r1-evidence-green.log`.
