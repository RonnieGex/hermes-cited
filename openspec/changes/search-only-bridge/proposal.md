# search-only-bridge

A second mode of the plugin, `search`, for Cited Harness: the plugin registers `cited_search` only, against a
search-only surface of the installation authenticated with its own token, and nothing else. No `cited_ask`, no
`cited_quote`, no `/cited` or `/dot` commands, no composition hooks, no `cited` skill, no audit record. The current
behaviour is the mode `full` and does not change.

## Why

Cited Harness (`cited-ledger`, change `harness-foundation`) runs every Vuk as a profile of Hermes and needs the
documents of the installation as an **unsealed** retrieval tool for Open mode, with a content boundary: the chassis
must never receive a sealed answer, the decision log or a credential that can reach them. The current plugin
registers three tools over `POST /api/mcp` with `CITED_MCP_TOKEN`, a credential that authorises the whole MCP
surface (including `cited_ask`); its cited composition is not the Ledger; and its commands and skill would appear in
the Vuk's Hermes. Codex's contract review of `harness-foundation` (R2-B01, R2-B03) requires a bridge that exposes
retrieval only, with a token that cannot reach anything else, delivered and archived before that change is approved.

## What changes

- A new environment variable `CITED_BRIDGE_TOOLS` with the closed values `full` (default) and `search`.
- In `search` mode the plugin registers exactly one tool, `cited_search`, that calls
  `POST <CITED_URL>/api/chassis/mcp` with `Authorization: Bearer <CITED_SEARCH_TOKEN>`, the versioned wire and model envelope in `wire-contract.md`; it registers no other tool, no command, no hook and no
  skill, and writes no audit record.
- `CITED_SEARCH_TOKEN` is required in `search` mode; `CITED_MCP_TOKEN` is ignored in that mode and never read.
- The token travels only to `<CITED_URL>/api/chassis/mcp`, with the explicit all-redirect refusal and origin rules in wire-contract.md.
- Documentation of the mode in `README.md` and `README.es.md`, and the install command pinned by commit for Harness.

## What does not change

- The `full` mode: tools, commands, modes, verifier, delivery policy, audit log and skill stay as specified by H0 to H18.
- The plugin remains read-only against Cited and never calls a language model.

## Depends on

Nothing in this repository. The counterpart surface `POST /api/chassis/mcp` is specified by `harness-foundation` in
`cited-ledger` with the contract published in this change's design; this change is tested against a fake of that
surface and is archived before `harness-foundation` is approved.

## Impact

- Code: `hermes_cited/config.py` (the mode and the second token), `hermes_cited/plugin.py` (conditional
  registration), `hermes_cited/client.py` (the endpoint path by mode), `hermes_cited/tools.py` (no change of
  behaviour of `search`).
- Tests: `tests/test_search_only_mode.py`.
- Docs: `README.md`, `README.es.md`, `openspec/config.yaml` (the mode joins the context).

## Contract correction status

H19-H22 and MODIFIED full-mode deltas close SB-M01 through SB-M05. Wire v1 and the target manifest are delivered
as fixtures. No product code is changed here. The runtime bridge, independent implementation review, archive and
merge are still future tasks. Its distribution pin uses exactly `git archive --format=tar <sha>` without prefix
or gzip, recording full SHA, SHA-256 and size. This correction authorizes no merge, push or archive.
