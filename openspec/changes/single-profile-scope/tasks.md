# Tasks: single-profile-scope

Branch `feature/single-profile-scope` from `main` at `58fa6cd`. Every report lives in `reports/` with the exact
command, its output, the SHA and the agent. A task is `[x]` only with evidence. No plugin database exists: the
real-host probe runs in a temporary `HERMES_HOME` and never opens the personal installation or a socket.

## 0. Branch

- [x] 0.1 `git switch -c feature/single-profile-scope` from `main`. Evidence: [step 1](reports/2026-10-21-step-1-tdd.md).

## 1. TDD

- [x] 1.1 Write `tests/test_single_profile_scope.py` (stand-in host: installed scope, single profile, multiplexing,
      a task routed to another profile, host without the builder, blank home, failing builder, non-mapping,
      rotation, explicit scope) and run it red against the unpatched `config.py`. Evidence:
      [step 1](reports/2026-10-21-step-1-tdd.md): 4 failed, 8 passed before the code; 42 passed after.
- [x] 1.2 Write `tests/test_single_profile_host.py`, the opt-in probe of the real modules of v0.22.4 in a
      subprocess, and add `tui_gateway` to the host namespaces of `tests/conftest.py`. Evidence:
      [step 5](reports/2026-10-21-step-5-real-host.md).

## 2. Implementation

- [x] 2.1 `hermes_cited/config.py`: the `values is None` branch of `active_scope()` and `_single_profile_scope()`,
      which refuses the missing scope while multiplexing is active or the task is routed to another profile.
      Evidence: [step 1](reports/2026-10-21-step-1-tdd.md).

## 3. Existing tests

- [x] 3.1 Run `tests/test_profile_scope.py` and update the docstring of `test_a_missing_host_scope_registers_nothing`
      to say its stand-in is a host without the builder. Evidence: [step 1](reports/2026-10-21-step-1-tdd.md), 26 cases green.

## 4. Unit verification

- [x] 4.1 `python -m pytest -q` (whole suite) with counts and runtime. Evidence:
      [step 4](reports/2026-10-21-step-4-validation.md): 946 passed, 6 skipped (581.70 s) before the routed-task
      refusal; 948 passed, 6 skipped (399.24 s) on the final tree.
- [x] 4.2 `npx --yes @fission-ai/openspec@1.1.1 validate --all --strict`. Evidence:
      [step 4](reports/2026-10-21-step-4-validation.md): `Totals: 2 passed, 0 failed (2 items)`, after one rewording
      of H23 so its first line carries the SHALL the validator reads.

## 5. Real host

- [x] 5.1 `tests/test_single_profile_host.py` against the shallow clone of tag `v0.22.4` (commit `4d043038`) with an
      interpreter that has `ruamel.yaml`; record what the probe proved. Evidence:
      [step 5](reports/2026-10-21-step-5-real-host.md), 2 passed; skipped with its reason without the clone.

## 6. Documentation

- [x] 6.1 `README.md` and `README.es.md`: Requirements, the scope paragraph of the mode switch and Host
      incompatibilities. `docs/technical-manual.md` section 2. `openspec/config.yaml` context. Evidence:
      [step 6](reports/2026-10-21-step-6-docs.md).

## 7. Closure

- [ ] 7.1 Pull request against `main` with the `tests` workflow green on Ubuntu and Windows; record the run.
- [ ] 7.2 Independent adversarial review recorded in `reports/`; Fable implemented, so Fable does not review.
- [ ] 7.3 Merge and archive belong to Franc.
