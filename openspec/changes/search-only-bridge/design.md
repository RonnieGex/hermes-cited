# Design: search-only-bridge (review correction)

## D1. Scope and registration

Full retains H0-H18, including its compatibility limitations and no emitted seal. The MODIFIED deltas scope the
legacy registration, skill, commands, audit and composition requirements to full; H6 protects both modes.
H19-H22 are new identifiers. `CITED_BRIDGE_TOOLS` accepts `full` and `search`; absent or empty selects full.
Any other value refuses registration before any callback is installed. Mode is immutable for that registration.
Search registers exactly one native tool `cited_search` with wire v1 arguments, description
`Search unsealed document passages.`, toolset `cited`, and no command, hook, skill or log writer.

## D2. Active profile configuration, fail closed

An explicit Mapping is accepted only by the test seam. In Hermes, import `current_secret_scope`,
`current_secret_scope_home` and `get_secret` from `agent.secret_scope`. Require a non-null mapping and home at
registration and every handler call. Check membership in that mapping before calling get_secret: a missing value
uses its documented default, never a process-environment fallback. Accessor/import/runtime failures when Hermes
is present fail closed with a redacted configuration sentence; there is no catch-all fallback to os.environ.
Only execution outside Hermes (agent package absent, not an error importing it) uses os.environ.
Capture the canonical home identity and registration mode, not a process-global Settings singleton. A call in
another home or with a changed mode is refused until that profile is registered again. Read URL, selected token
and timeout freshly from that same profile scope so rotations take effect. Search must never request the key
CITED_MCP_TOKEN, even to redact or check it; full validates only its own token. Mapping spies enforce that rule.
Concurrent profiles with different modes, URLs and tokens must remain independent of an adversarial root .env.

## D3. Versioned transport

`wire-contract.md` and its hashed schema/fixture are normative. Search uses that entire contract for arguments,
URL, limits, errors, redaction and the model envelope. Full keeps its existing endpoint normalization and envelope.
The fake `tests/fakes/chassis_surface.py` implements wire v1 and records redacted requests. Tests compare actual
unredacted headers in memory only; reports contain sentinel labels. No request to a running personal installation.

## D4. Manifest and profile installation

Version 0.2.0. The target manifest is `fixtures/plugin-search.yaml`; copy its semantics to plugin.yaml during
implementation. Only CITED_URL is unconditional requires_env. Both tokens are optional_env secrets with conditional
runtime requirements; CITED_BRIDGE_TOOLS defaults full. provides_tools/provides_hooks are potential catalogs, not
effective registrations. Registration and runtime tests establish the actual mode. No manifest extension is assumed.

At Hermes pin `dce1e9b37581dd62e480a9064dc04a709c2940d3`, the command is:
`env HERMES_HOME=<root> <chassis>/.venv/bin/hermes --profile <name> plugins install file://<release>/hermes-cited.git --ref <full-sha> --enable --yes-deps`.
The profile already exists at `<root>/profiles/<name>`; `--profile default` selects root. Write URL/mode/search token
before discovery. The local Git mirror is read-only to the chassis and its archive matches the release lock before
invocation. For a public install the identifier is the repository URL with a separate `--ref`, never `repo@sha`.
The harness operations adapter owns reload and readiness. B tests a new isolated profile with the real CLI and
loads its registered catalog, then calls the handler in that profile's secret scope. It never starts personal services. Offline CLI installation may attempt the catalog removal-list refresh;
the pinned upstream falls back to its in-tree list on denied network. Keep that guard and validate offline
installation from the local mirror, never grant runtime access to code-hosting origins.
Evidence: upstream `hermes_cli/subcommands/plugins.py` install flags; `hermes_cli/profiles.py:resolve_profile_env`;
`hermes_cli/plugins_cmd_install.py` accepts file URLs; `agent/secret_scope.py` accessors. These are source facts,
not a claim that this future search implementation has run.

## D5. No writes and packaging

Search makes no filesystem changes under HERMES_HOME, including cited/. There is no plugin database. Snapshot
inventory and SHA-256 before registration and after calls in tests, excluding only fake HTTP logs outside that home.
Set PYTHONDONTWRITEBYTECODE=1 in the isolated test process so Python import caches cannot mask or create plugin
write evidence. Installation/setup completes before this baseline; no actual plugin-created file is excluded.
The Harness-owned cited-documents skill belongs to A. Channels and every other deferred feature stay deferred.
The release artifact is exactly the bytes of `git archive --format=tar <sha>` for the full archived merge SHA,
with no prefix or gzip. Use an isolated Git configuration (no global/system/info attribute overrides and
no tar.umask override), honoring only tracked .gitattributes, so producer and verifier use the same bytes. Record full SHA, SHA-256 and byte size in bridge.lock.
Use Git's binary --output option when capturing bytes on Windows; PowerShell text redirection is forbidden.
README examples use an existing tested commit; the final release lock is written in a later consumer commit,
never a self-referential hash. This correction run commits specifications only, without archive, merge or push.
