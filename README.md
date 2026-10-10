# hermes-cited

Cited in [Hermes Agent](https://github.com/NousResearch/hermes-agent): a native Python plugin that gives
Hermes the read-only tools of [Cited](https://github.com/RonnieGex/cited) as native tools, two conversation
modes, and a cited mode whose answer is **written by the plugin** from the exact lines the model chose, next
to a local, hash-chained consistency record of the plugin's composition.

Built by Katalis. Apache-2.0.

- **Mode dot** (the default): normal answers; Cited is used when it helps. Nothing in dot mode is verified,
  whatever the text says: this version of the plugin writes no seal, so the phrase `Verified by Cited` in an
  answer never comes from the plugin, and the model's text is delivered intact.
- **Mode cited**: the model only *chooses*. It searches Cited and then calls `cited_quote` with the
  identifier of the passage and the numbered lines the user should read. The plugin discards the model's
  prose whole and renders those lines **byte for byte**, each with its document, its section and its `[n]`
  mark. The seal `Verified by Cited` is retained — not emitted — while the host exposes no accreditable
  delivery contract, and the answer carries the fixed note that says so (D11). Nothing to choose is the fixed
  refusal `It is not in the documents.`

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
| `CITED_LANGUAGE` | no | The language of the cited-mode render, `es` or `en`. `es` by default. The quoted lines are always the document's own bytes. |

Without `CITED_URL` or `CITED_MCP_TOKEN` the search tools answer a sentence that names the missing variable.
They never raise into Hermes, and Hermes keeps working.

## The three native tools

| Tool | Input | Output |
|---|---|---|
| `cited_search` | `query` (required), `limit` (1 to 8, 5 by default) | The passages that match, each with `pid`, `n`, `document`, `heading`, `position`, `excerpt` and its numbered `lines`. |
| `cited_ask` | `question` (required), `sessionId` (optional) | `status` (`answered` or `refused`), `answer` and the numbered `citations`, each with `pid` and its numbered `lines`. |
| `cited_quote` | `passage` (the `pid` of a passage or citation of this turn, like `P1`, or its number `n` while that number is not ambiguous), `lines` (their line numbers, in order) | The exact text of those lines, and the plugin records the choice for the answer. |

`cited_search` and `cited_ask` are the two tools that call `POST <CITED_URL>/api/mcp` with the JSON-RPC
`tools/call` method and `Authorization: Bearer <CITED_MCP_TOKEN>`; the network, the token and the Cited
pipeline live only there. `cited_quote` is a local selection of the plugin: it makes no HTTP request and
never leaves the excerpts of its own turn. The three are native and not an MCP configuration because the
installation is then one step and because the plugin needs to see every result to render the answer and to
write the record.

## One identifier per passage

Every passage and every citation a cited tool returns in a turn receives its own identifier `pid`: `P1`,
`P2`, and so on, in the order the calls returned them. `cited_quote` takes that `pid`, not the number `n`,
because two searches of the same turn can both return a passage 1 and the numbers then collide. The turn
keeps the mapping from the `pid` to the call, to the original `n` of the Cited result, to the document, to
the section and to the position. The `[n]` mark of the render, the selection of the model and the row of the
record are the same reference. A numeric `passage` is accepted only while it identifies exactly one passage
of the turn; when it is ambiguous the selection is rejected and the error asks for the `pid`. A chosen block
or a metadata value that carries the phrase `Verified by Cited` is data like any other: this version writes
no seal, so the phrase never comes from the plugin (D12).

## The two modes

- `/cited` turns cited mode on for this conversation; `/dot` turns it off. The key is the session when the
  surface exposes one and the profile otherwise. `CITED_DEFAULT_MODE` sets the initial mode. The
  confirmation of `/cited` states the scope of the promise: the **final message** the plugin composes, not
  the drafts a surface may show while the answer is written and not the notices the host may append
  afterwards. It also states the condition of the seal: **the mark is not emitted today**, because the host
  exposes no accreditable delivery contract (D11), so the answer carries the fixed note that says the seal
  was withheld. The confirmation of `/dot` says that nothing in dot mode is verified, whatever the text
  says: this version writes no seal, so the phrase never comes from the plugin, and the model's text is
  delivered intact.
- In cited mode, `pre_llm_call` injects the rules: call Cited first, choose the lines with `cited_quote`,
  never write the answer. The model's text is discarded whole. A real render, from `cited_quote` with
  `{"passage": "P1", "lines": [4]}` against `cafe-la-horquilla.md · Precios`, is:

  ```
  Según tus documentos:

  - Afinacion de bicicleta: 380 pesos. [1]
  Fuente: cafe-la-horquilla.md - Precios

  Note on delivery: the host does not expose a per-turn delivery policy that accredits the effective
  receivers and the guarantee that the terminal message is the plugin's composition, so the plugin cannot
  prove what was delivered. The verified seal is withheld here because something else may have been visible
  before this answer was verified. The text above is still copied from the documents of this turn.
  ```

  With `CITED_LANGUAGE=en` the entry template is `From your documents:` and the refusal
  `It is not in the documents.`; the quoted lines never change language.

- Each passage or citation is split into lines deterministically (by line break; a paragraph with no break
  is one line) and numbered from 1. Every displayed block is *identical* to a full line of an excerpt of the
  turn: there is no Unicode normalisation, no substring and no word list, because the plugin wrote the block
  from the excerpt itself. A value, a subject or a seal the model writes can never reach the answer.
- Nothing to show, meaning no `cited_quote` call, a `status: refused` anywhere in the turn, or a turn with
  no excerpt, becomes the fixed refusal `No está en los documentos.` (`It is not in the documents.` in
  English). It never carries the seal.
- The seal `Verified by Cited` would be added only by the plugin, only after the exact delivered text was
  persisted, and only when the delivery policy allows it **and** the host accredits the delivery of the turn
  (D11). While the host does not, the mark is not emitted on any route and the answer says so with the fixed
  note. The mark `[1]` and the source are generated by the plugin; the model writes none of them.
- Dot mode delivers the model's text **intact**. Nothing in dot mode is verified, whatever the text says:
  this version of the plugin writes no seal, so the phrase `Verified by Cited` in a dot answer never comes
  from the plugin (D12). A dot turn that carries the phrase is a text the model wrote, and the row records
  exactly the text that is delivered.
- Totals and other computed values are out of scope for this round: they belong to the documents mission,
  where a tool computes them in code and records their provenance.

## Delivery: one snapshot at the start of the turn

Hermes v0.21.6+387 hands every text delta to the screen, the messaging surface, the interim commentary and
streaming TTS **before** `transform_llm_output` decides. No plugin hook can retain those deltas; that is a
host limitation, and this plugin states it instead of hiding it. For a cited turn that reaches the hook, the
plugin's composition is the documentary render, the fixed refusal or the operational refusal; the host may add
text afterwards. It is not a promise about what a draft may have shown on screen while the answer was written.

The plugin decides the seal from one **snapshot taken at the start of the cited turn** and freezes that
snapshot in the turn, so a configuration change during the turn cannot change a decision already taken. The
snapshot resolves the effective streaming with the host's own `gateway.config.StreamingConfig`, so `mode`,
`enabled`, `transport` and the per-platform override mean what Hermes means by them, and it covers every
surface of the host that delivers text or voice:

| Surface | The seal |
|---|---|
| Every surface | **Retained.** The host of this release exposes no per-turn policy of the effective receivers and no guarantee that the terminal message is the plugin's composition, so the single capability point (`delivery.accredited_delivery()`) answers "not accredited" and the mark is not emitted (D11). A future host version that offers both halves turns the seal back on, and only a test of the real host demonstrates it. |
| `api_server` (the SSE route of the desktop app) | The readable surface is never clear: that surface builds its own stream, which no configuration here reaches. |
| `desktop` | The readable surface is never clear, for the same reason: the app wires its own SSE stream. |
| Messaging platform (Telegram, Slack, Discord, WeCom, Feishu, DingTalk, QQ and the like) | The readable surface is not clear when the effective `streaming` is on for that platform. |
| Interim assistant commentary (`display.interim_assistant_messages`) | Not clear when the interim messages are on for the platform of the turn. |
| Streaming TTS (`tts.auto_tts`) | Not clear when `tts.auto_tts` is on: voice is a delivery the turn cannot take back. |
| A platform the plugin cannot resolve | Not clear: it cannot prove that nothing else was visible. |
| A configuration that cannot be read, or a `FailedConfigRead` | Not clear, for the same reason. |
| CLI | Not clear with `display.streaming: true` or with interim commentary on. With both off the readable surface is clear, and the seal is still retained because the host is not accredited. `--format stream-json` still emits `text` events, so **a consumer of that format must show only the terminal `result` record**; a consumer that concatenates `text`, reasoning or comments would show the draft. |

An inbound-only surface (`local`, a webhook) never delivers a draft to a user, so its readable surface is
clear unless another reason applies. When the seal is withheld, the answer carries a fixed note that names
the surface and what to turn off, or the missing accreditation.

The exact configuration for the gateway:

```yaml
streaming:
  enabled: false                 # master switch; `transport: off` also disables
display:
  streaming: false               # CLI only
  interim_assistant_messages: false
  platforms:
    telegram:
      streaming: false           # narrows only; never enables streaming on its own
      interim_assistant_messages: false
tts:
  auto_tts: false
```

`display.streaming` is CLI-only; the gateway resolves `display.platforms.<platform>.streaming` first. The
plugin would grant the seal only when the snapshot affirmatively shows that nothing else could have been
visible **and** the host accredits the delivery of the turn; while the host does not, the mark is retained on
every route. `docs/upstream-proposal.md` (English) specifies both halves of that contract: the per-turn
delivery-policy hook and the terminal composition boundary, with the file and line of each point it touches.
No pull request and no issue was opened upstream.

## The consistency record

Every plugin composition whose append succeeds appends one line, one JSON object, to
`$HERMES_HOME/cited/audit.jsonl`, in both
modes: the UTC timestamp, a monotonic `seq`, the identity of the log, the platform, the session, the turn
identifier, the user when there is one, the mode, the question, the Cited tool calls with their arguments
and the SHA-256 **and text** of every returned excerpt, the `pid` and the original number of every chosen
line with its document, section and position, the composed text, the transcript the plugin would have
returned without the seal, the delivery snapshot and its decision, the verifier result, and the fixed
`composition_note` that says what the row is, plus `prev_hash` and `hash`. The chain is
`hash = sha256(prev_hash + canonical_json(entry without hash))`. A persistence refusal writes no row at all,
so the record is the plugin's composition when the append succeeds and never a claim about the terminal
message.

**The row registers the plugin's composition.** The host may show drafts while the answer is generated and
add its own notices at the end (the file-mutation footer, an abnormal-exit explanation), so the row is **not**
a record of the terminal message. `composition_note` says exactly that in the entry itself.

The append holds an exclusive inter-process lock over `<log>.lock` and, **before writing one byte**, it
reads the whole chain and validates every schema, `seq`, link and hash. Any mismatch refuses the append and
leaves the file untouched: an append never restarts the chain from genesis. When the append fails, the cited
answer is the fixed operational refusal without a seal, because a refused answer is not a delivered one.

The record is for reviewing and reproducing each answer. It is **not tamper-proof** against whoever controls
the PC: someone who rewrites the file and recomputes the chain, or who cuts a complete suffix, produces a
file that is internally consistent. That is the exact scope of its `internal consistency`, and it is what
the verifier checks. No key and no file outside `HERMES_HOME` is written or read for the record. Audited
custody is a server-side property, and it arrives with Cited Ledger.

Verify it from the installed plugin, which is where the module is importable:

```powershell
Push-Location (Join-Path $env:HERMES_HOME 'plugins/hermes-cited')
try {
    python -m hermes_cited.verify_log (Join-Path $env:HERMES_HOME 'cited/audit.jsonl')
} finally {
    Pop-Location
}
# OK: 4 entries, the chain is internally consistent (this is not a custody check; see the README).  (exit 0)
# BROKEN: entry 3 was altered: its hash does not match its content.                                 (exit 1)
```

Use explicitly the Python of Hermes when `python` is not that interpreter. Running the module from another
directory fails with `ModuleNotFoundError: No module named 'hermes_cited'`: Hermes imports a directory
plugin as `hermes_plugins.<slug>` and never installs it as a top-level package.

## The boundary of a cited turn

For a cited turn that reaches the hook, the plugin's composition is the documentary render, the fixed refusal
or the operational refusal; the host may add text afterwards. The three possible compositions are:

1. the render of the literal lines the model chose, with the mark and the source, and the fixed note that
   says the seal was withheld — the mark itself is not emitted while the host does not accredit the delivery;
2. the fixed localized refusal `No está en los documentos.` (`It is not in the documents.` in English), when
   there is nothing to show, when Cited refused, or when no chosen block passes the by-construction check;
3. the fixed localized operational refusal with an incident code, with no seal and with no error detail
   interpolated.

The host can still add its own text after the hook, such as the footer of the file mutations that failed
(`agent/turn_finalizer.py:645-647`); where it does, the terminal message can differ from that composition,
and the plugin does not claim this boundary for those paths. The third contract of
`docs/upstream-proposal.md` asks for the composition boundary that would close that gap.

A single boundary around the whole transformer turns any exception of reading the configuration, resolving,
rendering, composing or persisting into the third answer. The incident code is generated without ever
raising: if the entropy dependency fails, a constant reserve code is used, so the emergency exit depends on
no entropy, no disk, no configuration and no logger. The diagnostic is redacted of the bearer and goes
to the logger and to `stderr` only, never into the answer. The turn state is dropped in a `finally`, so a
failure of one turn cannot leak into the next. Dot mode keeps its own contract and never answers with a
refusal, because in dot mode the plugin never promised the text: it never rewrites the model's text either,
so a failure of its pass-through returns `None` and leaves the text in place.

## Host incompatibilities

- **An empty model response never reaches the hook.** `agent/turn_finalizer.py:501` of the pinned host
  returns before invoking `transform_llm_output` when the text of the model is false. A cited turn whose
  model answer is empty is therefore delivered empty: the plugin renders nothing and the record gets no row
  for it, because nothing was composed and nothing was delivered by the plugin. The plugin does not present
  that as covered.
- **The host can deliver a draft before the verdict.** The deltas of the surfaces listed above reach the
  user before `transform_llm_output` runs, and no plugin hook can retain them. The plugin cannot see the
  effective receivers of the turn, so it withholds the mark on every route.
- **The host can add text after the verdict.** The real finalizer applies `transform_llm_output`, persists
  the row, and only then appends its own text, such as the footer of the file mutations that failed
  (`agent/turn_finalizer.py:645-647`). The final message can therefore differ from the render the plugin
  composed and from the row the record stored. The plugin does not claim the render of C1 for a host path
  that can add text.

The contract this plugin asks Hermes for is three contracts: **synchronous retention of the delivery** — a
delivery policy resolved once per turn that holds text, reasoning, interim commentary, voice and the SSE route
until the verdict — **a final composition step even when the model's text is empty**, executed once per cited
turn before persisting and delivering, and **a final composition boundary after the host's own footer**, so the
plugin's composition runs after every footer or explanation the host adds and before the terminal delivery and
the delivered message is the text the record carries. `docs/upstream-proposal.md` carries the file and line of
each point that would change.

## The `cited` skill

The plugin ships a `cited` skill and registers it with `ctx.register_skill`, so it appears in the agent's
available skills while the plugin is enabled. It says when to use each tool, that the plugin writes the
cited answer and the model only chooses lines with `cited_quote`, that a refusal of Cited is passed on, and
that in cited mode nothing is completed from the model's own knowledge. In the MCP-only route the two search
tools exist, but `/cited`, `/dot`, `cited_quote`, the render and the record do not: there is no plugin to
run them.

## The MCP route, with no installation

Cited can also be reached as an MCP server, with no plugin at all. This is the route for any MCP client; in
Hermes the two search tools then appear as `mcp__cited__cited_search` and `mcp__cited__cited_ask`. The skill
is what makes the agent reach for Cited before the web, so copy
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

`${VAR}` is read from `$HERMES_HOME/.env` or the environment. Add `trust: untrusted` to that entry to let
the two tools, which are read-only, run without an approval prompt. Verify it with `hermes mcp test cited`,
which must connect and list both tools.

## What was tested (2026-10-10)

Everything below was run on 2026-10-10 with Hermes Agent **v0.21.6+387 (`dce1e9b`)**, the DeepSeek model
(`--provider deepseek -m deepseek-flash`), a Cited built from `origin/main` (`ef11f88`, the merged PR #21)
in its own temporary worktree and served on `127.0.0.1:3246` with the four documents of its `samples/`, and
a temporary `HERMES_HOME`. `scripts/gate.py`, run with the Python of the Hermes venv, affirms the properties
and prints `GATE: GREEN`; its output and the transcripts are inside the changes
(`openspec/changes/hermes-plugin-r3/reports/` and `openspec/changes/hermes-plugin-r4/reports/`).

Round 4 (2026-10-10) retired the local custody of the record, so what remains is the chained consistency
record described above, with no key and no file outside `HERMES_HOME`. It also took the delivery decision
with a snapshot at the start of the turn, added `api_server`, the interim commentary and streaming TTS to
the surfaces that withhold the seal, gave every passage its `pid`, and put one boundary around the whole
cited transformer.

Round 8 (2026-10-10, D12) retired the protection of the reserved mark. With D11 the plugin emits no seal on
any route, so no authentic seal exists that anyone could forge, and every hand-written reader of the host's
Markdown either opened a new evasion or deleted legitimate text. Dot mode now delivers the model's text
intact and records exactly that string, a documentary line that carries the phrase is data like any other,
and the documentation says in plain language that nothing in dot mode is verified. The activation of the
seal, when the host offers an accreditable delivery contract, requires protecting the reserved mark again
with the render semantics of the host, checked against its consumer (`docs/upstream-proposal.md`).

**The real `%LOCALAPPDATA%\hermes` was never written and never used as the target of any run of this
round.** The isolated final run and its gate use temporary homes only. One historical run of round 1, early
in `mision-cited-hermes.md`, executed `hermes mcp test cited` **without** `HERMES_HOME` and read the real
configuration (a read-only connection test against the live Cited on port 3240, which failed). It happened
once, it is preserved here instead of being claimed away, and it is reported as a RISK in
`tasks/entrega-cited-hermes-r2.md`. No byte was written under the real home, and no run of round 2 or round
3 touched port 3240.

| What | Result |
|---|---|
| The unit suite (`pytest`) | green: the client and its redirect refusal, the three tools and the per-turn `pid`, the by-construction verifier, the plugin-written render, the chained consistency record and its inter-process lock, the boundary with its three possible answers, the delivery snapshot of every surface, the modes and the packaged skill, plus one adversarial case per finding of the reviews |
| `hermes mcp test cited` | connected, `Tools discovered: 2` (`cited_search`, `cited_ask`) |
| `hermes plugins install "file:///…" --enable --yes-deps` | installed into `$HERMES_HOME/plugins/hermes-cited` and enabled |
| The real loader | the installed plugin loads with the Hermes plugin manager and registers its three hooks |
| The price question in the MCP route | the stream calls `mcp__cited__cited_search` and answers **380 pesos** with the citation of `cafe-la-horquilla.md · Precios` |
| The price question in cited mode | the stream calls the native `cited_search`, then `cited_quote`; the delivered answer is the plugin render of the line, with `Fuente: cafe-la-horquilla.md - Precios` and the mark `[1]`, and the seal retained because the host does not accredit the delivery, as the [transcript](openspec/changes/hermes-plugin-r4/reports/2026-10-10-step-5-e2e.md) shows |
| `What guarantee on repairs does bike-workshop-policies.md state?` | the render carries **90 days** from `bike-workshop-policies.md · Guarantee`, with the seal retained in the same [transcript](openspec/changes/hermes-plugin-r4/reports/2026-10-10-step-5-e2e.md) |
| A question the samples do not answer | exactly `No está en los documentos.`, with no datum and no seal |
| The consistency record of those turns | one entry per turn with the exact count; `python -m hermes_cited.verify_log` from the installed plugin reports the internal consistency of the chain and exits 0; altering an entry, removing one from the middle, reordering it or introducing a gap makes it exit 1, while a complete suffix cut or a file rewritten with every hash recomputed stays internally consistent, which is the documented limit of the check |
| Dot mode | the model's text is delivered intact and the entry is logged with the verifier marked as not applied; the row records exactly the text that is delivered, and a documentary line that carries the phrase `Verified by Cited` is data, because this version writes no seal (D12) |
| The cited contract | in cited mode, adversarial cases prove that a changed value, a moved subject, a substring, free prose and a forged seal never reach the delivered answer; dot mode passes the model's text through (D12) |
| The boundary | a failure of reading the configuration, resolving, rendering or persisting delivers the fixed operational refusal with an incident code — including when the entropy dependency of that code fails, which then uses the constant reserve code — and the plugin's composition of a cited turn is one of the three |
| The delivery policy (fixtures, apart from the run above) | `api_server`, `desktop`, an unknown platform and an unreadable configuration mark the readable surface as not clear; so do `streaming` on for a messaging platform, `interim_assistant_messages` on, and `tts.auto_tts` on; in a synthetic quiet-CLI fixture the readable surface is clear and the seal is still retained because the host is not accredited, and a change of the configuration after the turn started does not change its decision |
| The empty response | the real finalizer returns without invoking the hook, and the plugin reports that as a host incompatibility instead of covering it |
| The `cited` skill | registered by the plugin and present in the installed tree, with the `cited_quote` rule and the plugin-only note |

Not tested in this round: a real Telegram/Slack/Discord/WeCom bot (the delivery policy is proven in-process
and against the host's real `StreamingConfig` class), an interactive TUI, macOS or Linux, and installation
against the public GitHub URL.

## Security

- The token only travels in the `Authorization` header of a request to the configured `CITED_URL`. A `3xx`
  is refused before any second request, so a redirect can never carry the bearer to another origin.
- Before building any visible result, in success and in error, the client rejects a response that reflects
  the token in any string; the answer is discarded and nothing of it is shown or recorded.
- Before hashing and appending, every field of the record entry is redacted recursively, including the
  question, the arguments, the excerpts, the response and the errors.
- `401`, `403`, `404`, `405`, a timeout and a network failure each become a distinct sentence the model can
  read. The plugin never writes a secret to a log, a tool result, the record file or the evidence.
- The plugin is read-only against Cited: it never writes a document and never calls a language model itself.
  Only `cited_ask` may store a turn, and only when the caller passes a `sessionId`.
- The consistency record is a local file for review and reproduction only. It is not custody and it is not
  tamper-proof: whoever controls the machine can rewrite it and recompute the chain. No key is created or
  read, and no file outside `HERMES_HOME` is written for it.

## License

Apache-2.0. See `LICENSE` and `NOTICE`. Spanish version: [README.es.md](README.es.md).
