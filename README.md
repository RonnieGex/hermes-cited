# hermes-cited

Cited in [Hermes Agent](https://github.com/NousResearch/hermes-agent): a native Python plugin that gives
Hermes the two [Cited](https://github.com/RonnieGex/cited) read-only tools as native tools, two conversation
modes, an extractive verifier of the final answer and an auditable, hash-chained log with an authenticated
checkpoint.

Built by Katalis. Apache-2.0.

- **Mode dot** (the default): normal answers; Cited is used when it helps.
- **Mode cited**: before the turn the strict rules are injected, and after it a deterministic, non-AI
  verifier accepts a datum only when the whole sentence or line that carries it appears **verbatim** inside
  an excerpt Cited returned in that same turn. An answer that passes ends with `Verified by Cited` and its
  sources; an answer that restates a value in its own words — even with the right number — is replaced by a
  refusal that names the segment it could not verify.

## Requirements

- Hermes Agent with the native plugin API. Everything here was verified on **v0.21.6+387 (commit
  `dce1e9b`)**, Python 3.11.15 of the Hermes venv, on Windows.
- A Cited installation whose `/api/mcp` endpoint accepts the `MCP-Protocol-Version` header Hermes sends
  from `initialize`. Hermes sends `2025-11-25`; Cited needs
  [RonnieGex/cited#21](https://github.com/RonnieGex/cited/pull/21), merged into `main` as
  `ef11f88`. Without it the connection fails with `the protocol version 2025-11-25 is not supported`.
  The gate of this repository builds its test Cited from `origin/main`, which already carries that merge.
- The `CITED_MCP_TOKEN` of that installation.

## Install in one step

```bash
hermes plugins install RonnieGex/hermes-cited --enable
```

From a local checkout, which is what the gate of this repository uses:

```bash
hermes plugins install "file:///C:/absolute/path/to/hermes-cited" --enable --yes-deps
```

The command clones the repository into `$HERMES_HOME/plugins/hermes-cited` and enables it. The plugin is
opt-in, so it stays off until it appears in `plugins.enabled`.

## Configure

Write these variables in `$HERMES_HOME/.env` (the file Hermes loads into the environment of the process
that runs the plugin):

| Variable | Required | What it does |
|---|---|---|
| `CITED_URL` | yes | The address of the installation, like `https://cited.example.com`. The plugin calls `<CITED_URL>/api/mcp`. A URL already ending in `/api/mcp` is used as it is. |
| `CITED_MCP_TOKEN` | yes | The bearer token of that installation. It travels only in the `Authorization` header of a request to `CITED_URL`. |
| `CITED_TIMEOUT_MS` | no | How long one call to Cited may take, in milliseconds. `30000` by default. |
| `CITED_DEFAULT_MODE` | no | The mode a conversation starts in, `dot` or `cited`. `dot` by default. |
| `CITED_AUDIT_KEY_PATH` | no | Where the HMAC key of the audit checkpoint lives. `%APPDATA%\Katalis\hermes-cited\audit.key` by default. It is never inside `HERMES_HOME` and never the bearer of Cited. |

Without `CITED_URL` or `CITED_MCP_TOKEN` both tools answer a sentence that names the missing variable.
They never raise into Hermes, and Hermes keeps working.

## The two native tools

| Tool | Input | Output |
|---|---|---|
| `cited_search` | `query` (required), `limit` (1 to 8, 5 by default) | The passages that match, each with `n`, `document`, `heading`, `position` and `excerpt`, exactly as Cited sent them. |
| `cited_ask` | `question` (required), `sessionId` (optional) | `status` (`answered` or `refused`), `answer` and the numbered `citations` with their excerpts. |

They call `POST <CITED_URL>/api/mcp` with the JSON-RPC `tools/call` method and
`Authorization: Bearer <CITED_MCP_TOKEN>`. They are native and not an MCP configuration because the
installation is then one step and because the plugin needs to see every result to verify the answer and to
write the log.

## The two modes

- `/cited` turns cited mode on for this conversation; `/dot` turns it off. The key is the session when the
  surface exposes one and the profile otherwise. `CITED_DEFAULT_MODE` sets the initial mode.
- In cited mode, `pre_llm_call` injects the rules into the user message: call Cited first, answer only from
  the excerpts of this turn, copy every fact between `« »` exactly as the excerpt writes it, pass a refusal
  on, never fill a gap from the web or from general knowledge.
- At the end of the turn `transform_llm_output` runs the verifier. It splits the answer into sentences and
  lines, splits quoted from free text, and checks every datum-bearing segment:
  - a segment that carries a number, a price, a unit, a date or a code and is **not** between `« »` is
    refused: free text may not carry a datum;
  - a quoted segment is accepted only when it appears verbatim — after NFKC Unicode normalisation,
    accents off, case-folded and whitespace collapsed on both sides — inside a non-empty `excerpt` Cited
    returned in that same turn.
- The evidence is only `passages[].excerpt` and `citations[].excerpt`. The query, the generated `cited_ask`
  answer, the headings, the positions, the counts and the transport text are never evidence. A turn with
  zero excerpts cannot be sealed.
- Citation marks such as `[1]` are removed before the segment check and validated separately against the
  citation map of the turn; a mark with no matching passage or citation is refused.
- A `status: refused` from `cited_ask` becomes an explicit refusal, never a seal.
- An answer that passes is kept and ends with `Verified by Cited` and the sources Cited gave it. Dot mode
  replaces nothing and never carries the seal.
- Totals and other computed values are out of scope for this round: they belong to the documents mission,
  where a tool computes them in code and records their provenance.

## Delivery: what is verified, and what may be seen

Hermes v0.21.6+387 hands every text delta to the screen, the messaging surface and streaming TTS **before**
`transform_llm_output` decides. No plugin hook can retain those deltas; that is a host limitation, and this
plugin states it instead of hiding it.

| Surface | What the plugin does |
|---|---|
| Messaging (Telegram, Slack, Discord and the like) | Reads the effective streaming configuration and, when streaming is on, withholds the seal and says so in the answer. To receive the seal, turn streaming off for cited mode: `streaming.enabled: false`, or `display.platforms.<platform>.streaming: false`. |
| CLI | Keeps the seal. `--format stream-json` emits `text` events, so **a consumer of that format must show only the terminal `result` record**; a consumer that concatenates `text`, reasoning or comments would show the draft. Set `display.streaming: false` to remove the draft entirely. |
| Desktop app | Keeps the seal. The app wires its own SSE stream, which no configuration here reaches: **a draft may be visible while the answer is written**. The final answer is still verified and recorded. |

The exact configuration for the gateway:

```yaml
streaming:
  enabled: false                 # master switch; `transport: off` also disables
display:
  platforms:
    telegram:
      streaming: false           # narrows only; never enables streaming on its own
```

`display.streaming` is CLI-only; the gateway resolves `display.platforms.<platform>.streaming` first.
Discord and Slack only stream by edit when the global switch is on and no per-platform key is present, so
write `false` explicitly for a hard guarantee. `docs/upstream-proposal.md` (English) specifies the per-turn
delivery-policy hook Hermes would need to close this gap for every surface, including the SSE route, with
the file and line of each point it touches. No pull request and no issue was opened upstream.

## The audit log

Every response appends one entry to `$HERMES_HOME/cited/audit.jsonl`, in both modes: the UTC timestamp, a
monotonic `seq`, the identity of the log, the platform, the session, the turn identifier, the user when
there is one, the mode, the question, the Cited tool calls with their arguments and the SHA-256 **and text**
of every returned excerpt, the sources, the final response and the verifier result, plus `prev_hash` and
`hash`. The chain is `hash = sha256(prev_hash + canonical_json(entry))`.

The append holds an exclusive inter-process lock over `<log>.lock` while it reads and validates the tail,
computes the hash, appends and flushes to disk. A log whose tail is invalid refuses the append instead of
starting a new chain. The schema is validated before hashing and again at verification.

After every append the plugin rewrites an HMAC-authenticated checkpoint (`<log>.checkpoint`) with the
entry count, the final hash and the log identity. Its key lives **outside `HERMES_HOME`**, at
`%APPDATA%\Katalis\hermes-cited\audit.key` by default, and it is never the bearer of Cited. The verifier
requires the checkpoint:

- an altered, removed or reordered entry breaks the chain;
- an entry removed from the end, or a cut suffix, may leave the chain internally consistent, but it no
  longer matches the checkpoint;
- a chain rewritten and every hash recomputed without the key does not authenticate;
- a checkpoint rolled back while the log keeps its entries no longer matches the count and final hash;
- a missing checkpoint is an error, not a pass.

**Exact scope of the custody:** a change made by someone who does not have the key is detected. If the log
and its checkpoint are rolled back together by someone with write access to both, only remote custody can
tell — that arrives with Cited Ledger. The key proves authenticity, not remote immutability.

Verify it from the installed plugin, which is where the module is importable:

```powershell
Push-Location (Join-Path $env:HERMES_HOME 'plugins/hermes-cited')
try {
    python -m hermes_cited.verify_log (Join-Path $env:HERMES_HOME 'cited/audit.jsonl')
} finally {
    Pop-Location
}
# OK: 4 entries, the chain and its checkpoint verify.   (exit 0)
# BROKEN: the log does not match its checkpoint: ...    (exit 1)
```

Use explicitly the Python of Hermes when `python` is not that interpreter. Running the module from another
directory fails with `ModuleNotFoundError: No module named 'hermes_cited'`: Hermes imports a directory
plugin as `hermes_plugins.<slug>` and never installs it as a top-level package.

## The `cited` skill

The plugin ships a `cited` skill and registers it with `ctx.register_skill`, so it appears in the agent's
available skills while the plugin is enabled. It says when to use each tool, that the answer and its
citations are transmitted without changing a datum, that cited mode requires each datum to be copied
verbatim between `« »`, that a refusal of Cited is passed on, and that in cited mode nothing is completed
from the model's own knowledge. In the MCP-only route the same two tools exist, but `/cited`, `/dot`, the
verifier and the audit log do not: there is no plugin to run them.

## The MCP route, with no installation

Cited can also be reached as an MCP server, with no plugin at all. This is the route for any MCP client; in
Hermes the two tools then appear as `mcp__cited__cited_search` and `mcp__cited__cited_ask`. The skill is what
makes the agent reach for Cited before the web, so copy `hermes_cited/skills/cited/SKILL.md` to
`$HERMES_HOME/skills/cited/SKILL.md` as well.

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

`${VAR}` is read from `$HERMES_HOME/.env` or the environment. Add `trust: untrusted` to that entry to let
the two tools, which are read-only, run without an approval prompt. Verify it with `hermes mcp test cited`,
which must connect and list both tools.

## What was tested (2026-10-10)

Everything below was run on 2026-10-10 with Hermes Agent **v0.21.6+387 (`dce1e9b`)**, the DeepSeek model
(`--provider deepseek -m deepseek-flash`), a Cited built from `origin/main` (`ef11f88`, the merged PR #21)
in its own temporary worktree and served on `127.0.0.1:3246` with the four documents of its `samples/`, and
a temporary `HERMES_HOME`. `scripts/gate.py`, run with the Python of the Hermes venv, affirms the properties
and prints `GATE: GREEN`; its output and the transcripts are inside the change
(`openspec/changes/hermes-plugin-r2/reports/`).

**The real `%LOCALAPPDATA%\hermes` was never written and never used as the target of any run of this
round.** The isolated final run and its gate use temporary homes only. One historical run of round 1, early
in `mision-cited-hermes.md`, executed `hermes mcp test cited` **without** `HERMES_HOME` and read the real
configuration (a read-only connection test against the live Cited on port 3240, which failed). It happened
once, it is preserved here instead of being claimed away, and it is reported as a RISK in
`tasks/entrega-cited-hermes-r2.md`. No byte was written under the real home, and no run of round 2 touched
port 3240.

| What | Result |
|---|---|
| The unit suite (`pytest`) | green: the client and its redirect refusal, the two tools, the extractive verifier, the chain with its checkpoint and its inter-process lock, the modes, the delivery policy and the packaged skill, plus one adversarial case per review finding |
| `hermes mcp test cited` | connected, `Tools discovered: 2` (`cited_search`, `cited_ask`) |
| `hermes plugins install "file:///…" --enable --yes-deps` | installed into `$HERMES_HOME/plugins/hermes-cited` and enabled |
| The real loader | the installed plugin loads with the Hermes plugin manager and registers its three hooks |
| The price question in the MCP route | the stream calls `mcp__cited__cited_search` and answers **380 pesos** with the citation of `cafe-la-horquilla.md · Precios` |
| The price question in cited mode | the stream calls the native `cited_search`, no other tool before it, answers the value with its citation, and the final `result` record ends with `Verified by Cited` and its sources |
| "Is there a guarantee on repairs at the bike workshop?" | answers **90 days** from `bike-workshop-policies.md · Guarantee`, sealed |
| A question the samples do not answer | refuses without a datum |
| The audit log of those turns | one entry per turn, exact count, `python -m hermes_cited.verify_log` from the installed plugin says `OK` and exits 0; removing an entry, cutting a suffix, rewriting and recomputing, or rolling back the checkpoint makes it exit 1 |
| Dot mode | the answer is untouched and carries no seal, and the entry is logged with the verifier marked as not applied |
| The verifier path | adversarial cases prove that a reworded value, a swapped subject, a free-text datum and a query echo are all refused |
| The delivery policy | with `streaming.enabled: true`, a cited-mode answer on `telegram` withholds the seal and says so; with streaming off it is sealed |
| The `cited` skill | registered by the plugin and present in the installed tree, with the verbatim-quotation rule and the plugin-only note |

Not tested in this round: a real Telegram/Slack/Discord bot (the delivery policy is proven in-process
against the same configuration resolver), an interactive TUI, macOS or Linux, and installation against the
public GitHub URL.

## Security

- The token only travels in the `Authorization` header of a request to the configured `CITED_URL`. A `3xx`
  is refused before any second request, so a redirect can never carry the bearer to another origin.
- Before building any visible result, in success and in error, the client rejects a response that reflects
  the token in any string; the answer is discarded and nothing of it is shown or recorded.
- Before hashing and appending, every field of the audit entry is redacted recursively, including the
  question, the arguments, the excerpts, the response and the errors.
- `401`, `403`, `404`, `405`, a timeout and a network failure each become a distinct sentence the model can
  read. The plugin never writes a secret to a log, a tool result, the audit file or the evidence.
- The plugin is read-only against Cited: it never writes a document and never calls a language model itself.
  Only `cited_ask` may store a turn, and only when the caller passes a `sessionId`.
- The checkpoint key is created on first use, lives outside `HERMES_HOME` and is never the Cited bearer.

## License

Apache-2.0. See `LICENSE` and `NOTICE`. Spanish version: [README.es.md](README.es.md).
