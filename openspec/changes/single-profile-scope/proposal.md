# single-profile-scope

The plugin honours the single-profile contract of Hermes 0.22: when the host binds no secret scope because it
serves one profile, the configuration comes from the launch profile the host itself builds; when the host
multiplexes profiles, a missing scope stays refused. Nothing else changes.

## Why

Hermes Agent 0.22 binds no secret scope while a process serves a single profile. In v0.22.4 (upstream commit
`4d04303818b61bf3aa09278af48356315515965b`) `tui_gateway/launch_profile_policy.py` says it in `launch_body`
("Nothing is bound while single-profile, so its reads keep the process-env semantics they always had"), and the
host's own accessor `agent/secret_scope.py:get_secret` reads the process environment when no scope is bound and
multiplexing is inactive, raising `UnscopedSecretError` only once a second profile is served. The isolated plugin
host (`hermes_cli/plugin_host.py`) binds a profile scope only `if is_multiplex_active()`.

Plugin 0.2.0 was written against v0.21.6 (`dce1e9b`), where a profile scope was always present, and H19/D2 made a
missing scope fail closed. On the Hermes 0.22.4 of the Katalis server the plugin therefore refused to register with
"no readable secret scope", although the profile's `.env` held every value. The fix ran there as a local patch on
2026-10-21 (`katalis-dev/tasks/hotfix-diffs/hermes-cited-single-profile.diff`). This change makes it a formal one.

Authorized scope: the brief of Fable's session of 2026-10-21, which names the diff, the host contract to document
(pin v0.22.4, commit `4d043038`), the three cases to test and the two README sections to update. Fable specifies
and implements as a recorded exception to the separation of roles, as in `mcp-initialize-version-header` of Cited;
the adversarial review belongs to an independent reviewer and is recorded in `reports/`; Franc merges.

## What changes

- `active_scope()` in `hermes_cited/config.py`: when `current_secret_scope()` answers `None`, and only then, the
  plugin consults the host. If `is_multiplex_active()` is false it builds its `ProfileScope` with
  `owner_secret_scope(get_process_hermes_home())` of `tui_gateway.launch_profile_policy`, the mapping the host binds
  for every launch-profile body (`<HERMES_HOME>/.env` over the launch environment), with the process home as the
  profile home, no host getter and source `hermes`. If multiplexing is active the missing scope is refused, as
  before. A host without that builder (0.21), a blank process home, a builder that raises or answers a non-mapping
  are refused with the same redacted sentence.
- H19 is modified so that a missing scope sends zero requests *while multiplexing is active*; H23 is added with the
  contract above and its scenarios.
- Tests: `tests/test_single_profile_scope.py` (a stand-in host, the three cases and their failures) and
  `tests/test_single_profile_host.py` (opt-in, the real modules of v0.22.4 in a subprocess).
- Documentation: `README.md` and `README.es.md` (Requirements, the scope paragraph of the mode switch and Host
  incompatibilities), `docs/technical-manual.md` section 2, `openspec/config.yaml` context.

## What does not change

- An installed scope is used exactly as before, with the host's `get_secret` as the getter; the builder is not
  consulted while a scope is bound.
- The plugin itself never reads `os.environ` while the `agent` package is present: the launch profile comes from the
  host's builder. Execution outside Hermes keeps its environment fallback.
- Registration identity, the per-profile callbacks, the search wire, the audit log, the version `0.2.0` of the
  manifest (the install is pinned by commit, so no version bump is needed) and every requirement H0 to H22 except the
  wording of H19.

## Impact

- Code: `hermes_cited/config.py` (one branch and one helper).
- Tests: the two new files, a docstring in `tests/test_profile_scope.py`, `tui_gateway` in the host namespaces that
  `tests/conftest.py` isolates.
- Docs: the two READMEs, the technical manual and `openspec/config.yaml`.
