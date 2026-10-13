# hermes-cited technical manual

This manual is the reference of the two modes of the plugin, the profile-scoped configuration, the search
wire and the pinned per-profile installation. It describes the implementation of
`openspec/changes/search-only-bridge`; the normative contracts are `spec.md` (H0-H22),
`design.md` (D1-D5) and `wire-contract.md` of that change.

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
`current_secret_scope_home()` and `get_secret()`. Both the mapping and the home are required at registration
and at every handler call. A key that is absent from the mapping takes its documented default; there is no
fallback to the process environment. An accessor that raises, or that answers `None`, fails closed with the
redacted sentence that names neither the profile, nor the URL, nor the token.

Only a run **outside Hermes**, where the `agent` package is absent, reads `os.environ`. That is what keeps
the unit suite and a standalone client testable.

The failures are:

| Situation | Answer | Requests |
|---|---|---|
| no mapping or no home | redacted configuration sentence | zero |
| a home different from the registration's | redacted configuration sentence | zero |
| a mode different from the registration's | redacted configuration sentence | zero |
| absent `CITED_URL` | a sentence that names `CITED_URL` | zero |
| absent token of the mode | a sentence that names `CITED_SEARCH_TOKEN` or `CITED_MCP_TOKEN` | zero |
| invalid `CITED_TIMEOUT_MS` in search | a sentence that names `CITED_TIMEOUT_MS` | zero |
| a URL with userinfo, path, query or fragment in search | a sentence that names `CITED_URL` | zero |

Rotations take effect on the next call: the URL, the selected token and the timeout are read freshly from
the same profile scope on every handler call.

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
  credential or header.
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
