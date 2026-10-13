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
- [ ] 1.1 Write RED `tests/test_search_guard.py`: all effective URLs, sockets and redirect destinations reject
      ports 3240/3241, localhost aliases and IPv6 equivalents; canonical paths reject the personal installation,
      symlinks/junction escapes and anything outside the registered temporary workspace. Missing overrides fail
      before file/process/network effects. Then implement the test guard and record RED/GREEN.
- [ ] 1.2 Write `tests/fakes/chassis_surface.py` for wire v1 on a guarded free loopback port, including tools/list,
      every error and both redirect classes. No real provider is used. Add a script entry accepting --port and
      --record in this test file for the curl checks below.
- [ ] 1.3 RED `tests/test_search_only_mode.py`, `tests/test_profile_scope.py`, `tests/test_search_wire.py` for every
      H19-H21 scenario and Mapping access spies. Record before/after including failure paths.
- [ ] 1.4 RED `tests/test_manifest_modes.py`, `tests/test_profile_install.py`, and README/manual tests for H22;
      preserve full regression cases H12-H18 and check unique IDs on a temporary synchronized spec copy.
- [ ] 1.5 `pytest -q tests/test_search_guard.py tests/test_search_only_mode.py tests/test_profile_scope.py
      tests/test_search_wire.py tests/test_manifest_modes.py` before implementation; record intended failures.

## 2. Small implementation steps
- [ ] 2.1 config.py: scoped accessor, immutable registration mode, selected credential and timeout validation.
- [ ] 2.2 client.py/tools.py: search-only strict arguments, wire v1 endpoint, response validation and redaction;
      retain full behavior. Do not coerce booleans, numbers or fractional limits in search.
- [ ] 2.3 plugin.py: search registration with one handler bound to its profile identity, no shared settings cache.
- [ ] 2.4 plugin.yaml: implement fixtures/plugin-search.yaml semantics and version 0.2.0.

## 3. Review existing tests
- [ ] 3.1 Run full-mode H0-H18 regression suite, list every existing test updated and why; preserve delivery policy.

## 4. Unit verification and state
- [ ] 4.1 `pytest -q` with counts/runtime and complete before/after home inventory. No database test is invented.
- [ ] 4.2 `openspec validate --all --strict`; compare both wire copies by SHA-256; run existing CI commands from
      .github/workflows without claiming remote CI has run. Record the actual workflow SHA/result when available.

## 5. Agent-executed HTTP and profile integration
- [ ] 5.1 Set PYTHONDONTWRITEBYTECODE=1 for isolated handler/profile tests. Start `python tests/fakes/chassis_surface.py --port <guarded-free-port> --record <temporary-log>`;
      from Windows run `curl.exe --max-time 30 --request POST http://127.0.0.1:<port>/api/chassis/mcp
      --header "Content-Type: application/json" --header @<synthetic-header.txt>
      --data-binary @<fixture-request.json>` (fixture's request object only). The temporary header file holds the synthetic search bearer; remove it after
      the run and never include it in reports. Repeat tools/list, wrong token,
      wrong tool and invalid limits. Paste redacted requests/results, stop only the owned fake.
- [ ] 5.2 `pytest -q tests/test_search_only_mode.py -k handler_wire -s` must call the registered handler, compare
      its actual wire with the same fixture, capture output and prove no home writes. Create that named case in 1.3.
- [ ] 5.3 Run `pytest -q tests/test_profile_install.py -s` in the disposable VM using D4's CLI, pinned Hermes,
      local mirror and isolated homes; no personal executable or service. Test real scoped registration and catalog.
      Network is blocked after provisioning. Record CLI argv, digest and profile inventory.
- [ ] 5.4 Playwright: not applicable, this change has no frontend.

## 6. Documentation
- [ ] 6.1 Update README.md, README.es.md and docs/technical-manual.md with modes, scope failures, conditional
      secrets, complete wire, no writes, per-profile install and canonical pin command.
- [ ] 6.2 Verify openspec/config.yaml against implementation; update schema/fixture consumers, never silently drift.

## 7. Implementation closing (not executed by this contract correction)
- [ ] 7.1 `/verify`, then independent `/adversarial-review`; resolve Blockers/Majors and re-verify corrections.
- [ ] 7.2 Automated tests and CI green for the delivering SHA; `gitleaks protect --staged` before every commit.
- [ ] 7.3 `/archive` with explicit owner approval, then `/commit`; merge/push require a separate authorization.
- [ ] 7.4 After the authorized merge, record full merge SHA, SHA-256 and byte size of
      `git archive --format=tar <sha>` without prefix/gzip for A's bridge.lock. Never use this spec commit as a
      completed bridge pin. Update the consuming lock in a later commit.
