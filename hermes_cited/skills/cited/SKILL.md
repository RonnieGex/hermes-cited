---
name: cited
description: >
  Cited is this user's verified knowledge base: the documents of their businesses (price lists,
  policies, manuals, procedures, product data) served by a Cited server wired into Hermes. Use it
  FIRST, before web search, memory or general knowledge, whenever a question is about the user's own
  businesses, products, prices, services, policies, procedures or manuals, or names a business or
  document that may live there (for example Cafe La Horquilla or the bike workshop). Use it also to
  ground any document you write with the user's data (quotes, invoices, reports).
---

# Cited: answers from the user's own documents

## When

- Any question about the user's businesses, prices, services, policies, procedures, manuals or products.
- Before writing a quote, an invoice, a report or any document that needs the user's data.
- Do not search the web first for these: a business that is not on the internet can still be in Cited.

## The three tools

| Tool | Use it for | Arguments |
|---|---|---|
| `cited_search` | The raw passages that match a query. Every passage carries `n`, its document, its section, its position, its exact text and its numbered `lines`. | `query` (required), `limit` (1 to 8, 5 by default) |
| `cited_ask` | A written answer from the documents, with numbered citations and the passage each one came from, also split into numbered `lines`. | `question` (required), `sessionId` (optional, to keep a thread) |
| `cited_quote` | In cited mode, choose the exact lines the user will read. | `passage` (the `n` of a passage or citation of this turn), `lines` (their line numbers, in order) |

In the MCP route, without the native plugin, the first two tools appear as
`mcp__cited__cited_search` and `mcp__cited__cited_ask`. They are the same two calls; `cited_quote` and
the plugin-written answer exist only in the native plugin.

## Rules

- Transmit what Cited returned without changing a datum: the answer, the passages, the excerpts, the
  numbers, the document names and the citation numbers. Never round, convert, translate or reword a value.
- In cited mode, **the plugin writes the answer**. Your own prose is discarded; only the lines you choose
  with `cited_quote` are delivered. Call `cited_search` or `cited_ask` first, then `cited_quote` for the
  lines the user should see. A paragraph with no line break is one line.
- The plugin copies each chosen line byte for byte and adds, itself, the `[n]` mark, the source
  (`Fuente: <document> - <section>`) and the seal `Verified by Cited`. Never write those yourself, and
  never write a datum outside `cited_quote`.
- When Cited refuses, or the passages do not hold the answer, call no `cited_quote`: the plugin answers
  that it is not in the documents. Never fill that gap from the web or from general knowledge.
- When the question is in one language and the documents may be in another, search with the key terms
  translated too: Cited's keyword search does not translate.
- Re-run `cited_search` whenever you need a number for a document you are about to write, and build
  line items in code from the returned numbers instead of computing them mentally.

## The two modes

The two modes, the render and the audit log belong to the **native plugin** (`hermes-cited`). In the
MCP-only route the same two search tools exist, but `/cited`, `/dot`, `cited_quote`, the render and the
audit log do not: there is no plugin to run them.

- **Mode dot** (`/dot`, the default): Cited is used when it helps, and the answer is not verified.
- **Mode cited** (`/cited`): before the turn, the rules are injected: search Cited first, then choose the
  lines with `cited_quote`. The plugin discards the model's text and renders the chosen lines, copied
  byte for byte, each with its source and its `[n]` mark. A real render of `cited_quote` with
  `{"passage": 1, "lines": [4]}` against `cafe-la-horquilla.md · Precios` is:

  ```
  Según tus documentos:

  - Afinacion de bicicleta: 380 pesos. [1]
  Fuente: cafe-la-horquilla.md - Precios

  Verified by Cited
  ```

  When nothing was chosen, Cited refused or the turn had no excerpt, the answer is exactly
  `No está en los documentos.`. On a messaging platform whose streaming is on, the desktop app or the
  CLI with streaming on, the seal is withheld and the answer says so, because a draft may already have
  been visible. `CITED_LANGUAGE` picks `es` (default) or `en` for the entry template and the refusal;
  the quoted lines never change language.
- `CITED_DEFAULT_MODE` sets the mode a conversation starts in (`dot` unless it says `cited`).
