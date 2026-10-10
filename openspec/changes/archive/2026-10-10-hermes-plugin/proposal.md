# Why

Franc asked that Cited be connectable to Hermes Agent, the way it already is to DeepSeek Harness, Codex and Claude
(`tasks/idea-crew-agente-con-cited.md`, section 5A and section 6). This change is the authorized scope of
`tasks/mision-cited-hermes.md`: a new repository, `hermes-cited`, holding a native Hermes Agent plugin, plus the two
routes to connect Cited (MCP configuration and the native plugin), the two conversation modes, a deterministic
verifier, an auditable log, tests and documentation.

Requirement author: Fable. Implementer: DeepSeek. The contract is the mission document; this specification
transcribes it without adding scope.

# What Changes

A new Apache-2.0 repository `hermes-cited` SHALL hold a native Hermes Agent plugin that:

- registers `cited_search` and `cited_ask` as native tools that call `POST <CITED_URL>/api/mcp` (JSON-RPC
  `tools/call`) with `Authorization: Bearer <CITED_MCP_TOKEN>`;
- packages a `cited` skill with the cited-mode rules;
- adds the `/cited` and `/dot` conversation modes, seeded by `CITED_DEFAULT_MODE` (`dot` by default);
- in cited mode, injects strict rules through `pre_llm_call` and replaces the final answer through
  `transform_llm_output` when a deterministic verifier cannot ground every number, unit, price and code in a passage
  Cited returned in that same turn;
- appends one hash-chained entry per response to `$HERMES_HOME/cited/audit.jsonl`, with a chain verifier;
- never writes the token anywhere but the request header.

The repository also SHALL document the MCP-configuration route in `docs/mcp.md` of the Cited worktree and add the
Hermes Agent row to the "Works with your agent" table of `README.md` / `README.es.md`, without touching graphics.

# Impact

New repository under `katalis-dev`. In the existing Cited worktree `community-hermes` (branch `docs/hermes-agent`):
documentation only, in `docs/mcp.md`, `README.md` and `README.es.md`. No product code, no graphics, no landing, no
deployment, no push, and not one byte written under `%LOCALAPPDATA%\hermes` or `~/.hermes`.
