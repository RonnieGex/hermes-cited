# hermes-cited technical manual

This manual is the reference of the two modes of the plugin, the profile-scoped configuration, the search
wire and the pinned per-profile installation. It describes the implementation of
`openspec/changes/archive/2026-10-13-search-only-bridge`; the normative contracts are `spec.md` (H0-H22),
`design.md` (D1-D10) and `wire-contract.md` of that change.

## 1. The closed mode switch

`CITED_BRIDGE_TOOLS` is read once, at registration, from the active profile scope:

| Value | Result |
|---|---|
| absent or empty | `full` |
| `full` | `full` |
| `search` | `search` |
| anything else | registration is refused and **nothing** is registered |

The mode is immutable for the registration. A call that resolves to another home or another mode is refused
until that profile registers again.

- **`full`** keeps H0-H18: `cited_search`, `cited_ask`, `cited_quote`, the `/cited` and `/dot` commands, the
  `pre_llm_call`, `post_tool_call` and `transform_llm_output` hooks, the `cited` skill and the hash-chained
  audit log. It calls `POST <CITED_URL>/api/mcp` with `CITED_MCP_TOKEN`.
- **`search`** registers exactly one native tool, `cited_search`, and no command, hook, skill or audit
  writer. It calls `POST <CITED_URL>/api/chassis/mcp` with `CITED_SEARCH_TOKEN`. It `writes nothing` under
  `HERMES_HOME`, and it never requests `CITED_MCP_TOKEN`, not even to check or redact it.

## 2. Profile-scoped configuration and its failures

Inside Hermes the plugin imports `agent.secret_scope`: `current_secret_scope()`,
`current_secret_scope_home()` and `get_secret()`. The accessor must answer a `Mapping` and a non-empty home;
both are required at registration and at every handler call. A key that is absent from the mapping takes its
documented default; there is no fallback to the process environment. An accessor that raises, that answers
`None`, a non-mapping value or a blank home fails closed with the redacted sentence that names neither the
profile, nor the URL, nor the token. When `import agent` fails, only a missing `agent` package **itself**
selects the environment; a `ModuleNotFoundError` raised by a dependency inside the host means the host is
present and broken, and it fails closed too.

Only a run **outside Hermes**, where the `agent` package is genuinely absent, reads `os.environ`. That is
what keeps the unit suite and a standalone client testable.

The failures are:

| Situation | Answer | Requests |
|---|---|---|
| no mapping, a non-mapping value or no home | redacted configuration sentence | zero |
| the host is present but its scope cannot be imported | redacted configuration sentence | zero |
| a home different from the registration's (canonical paths, so `home/child/..` is the same identity) | redacted configuration sentence | zero |
| a mode different from the registration's | redacted configuration sentence | zero |
| absent `CITED_URL` | a sentence that names `CITED_URL` | zero |
| absent token of the mode | a sentence that names `CITED_SEARCH_TOKEN` or `CITED_MCP_TOKEN` | zero |
| invalid `CITED_TIMEOUT_MS` in search | a sentence that names `CITED_TIMEOUT_MS` | zero |
| a URL with userinfo, path, query or fragment in search | a sentence that names `CITED_URL` | zero |

Rotations take effect on the next call: the URL, the selected token and the timeout are read freshly from
the same profile scope on every handler call.

Every registered callback of `full` — `cited_search`, `cited_ask`, `cited_quote`, the three hooks and the two
commands — validates the registration's profile before an effect and reads its settings from that profile. The
default mode, the language, the selected token and the audit path of a turn come from the profile that
registered the callback, and a turn is visible only to the profile that opened it. A process that hosts more
than one Hermes profile therefore never serves one profile's mode, evidence or log from another.

Round 4 (D6-D8) makes that binding explicit:

- **Turn identity (D6).** The live turns of the process are keyed by the canonical profile home together with
  the host session and turn identifiers, so two profiles that receive identical `session_id`/`turn_id` values
  hold two independent turns. A callback whose active scope resolves to another home or mode is refused before
  any turn is read, created or dropped, and the refusal performs no cleanup; the transformer drops only the
  turn its own validated call owns, through the same key. The turn table's capacity is per profile as well:
  the oldest key of the calling owner is evicted, never the first key of the whole table, so a busy profile
  cannot remove another profile's pending turn. An explicit execution identity (`turn_id` or `task_id`) that
  resolves to no open turn is refused instead of falling back to the only active turn; the implicit form with
  no identity still uses the single open turn and refuses an ambiguous session. The pinned host composes its
  turn identifier as `"<session>:<task>:<suffix>"` and hands the tool dispatch the task and the session but
  never the turn, so both spellings resolve the same execution; a present `turn_id` is authoritative and a
  failed primary is never replaced by the `task_id` of the same call. Creation, resolution and observation use
  the identical raw spelling of the identifier, and an observation locates a live turn without ever
  fabricating one, so a turn that already returned from the transformer is not revived and an identity-less
  second execution is never opened. Both rules are ported as
  regressions in `tests/test_round4_amendments.py` (D6/M01-B2R1, H14/M02-B2R1) and
  `tests/test_bridge2_amendments.py` (D6/H14, M01-B2R2, M02-B2R2).
- **Persisted mode (D7).** The host's `PluginState` already partitions its state per profile home, so the
  plugin writes the plain `mode.profile` key of the previous version and never a path or NUL prefix. Every key
  satisfies the host pattern `^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$`; a `mode.profile` value written before the
  upgrade is honoured with no migration, and a host key-validation error is surfaced instead of being turned
  into the default.
- **Diagnostics (D8).** The redaction set of a failure diagnostic is the one of the profile whose callback
  failed. `_profile_call` hands the resolved bearer to `_report_failure` (or keeps the call context active
  until the report), so every log record and traceback is redacted with that profile's secret and never with
  the root environment's.

## 3. The search wire, version 1

`wire-contract.md` and `fixtures/search-wire-v1.schema.json` are normative and hash-pinned. The schema is
`$defs.arguments` for the tool, `$defs.request`/`$defs.response` for `tools/call`, `$defs.listRequest`/
`$defs.listResponse` for `tools/list` and `$defs.error` for every JSON-RPC error.

- The only destination is `POST /api/chassis/mcp`, `Content-Type: application/json`, bearer
  `CITED_SEARCH_TOKEN`, body at most 16 KiB.
- The arguments are exactly `query` (a string of 1 to 1000 Unicode code points with at least one
  non-whitespace character) and an optional `limit` (an integer from 1 to 8, `5` by default). There is no
  coercion and no trimming: a boolean, a float, a numeric string, a whitespace-only query or an unknown
  property is refused before any request.
- `tools/list` returns the one tool, its description `Search unsealed document passages.` and exactly the
  arguments schema. `tools/call` returns one content block and `structuredContent.passages`; passage numbers
  are sequential from 1, `position` is zero-based, `heading` is a string or `null`, `document` is the stored
  name and `excerpt` is the literal source text.
- The content block recomposes from the passages as `[n] document`, the heading when it is not `null`, and
  the excerpt, joined with two LF characters. The client rejects a block that does not recompose.
- The client rejects non-JSON, a mismatched id, a malformed passage, an `isError` result, a JSON-RPC error
  and any reflected bearer, each with a redacted diagnostic sentence that carries no raw body, exception,
  credential or header. The transport categories are fixed sentences: a timeout, a network failure, an
  `OSError`, a read failure and any unexpected exception name the condition, never the text of the
  underlying exception (M02).
- **Every redirect is refused**: 301, 302, 303, 307 and 308, to the same origin and to another one, without
  a second request, so the bearer never reaches a `Location`.
- The model envelope is a JSON *string*:
  `{"cited_tool":"cited_search","query":<unchanged>,"text":<content[0].text>,"passages":[<passage plus lines>]}`.
  It introduces no `pid`, no seal, no composition and no audit entry.

## 4. No writes

Search completes before a baseline is taken and then makes no filesystem change under `HERMES_HOME`,
including `cited/`. The isolated tests set `PYTHONDONTWRITEBYTECODE=1`, snapshot the sorted inventory and the
SHA-256 of every regular file of the home before registration and after a successful call and a failing
call, and require the two snapshots to be identical. Installation and setup complete before that baseline,
so no plugin-created file is excluded.

## 5. Threat model of the search bearer

The search token is a separate credential that reaches only the retrieval surface. It travels only to
`<CITED_URL>/api/chassis/mcp`; the origin must be explicit, every redirect is refused, the global urllib
opener is never replaced, and a response that reflects the bearer is discarded whole. The token is never
written to a log, a report, a fixture or a commit: the fake surface of the tests uses a synthetic bearer
constant and every recorded row is written as `<search-token>`.

## 6. Per-profile installation, pinned

At the Hermes pin `dce1e9b37581dd62e480a9064dc04a709c2940d3`:

```bash
env HERMES_HOME=<root> <chassis>/.venv/bin/hermes --profile <name> \
  plugins install file://<release>/hermes-cited.git --ref <full-sha> --enable --yes-deps
```

- The profile already exists at `<root>/profiles/<name>`; `--profile default` selects the root.
- The URL, the mode and the search token are written before discovery.
- A public install passes the commit in a separate `--ref`; `repo@sha` is never used.
- The local Git mirror is read-only to the chassis, and its archive matches the release lock before the
  invocation. An offline install may attempt the catalog refresh; the pinned upstream falls back to its
  in-tree list when the network is denied.
- The package is version `0.2.0`; only `CITED_URL` is unconditionally required, and both tokens are
  conditional secrets. `provides_tools` and `provides_hooks` are potential catalogs, not effective
  registrations: the mode established by `CITED_BRIDGE_TOOLS` is what actually registers.
- The disposable Linux runner pre-provisions the managed runtimes the pinned host's `plugins install` needs
  beyond the venv (that pin: CPython `3.14.7+20260901` and uv `0.12.3`) before the network namespace is
  closed, recording each version, SHA-256 and store path. During the run the network stays closed, a download
  attempt fails the test rather than skipping it, and the complete inventory of the profile home after setup is
  compared with its baseline (D5, D9), not only the absence of `cited/`.

The release artifact is exactly the bytes of `git archive --format=tar <full-archived-merge-sha>` with no
prefix and no gzip. Use an isolated Git configuration with no global, system or info attribute overrides and
no `tar.umask` override, capture the bytes with Git's binary `--output` option (PowerShell text redirection
is forbidden), and record the full SHA, the SHA-256 and the byte size in `bridge.lock`. The lock is written
in a later consumer commit, never with a self-referential hash.

## 7. Testing this change

- `tests/search_guard.py` forbids the personal ports 3240/3241 in every spelling and the personal paths,
  and installs a socket guard for the whole suite.
- `tests/fakes/chassis_surface.py` implements the wire v1 subset, every documented error, both redirect
  classes and the `--port`/`--record` script entry for the manual `curl.exe` checks.
- `tests/test_search_only_mode.py`, `tests/test_profile_scope.py` and `tests/test_search_wire.py` cover
  H19-H21; `tests/test_manifest_modes.py`, `tests/test_profile_install.py` and `tests/test_docs_bridge.py`
  cover H22.
- Every run uses a temporary `HERMES_HOME`. The installation under `%LOCALAPPDATA%\hermes` and the
  `hermes-agent` checkout are read-only, and no run touches the personal ports 3240 or 3241.
