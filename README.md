# hermes-cited

Cited in [Hermes Agent](https://github.com/NousResearch/hermes-agent): a native Python plugin that
gives Hermes the two [Cited](https://github.com/RonnieGex/cited) read-only tools as native tools, two
conversation modes, a deterministic verifier of the final answer and an auditable, hash-chained log.

Built by Katalis. Apache-2.0.

- **Mode dot** (the default): normal answers; Cited is used when it helps.
- **Mode cited**: before the turn the strict rules are injected, and after it a deterministic,
  non-AI verifier checks every number, unit, price and code of the answer against the passages Cited
  returned in that same turn. An answer that passes ends with `Verified by Cited` and its sources; an
  answer with a value no passage contains is replaced by a refusal that names it.

## Requirements

- Hermes Agent with the native plugin API. Everything here was verified on **v0.21.6+387
  (commit `dce1e9b`)**, Python 3.11.15 of the Hermes venv, on Windows.
- A Cited installation whose `/api/mcp` endpoint accepts the `MCP-Protocol-Version` header Hermes
  sends from `initialize`. Hermes sends `2025-11-25`; Cited needs the fix of
  [RonnieGex/cited#21](https://github.com/RonnieGex/cited/pull/21) (branch
  `fix/mcp-initialize-version-header`). Without it the connection fails with
  `the protocol version 2025-11-25 is not supported`.
- The `CITED_MCP_TOKEN` of that installation.

## Install in one step

```bash
hermes plugins install RonnieGex/hermes-cited --enable
```

From a local checkout, which is what the gate of this repository uses:

```bash
hermes plugins install "file:///C:/absolute/path/to/hermes-cited" --enable --yes-deps
```

The command clones the repository into `$HERMES_HOME/plugins/hermes-cited` and enables it. The
plugin is opt-in, so it stays off until it appears in `plugins.enabled`.

## Configure

Write these two variables in `$HERMES_HOME/.env` (the file Hermes loads into the environment of the
process that runs the plugin):

| Variable | Required | What it does |
|---|---|---|
| `CITED_URL` | yes | The address of the installation, like `https://cited.example.com`. The plugin calls `<CITED_URL>/api/mcp`. A URL already ending in `/api/mcp` is used as it is. |
| `CITED_MCP_TOKEN` | yes | The bearer token of that installation. It travels only in the `Authorization` header of a request to `CITED_URL`. |
| `CITED_TIMEOUT_MS` | no | How long one call to Cited may take, in milliseconds. `30000` by default. |
| `CITED_DEFAULT_MODE` | no | The mode a conversation starts in, `dot` or `cited`. `dot` by default. |

Without `CITED_URL` or `CITED_MCP_TOKEN` both tools answer a sentence that names the missing
variable. They never raise into Hermes, and Hermes keeps working.

## The two native tools

| Tool | Input | Output |
|---|---|---|
| `cited_search` | `query` (required), `limit` (1 to 8, 5 by default) | The passages that match, each with `n`, `document`, `heading`, `position` and `excerpt`, exactly as Cited sent them. |
| `cited_ask` | `question` (required), `sessionId` (optional) | `status` (`answered` or `refused`), `answer` and the numbered `citations` with their excerpts. |

They call `POST <CITED_URL>/api/mcp` with the JSON-RPC `tools/call` method and
`Authorization: Bearer <CITED_MCP_TOKEN>`. They are native and not an MCP configuration because the
installation is then one step and because the plugin needs to see every result to verify the answer
and to write the log.

## The two modes

- `/cited` turns cited mode on for this conversation; `/dot` turns it off. The key is the session when
  the surface exposes one and the profile otherwise. `CITED_DEFAULT_MODE` sets the initial mode.
- In cited mode, `pre_llm_call` injects the rules into the user message: call Cited first, answer only
  from the passages of this turn, copy every value exactly, pass a refusal on, never fill a gap from
  the web or from general knowledge.
- At the end of the turn `transform_llm_output` runs the verifier. It extracts numbers, units, prices
  and codes from the final text and checks each one against what Cited returned in that same turn,
  after normalising accents, case, thousands separators and English/Spanish singular-plural pairs. It
  never calls a model and never reads the question. A turn of cited mode with no Cited result at all
  cannot pass.
- An answer that passes is kept and ends with `Verified by Cited` and the sources Cited gave it. An
  answer with a value no passage contains is replaced by a sentence that names every value it could
  not verify. In dot mode nothing is replaced and the seal never appears.

## The audit log

Every response appends one entry to `$HERMES_HOME/cited/audit.jsonl`, in both modes: the UTC
timestamp, the platform, the session, the user when there is one, the mode, the question, the Cited
tool calls with their arguments, the SHA-256 of every excerpt Cited returned, the final response and
the verifier result, plus `prev_hash` and `hash`. The chain is
`hash = sha256(prev_hash + canonical_json(entry))`, so an entry that was altered, removed or
reordered breaks it.

```bash
python -m hermes_cited.verify_log "$HERMES_HOME/cited/audit.jsonl"
# OK: 4 entries, the chain verifies.        (exit 0)
# BROKEN: entry 2 was altered: ...          (exit 1)
```

The token is never written to the log, to a tool result or to any file of this repository.

## The `cited` skill

The plugin ships a `cited` skill and registers it with `ctx.register_skill`, so it appears in the
agent's available skills while the plugin is enabled. It says when to use each tool, that the answer
and its citations are transmitted without changing a datum, that a refusal of Cited is passed on, and
that in cited mode nothing is completed from the model's own knowledge.

## The MCP route, with no installation

Cited can also be reached as an MCP server, with no plugin at all. This is the route for any MCP
client; in Hermes the two tools then appear as `mcp__cited__cited_search` and
`mcp__cited__cited_ask`. The skill is what makes the agent reach for Cited before the web, so copy
`hermes_cited/skills/cited/SKILL.md` to `$HERMES_HOME/skills/cited/SKILL.md` as well.

`hermes mcp add cited --url <CITED_URL>/api/mcp --auth header` asks for the token, stores it in
`$HERMES_HOME/.env` as `MCP_CITED_API_KEY` and writes this into `$HERMES_HOME/config.yaml`:

```yaml
mcp_servers:
  cited:
    url: http://127.0.0.1:3246/api/mcp
    headers:
      Authorization: Bearer ${MCP_CITED_API_KEY}
    enabled: true
```

`${VAR}` is read from `$HERMES_HOME/.env` or the environment. Add `trust: untrusted` to that entry to
let the two tools, which are read-only, run without an approval prompt. Verify it with
`hermes mcp test cited`, which must connect and list both tools.

## What was tested (2026-10-09)

Everything below was run on 2026-10-09 with Hermes Agent **v0.21.6+387 (`dce1e9b`)**, the DeepSeek
model (`--provider deepseek -m deepseek-flash`), a Cited built from the branch of
[RonnieGex/cited#21](https://github.com/RonnieGex/cited/pull/21) on `127.0.0.1:3246` with the four
documents of its `samples/`, and a temporary `HERMES_HOME`. The real `%LOCALAPPDATA%\hermes` was
never used. Nothing else is claimed here.

| What | Result |
|---|---|
| The unit suite (`pytest`) | green: the client against a local fake `/api/mcp`, the two tools, the verifier, the chain, the modes, the registration and the packaged skill |
| `hermes mcp test cited` | connected, `Tools discovered: 2` (`cited_search`, `cited_ask`) |
| `hermes plugins install "file:///…" --enable --yes-deps` | installed into `$HERMES_HOME/plugins/hermes-cited` and enabled |
| The price question in the MCP route | the stream calls `mcp__cited__cited_search` and answers **380 pesos** with the citation of `cafe-la-horquilla.md · Precios` |
| The price question in cited mode | the stream calls the native `cited_search` and no web tool, answers **380 pesos [1]**, and the final text ends with `Verified by Cited` and its sources |
| "Is there a guarantee on repairs at the bike workshop?" | answers **90 days** from `bike-workshop-policies.md · Guarantee`, sealed |
| A question the samples do not answer | refuses without inventing a price |
| The audit log of those turns | one entry per answer, `python -m hermes_cited.verify_log` says `OK` and exits 0; altering, removing or reordering an entry makes it exit 1 and name the entry |
| Dot mode | the answer is untouched and carries no seal, and the entry is logged with the verifier marked as not applied |
| The refusal path | a unit case proves that an invented number is replaced by a refusal naming it |
| The `cited` skill | registered by the plugin and present in the installed tree |

`scripts/gate.py`, run with the Python of the Hermes venv, affirms H0 to H8 and prints
`GATE: GREEN`. Its output and the transcripts of the end-to-end runs are in `reports/`.

## Security

- The token only travels in the `Authorization` header of a request to the configured `CITED_URL`. It
  is never logged, never returned in a tool result, never written to the audit log and never written
  to the evidence.
- `401`, `403`, `404`, `405`, a timeout and a network failure each become a distinct sentence the model
  can read, and an answer from Cited that reflects the token is redacted before it is shown.
- The plugin is read-only against Cited: it never writes a document and never calls a language model
  itself. Only `cited_ask` may store a turn, and only when the caller passes a `sessionId`.

## License

Apache-2.0. See `LICENSE` and `NOTICE`. Spanish version: [README.es.md](README.es.md).
