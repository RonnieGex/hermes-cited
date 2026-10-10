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

## The two tools

| Tool | Use it for | Arguments |
|---|---|---|
| `cited_search` | The raw passages that match a query, with the document, the section, the position and the exact text of each one. | `query` (required), `limit` (1 to 8, 5 by default) |
| `cited_ask` | A written answer from the documents, with numbered citations and the passage each one came from. | `question` (required), `sessionId` (optional, to keep a thread) |

In the MCP route, without the native plugin, the same two tools appear as
`mcp__cited__cited_search` and `mcp__cited__cited_ask`. They are the same two calls.

## Rules

- Transmit what Cited returned without changing a datum: the answer, the passages, the excerpts, the
  numbers, the document names and the citation numbers. Never round, convert, translate or reword a value.
- In cited mode, copy each sentence or line that carries a number, a price, a unit, a date or a code
  between `« »` exactly as an excerpt of the turn writes it, with its subject, on its own line, and
  exactly once. Never write a datum outside `« »`, not even to announce or repeat the quotation. A
  valid answer is:
  `«Afinación de bicicleta: 380 pesos.»`
  `Fuente: cafe-la-horquilla.md, Precios [1].`
  A value glued to a subject the excerpt does not give it (`Espresso: «380 pesos.»`) is refused, and
  so is a value repeated outside the quotation.
- Cite each passage by its number, like [1], and name the document and its section.
- When Cited refuses, pass the refusal on. When the passages do not hold the answer, say plainly that it
  is not in the documents. Never fill that gap from the web or from general knowledge.
- When the question is in one language and the documents may be in another, search with the key terms
  translated too: Cited's keyword search does not translate.
- Re-run `cited_search` whenever you need a number for a document you are about to write, and build
  line items in code from the returned numbers instead of computing them mentally.

## The two modes

The two modes, the verifier and the audit log belong to the **native plugin** (`hermes-cited`). In the
MCP-only route the same two tools exist, but `/cited`, `/dot`, the verifier and the audit log do not:
there is no plugin to run them.

- **Mode dot** (`/dot`, the default): Cited is used when it helps, and the answer is not verified.
- **Mode cited** (`/cited`): before the turn, the strict rules are injected: answer only from the
  excerpts Cited returns in that same turn. Afterwards a deterministic verifier accepts a datum only
  when the whole sentence or line that carries it appears verbatim inside an excerpt of the turn.
  An answer that passes ends with `Verified by Cited` and its sources; an answer with a value no
  excerpt contains is replaced by a refusal that names it. Never state in cited mode anything you did
  not read in an excerpt. On a messaging platform whose streaming is on, the seal is withheld and the
  answer says so, because a draft may already have been visible.
- `CITED_DEFAULT_MODE` sets the mode a conversation starts in (`dot` unless it says `cited`).
