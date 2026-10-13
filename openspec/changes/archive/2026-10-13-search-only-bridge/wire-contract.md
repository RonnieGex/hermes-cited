# Search wire v1

Both contracts carry byte-identical `fixtures/search-wire-v1.schema.json` (SHA-256 `f09ad94cefa06df570d1c8fee681f47df9fd5ce162ea8ebb52943d1e343ceb00`) and
`fixtures/search-wire-v1.json`. Changes to the wire require a new version and both contracts to change together.
This is the closed HTTP JSON-RPC subset used by the native bridge, not an SDK negotiation flow.

Only `POST /api/chassis/mcp`, `Content-Type: application/json`, bearer `CITED_SEARCH_TOKEN`, maximum body 16 KiB.
No CORS, cookies, batches, notifications, initialization, sessions, redirects or SSE. No other path is served.
Authenticated `tools/list` uses `{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}` and returns
`{"jsonrpc":"2.0","id":1,"result":{"tools":[{"name":"cited_search","description":"Search unsealed document passages.","inputSchema":<arguments schema>}]}}`.
The inputSchema is exactly `$defs.arguments`; tools/list envelopes use the delivered listRequest/listResponse schemas. `tools/call` and its response follow `$defs.request/response`.
The response id equals the request id. Query length counts Unicode code points; no type coercion or trimming
changes the transmitted query. Whitespace-only queries are invalid. Limit defaults to 5; booleans are not integers.
Unknown properties are invalid. Passage numbers are sequential 1..count, count is at most the requested limit;
position is zero-based, heading is string or null, document is the stored name, excerpt is literal source text.
Empty retrieval returns an empty passages array and one text item whose text is empty.
For nonempty retrieval each text block is `[n] document\nheading\nexcerpt` (omit heading and its newline when null),
joined with two LF characters. No answer composition, seal or decision record is returned or written.

Authentication precedes body parsing: absent/wrong bearer -> HTTP 401 `{"code":"unauthorized"}`, never reflected.
Authenticated errors use `$defs.error`: malformed JSON -> HTTP 400/-32700 with null id; invalid envelope/id,
batch or notification -> HTTP 400/-32600 with null id; invalid arguments -> HTTP 200/-32602; unknown method/tool
-> HTTP 200/-32601; retrieval failure -> HTTP 200/-32603 with generic text. Valid-id errors echo that id.
Oversized body -> HTTP 413 `{"code":"body_too_large"}`; wrong method -> 405; other paths -> 404.
The client rejects non-JSON, a mismatched id, malformed schema, isError responses, and JSON-RPC errors with a
redacted diagnostic sentence. It never returns raw HTTP error bodies, exceptions, credentials or headers.

Search-mode CITED_URL must be an explicit http/https origin without userinfo, path (including a trailing slash),
query or fragment. Append exactly `/api/chassis/mcp`. The configured origin is the only permitted destination;
every 3xx is refused without a second request, including redirects to the same origin. Timeout is 30000 ms by
default, an integer from 1 through 120000 (`CITED_TIMEOUT_MS`); invalid configuration makes zero requests.
Before building any model-visible output recursively reject the current token reflected in any response string.

The tool returns a JSON *string* to the model, not the RPC envelope:
`{"cited_tool":"cited_search","query":<unchanged query>,"text":<content[0].text>,"passages":[<passage plus lines>]}`.
`lines` is `[{"line":1,"text":<first line>}, ...]`, splitting on LF, stripping trailing CR from each line, dropping whitespace-only lines and
numbering the retained lines consecutively from 1 (the existing render.numbered_lines algorithm). No PID, citation seal, audit entry or full-mode composition is introduced in search.
The full-mode handler retains H0-H18 behavior; strict v1 validation belongs to the search-mode handler.
