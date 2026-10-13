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
- [x] 1.2 Write `tests/fakes/chassis_surface.py` for wire v1 on a guarded free loopback port, including tools/list,
      every error and both redirect classes. No real provider is used. Add a script entry accepting --port and
      --record in this test file for the curl checks below.
      Evidence: `reports/2026-10-12-step-1-red.md`, `reports/2026-10-12-step-5-http.md`.
- [x] 1.3 RED `tests/test_search_only_mode.py`, `tests/test_profile_scope.py`, `tests/test_search_wire.py` for every
      H19-H21 scenario and Mapping access spies. Record before/after including failure paths.
      Evidence: `reports/2026-10-12-step-1-red.md`, `reports/2026-10-12-step-2-implementation.md`.
- [x] 1.4 RED `tests/test_manifest_modes.py`, `tests/test_profile_install.py`, and README/manual tests for H22;
      preserve full regression cases H12-H18 and check unique IDs on a temporary synchronized spec copy.
      Evidence: `reports/2026-10-12-step-1-red.md`, `reports/2026-10-12-step-6-docs.md`.
- [x] 1.5 `pytest -q tests/test_search_guard.py tests/test_search_only_mode.py tests/test_profile_scope.py
      tests/test_search_wire.py tests/test_manifest_modes.py` before implementation; record intended failures.
      Evidence: `reports/2026-10-12-step-1-red.md` (104 failed, 34 passed, 1 skipped).

## 2. Small implementation steps
- [x] 2.1 config.py: scoped accessor, immutable registration mode, selected credential and timeout validation.
      Evidence: `reports/2026-10-12-step-2-implementation.md`.
- [x] 2.2 client.py/tools.py: search-only strict arguments, wire v1 endpoint, response validation and redaction;
      retain full behavior. Do not coerce booleans, numbers or fractional limits in search.
      Evidence: `reports/2026-10-12-step-2-implementation.md`, `tests/test_search_wire.py`.
- [x] 2.3 plugin.py: search registration with one handler bound to its profile identity, no shared settings cache.
      Evidence: `reports/2026-10-12-step-2-implementation.md`, `tests/test_search_only_mode.py`.
- [x] 2.4 plugin.yaml: implement fixtures/plugin-search.yaml semantics and version 0.2.0.
      Evidence: `reports/2026-10-12-step-2-implementation.md`, `tests/test_manifest_modes.py`.

## 3. Review existing tests
- [x] 3.1 Run full-mode H0-H18 regression suite, list every existing test updated and why; preserve delivery policy.
      Evidence: `reports/2026-10-12-step-3-regression.md` (502 passed, 3 skipped; only the manifest test updated).

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
- [BLOCKED] 5.3 Run `pytest -q tests/test_profile_install.py -s` in the disposable VM using D4's CLI, pinned Hermes,
      local mirror and isolated homes; no personal executable or service. Test real scoped registration and catalog.
      Network is blocked after provisioning. Record CLI argv, digest and profile inventory.
      BLOCKED: the disposable VM does not exist in this run (no pinned Hermes CLI and no local read-only mirror);
      `test_a_fresh_real_profile_installs_the_search_bridge` is skipped with that explicit reason. Evidence:
      `reports/2026-10-12-step-5-http.md`.
- [x] 5.4 Playwright: not applicable, this change has no frontend.
      Evidence: `reports/2026-10-12-step-5-http.md`.

## 6. Documentation
- [x] 6.1 Update README.md, README.es.md and docs/technical-manual.md with modes, scope failures, conditional
      secrets, complete wire, no writes, per-profile install and canonical pin command.
      Evidence: `reports/2026-10-12-step-6-docs.md`.
- [x] 6.2 Verify openspec/config.yaml against implementation; update schema/fixture consumers, never silently drift.
      Evidence: `reports/2026-10-12-step-6-docs.md` (no drift found; no edit needed).

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
