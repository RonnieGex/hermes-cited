# Design: search-only-bridge

## D1. One variable, two closed modes, registration decided once

`hermes_cited/config.py` gains `bridge_tools_of(environment) -> "full" | "search"`; any other value raises the
configuration sentence. `plugin.register(ctx)` reads it once and branches: `full` runs the registration that exists
today, untouched; `search` runs `_register_search_only(ctx)`, which calls `ctx.register_tool("cited_search", ...)`
with the same toolset, schema, description and handler as today and returns. No hook, command or skill is touched in
that branch, so H5's audit log, H4's modes and H10's composition are simply absent.

## D2. The second token and the second path

`Settings` gains `mode` and `search_token`. `settings_from_env()` in `search` mode reads `CITED_URL` and
`CITED_SEARCH_TOKEN` and does not read `CITED_MCP_TOKEN`; in `full` mode it behaves as today. `client.py` derives the
endpoint from the mode: `<CITED_URL>/api/mcp` in `full`, `<CITED_URL>/api/chassis/mcp` in `search`. The bearer is the
token of the mode. The host check, the redirect refusal and the timeout of H6 apply unchanged.

## D3. The contract of the search surface (implemented by `cited-ledger`)

`POST /api/chassis/mcp` is a JSON-RPC 2.0 MCP endpoint whose `tools/list` returns `cited_search` only and whose
`tools/call` accepts `{ "name": "cited_search", "arguments": { "query": string, "limit"?: integer 1..MAX } }` and
returns the same result envelope as `cited_search` of `/api/mcp` (passages with document, heading, position and
excerpt). Any other tool name answers the JSON-RPC error `-32601`. The bearer is a token distinct from
`CITED_MCP_TOKEN`, valid only for this path. This change tests against a fake of that contract in
`tests/fakes/chassis_surface.py`; the real surface is verified by `harness-foundation`.

## D4. Nothing is written in search mode

The audit log, the verify log and the delivery policy are features of sealed delivery (`full` mode). In `search`
mode the plugin writes nothing under `$HERMES_HOME/cited/`. The skill `cited-documents` that Harness installs in
every Vuk is owned and delivered by `cited-ledger`, not by this plugin.

## D5. Compatibility

The default is `full`, so every existing installation keeps its behaviour. The plugin version becomes `0.2.0`.
