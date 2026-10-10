# Install from GitHub, verified on 2026-10-10

What was checked: the one-step install the README promises, from the public repository, and then one question in
cited mode against a test Cited.

- Host: Hermes Agent v0.21.6+387 (commit `dce1e9b`) on Windows, in a temporary `HERMES_HOME`, never the user's.
- Cited: a build of `RonnieGex/cited` at `1cb8d4b`, which carries the `initialize` fix of
  [RonnieGex/cited#21](https://github.com/RonnieGex/cited/pull/21), with `CHAT_PROVIDER=fake`, a fresh store seeded from
  `samples/` with `scripts/mcp-seed.ts`, and a synthetic token, on `127.0.0.1:3246`.
- Model: `deepseek-flash` through `--provider deepseek`.

## Install

```bash
hermes plugins install RonnieGex/hermes-cited --enable
```

Exit 0 and `✓ Plugin hermes-cited enabled.` The clone in `$HERMES_HOME/plugins/hermes-cited` is at `eb02713`, and
`hermes plugins list` shows `hermes-cited │ enabled │ 0.1.0`.

## A question in cited mode

The `.env` of the temporary home declares `CITED_URL`, `CITED_MCP_TOKEN` and `CITED_DEFAULT_MODE=cited`.

```bash
hermes chat --oneshot -q "¿Cuánto cuesta la afinación de bicicleta en Café La Horquilla?" --format stream-json --source tool --provider deepseek -m deepseek-flash
```

Exit 0. The tool calls, in order:

1. `tool_describe` with `cited_search`, `cited_ask` and `cited_quote`.
2. `cited_search` with the query `afinación de bicicleta Café La Horquilla precio`.
3. `cited_quote` with `passage: P1` and `lines: [5]`.

The terminal record (`type: result`), whole:

```text
Según tus documentos:

- Afinación de bicicleta: 380 pesos. [1]
Fuente: cafe-la-horquilla.md - Precios

Note on delivery: interim assistant messages are on for this platform, so commentary may have been visible before this answer was verified. Turn them off with `display.platforms.cli.interim_assistant_messages: false` (or `display.interim_assistant_messages: false`). The verified seal is withheld here because something else may have been visible before this answer was verified. The text above is still copied from the documents of this turn.
```

The line is the plugin's render of the passage the model chose, not the model's prose. The seal is withheld, as the
contract requires on every route with this host, and the note names the switch that made the surface not clear.

## Consistency record

From the installed plugin, `python -m hermes_cited.verify_log $HERMES_HOME/cited/audit.jsonl` printed
`OK: 1 entries, the chain is internally consistent (this is not a custody check; see the README).`

The synthetic token appears in none of the outputs: the stream, its stderr and the record.
