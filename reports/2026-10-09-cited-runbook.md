# Cited MCP runbook — probe of `POST /api/mcp`

Date of the probe: 2026-10-09 (local, Mexico) / 2026-10-10 04:33–04:35 UTC.
Product: Cited (Next.js knowledge base) at `C:\Users\Franc\Documents\katalis-dev\community-mcpfix`,
branch `fix/mcp-initialize-version-header`, commit `e9bc92574cc0924e4c397499304d8ffb1b25968a`.
The companion worktree `community-hermes` (`origin/main` a044405) was **not** started or modified.

Every command below is copy-pasteable in **Windows PowerShell 5.1** (`$PSVersionTable.PSVersion` = `5.1.26100.9549`).
This matters: the shell is not `pwsh` 7, so `Invoke-WebRequest -SkipHttpErrorCheck` does not exist and PowerShell's
native-argument quoting is the 5.1 flavour (see "Gotchas"). All HTTP probing was therefore done with `curl.exe`.

## 0. Environment facts

| Fact | Observed value |
|---|---|
| Default `node` on PATH | `v24.11.0` — **below** the repo `engines` range `>=24.15.0 <25.0.0` |
| Node 24 via npx | `npx -y -p node@24 node --version` → `v24.21.0` |
| Node 24 binary resolved by npx | `C:\Users\Franc\AppData\Local\npm-cache\_npx\387698761821791d\node_modules\node\bin\node.exe` |
| Prebuilt `.next` | present, `.next\BUILD_ID` mtime `2026-10-09 22:18:41` (the probe did **not** rebuild) |
| `.env` files in the worktree | **none** (`Test-Path` false for `.env`, `.env.local`, `.env.production`, `.env.production.local`, `.env.development`) |
| Port used by the probe | **3247 only**. Ports 3240 and 3246 were never touched. |
| Other traffic on the box | a pre-existing, unrelated `next start --port 3240` process was running during the probe (another agent). It was left untouched. |

`.env.example` is safe and was read; no `.env` file was opened.

---

## 1. Server startup

### 1.1 Which environment variables the route actually needs

Read: `docs/mcp.md` (§1 and §9), `scripts/gate-mcp.mjs` (`serverEnvironment()`, lines 575–590), `scripts/mcp-smoke.mjs`,
`app/api/mcp/route.ts`, `lib/mcp/auth.ts`, `lib/mcp/tools.ts`, `lib/store/path.ts`, `lib/settings/providers.ts`.

| Variable | Needed for `/api/mcp`? | Evidence |
|---|---|---|
| `CITED_MCP_TOKEN` | **Strictly required** — without it the route is off and answers 404 to everything | `lib/mcp/auth.ts:13-15`, `app/api/mcp/route.ts:38-43`; `docs/mcp.md:15-18` |
| `DATABASE_URL` (or `TURSO_DATABASE_URL`) | **Required to return the corpus**; the route still answers 200 with an empty passage list against a missing/empty store | `lib/store/path.ts:6-11`; default `.data/katalis.sqlite` |
| `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN` | Not required, but **must be forced empty** for isolation because `TURSO_DATABASE_URL` wins over `DATABASE_URL` | `lib/store/path.ts:6-10` |
| `CHAT_PROVIDER=fake` | **Required only for `cited_ask` to answer offline**; `cited_search` works without any provider | `lib/mcp/tools.ts:340-346`, `lib/models/providers.ts:60-62` |
| `EMBEDDINGS_PROVIDER` | **Can be omitted**; empty resolves to keyword mode and `cited_search` still returns passages | `lib/settings/providers.ts:274-290`, `lib/mcp/tools.ts:267-276` |
| `MCP_RATE_LIMIT_PER_HOUR` | Optional, default 120 | `lib/mcp/limits.ts:14-21` |
| `ADMIN_PASSWORD` | **Not needed** by `/api/mcp` | not imported by the route chain; only the admin panel uses it |
| `ADMIN_SESSION_SECRET` | **Not needed**; MCP passes `quota: "external"`, so the IP hash that would use it is skipped | `lib/answer/ask.ts:73-84`, `lib/mcp/tools.ts:366-368` |
| `VOICE_TOOL_SECRET` | **Not needed** | voice routes only |
| `ENCRYPTION_KEY` | **Not needed**; only opened when a key saved in the panel is used | `lib/secrets/index.ts` |
| `ALLOW_LOCAL_PROVIDERS` | Not needed for `fake` | `lib/providers/address.ts:25,68` |
| `PORT` | Not required; the port is passed on the command line | `next start --help` |

The probe deliberately omitted `ADMIN_PASSWORD`, `ADMIN_SESSION_SECRET`, `VOICE_TOOL_SECRET`, `ENCRYPTION_KEY`,
`ALLOW_LOCAL_PROVIDERS`, `EMBEDDINGS_PROVIDER` and `CHAT_MODEL` and every provider API key, and the endpoint answered
normally. Environment is read **at request time**, so changing `CHAT_PROVIDER` requires a process restart.

### 1.2 Does `npx -y -p node@24 ... next start` work?

**The literal form does NOT work on Windows.** Running exactly

```powershell
npx.cmd -y -p node@24 node_modules/next/dist/bin/next start -H 127.0.0.1 -p 3247
```

fails because `node_modules/next/dist/bin/next` is a JS file with a shebang, not an executable `cmd` shim. Observed
stderr (empty stdout; the server never listened):

```
"node_modules" no se reconoce como un comando interno o externo,
programa o archivo por lotes ejecutable.
```

The equivalent **with an explicit `node` works**:

```powershell
npx.cmd -y -p node@24 node node_modules/next/dist/bin/next start -H 127.0.0.1 -p 3247
```

Observed with that form (no token configured, so the probe URL answered 404):

```
▲ Next.js 16.4.0
- Local:         http://127.0.0.1:3247
- Network:       http://127.0.0.1:3247
✓ Ready in 559ms
✓ Running next.config.ts took 171ms
```

Wall time from `Start-Process` to the first HTTP answer for that npx form: **5911 ms** (npx startup overhead). For the
measured Phase A server below the npx-resolved `node.exe` was invoked directly, which is faster and is what all protocol
outputs in this runbook were captured against.

### 1.3 Exact startup command used for the measured probe (canonical)

```powershell
$node24 = 'C:\Users\Franc\AppData\Local\npm-cache\_npx\387698761821791d\node_modules\node\bin\node.exe'
$root   = 'C:\Users\Franc\Documents\katalis-dev\community-mcpfix'
$probe  = Join-Path $env:TEMP 'cited-mcp-probe'
New-Item -ItemType Directory -Force -Path $probe | Out-Null
$store  = Join-Path $probe 'cited.sqlite'
$token  = '<a random throwaway token, never committed>'

$env:DATABASE_URL            = $store
$env:TURSO_DATABASE_URL      = ''      # must win over DATABASE_URL; forced empty for isolation
$env:TURSO_AUTH_TOKEN        = ''
$env:CITED_MCP_TOKEN         = $token
$env:CHAT_PROVIDER           = 'fake'
$env:NEXT_TELEMETRY_DISABLED = '1'
$env:MCP_RATE_LIMIT_PER_HOUR = '1000'
$env:NODE_ENV                = 'production'

$out = Join-Path $probe 'server.out.log'
$err = Join-Path $probe 'server.err.log'
$p = Start-Process -FilePath $node24 `
  -ArgumentList @("$root\node_modules\next\dist\bin\next",'start','-H','127.0.0.1','-p','3247') `
  -WorkingDirectory $root -RedirectStandardOutput $out -RedirectStandardError $err -PassThru -WindowStyle Hidden
Set-Content -Path (Join-Path $probe 'server.pid') -Value $p.Id   # PID saved so a later shell can kill it
```

Observed `server.out.log` on the measured restart:

```
▲ Next.js 16.4.0
- Local:         http://127.0.0.1:3247
- Network:       http://127.0.0.1:3247
✓ Ready in 269ms
✓ Running next.config.ts took 59ms
```

`server.err.log` was empty. (The very first cold start logged `Ready in 371ms` / `Running next.config.ts took 125ms`.)

### 1.4 Exact readiness probe used

`POST /api/mcp` with `tools/list` is the cheapest request that proves the route is mounted (it consumes no tool quota).
Poll until curl returns a 3-digit status.

```powershell
$u = 'http://127.0.0.1:3247/api/mcp'
$sw = [System.Diagnostics.Stopwatch]::StartNew()
do {
  $code = curl.exe -sS -o NUL -w "%{http_code}" --max-time 2 $u `
    -H "Authorization: Bearer $token" -H 'Content-Type: application/json' `
    -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' 2>$null
  if ($code -match '^[1-5]\d\d$') { break }
  Start-Sleep -Milliseconds 100
} while ($sw.Elapsed.TotalSeconds -lt 60)
"READY_MS=$($sw.ElapsedMilliseconds) HTTP=$code"
```

Observed: `READY_MS=1276 HTTP=200` (and `973`–`1072` ms on the later restarts). A server started **without**
`CITED_MCP_TOKEN` also proves readiness: the same POST returns `404`, and curl still gets a status instead of a
connection error (`HTTP=404` was observed for the route-off server).

> Do **not** use `Invoke-WebRequest -SkipHttpErrorCheck` here: this PowerShell is 5.1 and the parameter does not exist;
> the resulting `ParameterBindingException` is swallowed by a `try/catch` retry loop and looks exactly like "server never
> became ready" (this cost the probe 90 s before it was diagnosed).

---

## 2. Seeding the throwaway database from `samples/`

`scripts/mcp-seed.ts` is run **directly by Node 24** (native TypeScript type stripping); no `tsx`, no
`--experimental-strip-types` and no `--env-file` are needed. It calls `openStore(prepareStorePath(storePath))` and
`ingestFolder(folder, { embeddings: null, signature: "keyword", ... })`, so it calls **no** provider
(`scripts/mcp-seed.ts:21-27`). It prints one line per document and a final `documents N, store PATH` (`:29-37`).

Exact command used (measured run):

```powershell
$node24 = 'C:\Users\Franc\AppData\Local\npm-cache\_npx\387698761821791d\node_modules\node\bin\node.exe'
$root   = 'C:\Users\Franc\Documents\katalis-dev\community-mcpfix'
$probe  = Join-Path $env:TEMP 'cited-mcp-probe'
$store  = Join-Path $probe 'cited.sqlite'

$env:DATABASE_URL       = $store
$env:TURSO_DATABASE_URL = ''
$env:TURSO_AUTH_TOKEN   = ''

& $node24 "$root\scripts\mcp-seed.ts" $store "$root\samples"
```

Equivalent npx form (same behaviour):

```powershell
npx -y -p node@24 node scripts/mcp-seed.ts <store-path> samples
```

Observed stdout (exit 0, **1093 ms**):

```
ingested README.txt (txt, 1 passages)
ingested bike-workshop-policies.md (md, 5 passages)
ingested cafe-la-horquilla.md (md, 4 passages)
ingested notas-del-negocio.txt (txt, 1 passages)
documents 4, store C:\Users\Franc\AppData\Local\Temp\cited-mcp-probe\cited.sqlite
```

Observed stderr (harmless; does not change the exit code):

```
(node:51604) [MODULE_TYPELESS_PACKAGE_JSON] Warning: Module type of
file:///C:/Users/Franc/Documents/katalis-dev/community-mcpfix/scripts/mcp-seed.ts is not specified and it doesn't
parse as CommonJS.
Reparsing as ES module because module syntax was detected. This incurs a performance overhead.
To eliminate this warning, add "type": "module" to
\\?\C:\Users\Franc\Documents\katalis-dev\community-mcpfix\package.json.
```

The store file was 139264 bytes after seeding. Environment needed: `DATABASE_URL` (belt-and-braces — the path is also a
positional argument) and forced-empty `TURSO_*`. No provider key, no `ADMIN_*`, no `ENCRYPTION_KEY`.

`docs/mcp.md:167-171` also shows an older, port-3230 variant (`node scripts/mcp-seed.ts .data/mcp-smoke.sqlite samples/`);
that writes inside the repo, which the probe avoided on purpose.

### 2.1 Exact `cited_search` result for `Café La Horquilla afinación de bicicleta precio`

Request body passed via `--data-binary` file (the `\u` escapes are the JSON escapes for `é`/`ó`; the server receives the
literal accented query):

```json
{"jsonrpc":"2.0","id":8,"method":"tools/call","params":{"name":"cited_search","arguments":{"query":"Café La Horquilla afinación de bicicleta precio"}}}
```

`HTTP/1.1 200 OK`, `content-type: application/json; charset=utf-8`, `cache-control: no-store`. Body observed (exact):

```json
{"jsonrpc":"2.0","id":8,"result":{"content":[{"type":"text","text":"Cited found 5 passage(s) for \"Café La Horquilla afinación de bicicleta precio\". Cite each one by its number, like [1].\n\n1. cafe-la-horquilla.md · Precios\nPrecios\n- Espresso: 35 pesos.\n- Café de olla: 45 pesos.\n- Pan dulce del día: 30 pesos.\n- Afinación de bicicleta: 380 pesos.\n- Cambio de cámara: 120 pesos.\n2. cafe-la-horquilla.md · Café La Horquilla\nCafé La Horquilla Somos un café y taller de bicicletas en el centro de la ciudad. Abrimos de martes a domingo.\n3. notas-del-negocio.txt\nCafé La Horquilla — notas del negocio Dirección: avenida central, frente al parque. Sin estacionamiento propio, pero hay uno público a media cuadra. Formas de pago: efectivo, tarjeta de débito y crédito. No aceptamos cheques ni transferencias para consumos menores a 200 pesos. Facturación: pedimos el RFC el mismo día de la compra. Las facturas del taller se emiten al terminar la reparación. Mascotas: bienvenidas en la terraza. Dentro del local solo si van en transportadora. Accesibilidad: la entrada tiene rampa y el baño es amplio. El taller está en planta baja. Contacto: mostrador, teléfono del local y correo del negocio. No damos precios por mensaje para trabajos que requieren revisar la bicicleta.\n4. bike-workshop-policies.md · Bike workshop policies at Café La Horquilla\nBike workshop policies at Café La Horquilla Everything a customer needs to know before leaving a bicycle with us.\n5. README.txt\nSample corpus of Cited These documents describe a fictional small business, Café La Horquilla, a café and bicycle workshop. They exist so the tests, the manual verification and the RAM measurement of this repository have something real to ingest. They were written for this repository. They are not the book of Construye, not golden cases, not holdout data, not a customer document and not prices of a real business.\n- cafe-la-horquilla.md: hours, prices and policies, in Spanish.\n- bike-workshop-policies.md: bookings, storage, groups and guarantee, in English.\n- notas-del-negocio.txt: payment, invoicing, pets, accessibility, in Spanish."}],"structuredContent":{"passages":[{"n":1,"document":"cafe-la-horquilla.md","heading":"Precios","position":2,"excerpt":"Precios\n- Espresso: 35 pesos.\n- Café de olla: 45 pesos.\n- Pan dulce del día: 30 pesos.\n- Afinación de bicicleta: 380 pesos.\n- Cambio de cámara: 120 pesos."},{"n":2,"document":"cafe-la-horquilla.md","heading":"Café La Horquilla","position":0,"excerpt":"Café La Horquilla Somos un café y taller de bicicletas en el centro de la ciudad. Abrimos de martes a domingo."},{"n":3,"document":"notas-del-negocio.txt","heading":null,"position":0,"excerpt":"Café La Horquilla — notas del negocio Dirección: avenida central, frente al parque. Sin estacionamiento propio, pero hay uno público a media cuadra. Formas de pago: efectivo, tarjeta de débito y crédito. No aceptamos cheques ni transferencias para consumos menores a 200 pesos. Facturación: pedimos el RFC el mismo día de la compra. Las facturas del taller se emiten al terminar la reparación. Mascotas: bienvenidas en la terraza. Dentro del local solo si van en transportadora. Accesibilidad: la entrada tiene rampa y el baño es amplio. El taller está en planta baja. Contacto: mostrador, teléfono del local y correo del negocio. No damos precios por mensaje para trabajos que requieren revisar la bicicleta."},{"n":4,"document":"bike-workshop-policies.md","heading":"Bike workshop policies at Café La Horquilla","position":0,"excerpt":"Bike workshop policies at Café La Horquilla Everything a customer needs to know before leaving a bicycle with us."},{"n":5,"document":"README.txt","heading":null,"position":0,"excerpt":"Sample corpus of Cited These documents describe a fictional small business, Café La Horquilla, a café and bicycle workshop. They exist so the tests, the manual verification and the RAM measurement of this repository have something real to ingest. They were written for this repository. They are not the book of Construye, not golden cases, not holdout data, not a customer document and not prices of a real business.\n- cafe-la-horquilla.md: hours, prices and policies, in Spanish.\n- bike-workshop-policies.md: bookings, storage, groups and guarantee, in English.\n- notas-del-negocio.txt: payment, invoicing, pets, accessibility, in Spanish."}]}}}
```

Key numbers: **5 passages**, first is `cafe-la-horquilla.md · Precios, position 2`, and that excerpt contains
`Afinación de bicicleta: 380 pesos.`

### 2.2 Exact `cited_search` result for `bike workshop guarantee repairs`

Request body:

```json
{"jsonrpc":"2.0","id":9,"method":"tools/call","params":{"name":"cited_search","arguments":{"query":"bike workshop guarantee repairs"}}}
```

`HTTP/1.1 200 OK`. Body observed (exact):

```json
{"jsonrpc":"2.0","id":9,"result":{"content":[{"type":"text","text":"Cited found 3 passage(s) for \"bike workshop guarantee repairs\". Cite each one by its number, like [1].\n\n1. bike-workshop-policies.md · Bike workshop policies at Café La Horquilla\nBike workshop policies at Café La Horquilla Everything a customer needs to know before leaving a bicycle with us.\n2. README.txt\nSample corpus of Cited These documents describe a fictional small business, Café La Horquilla, a café and bicycle workshop. They exist so the tests, the manual verification and the RAM measurement of this repository have something real to ingest. They were written for this repository. They are not the book of Construye, not golden cases, not holdout data, not a customer document and not prices of a real business.\n- cafe-la-horquilla.md: hours, prices and policies, in Spanish.\n- bike-workshop-policies.md: bookings, storage, groups and guarantee, in English.\n- notas-del-negocio.txt: payment, invoicing, pets, accessibility, in Spanish.\n3. bike-workshop-policies.md · Guarantee\nGuarantee Every repair carries a 90 day guarantee on the work. Parts carry the guarantee of their maker. Bring the ticket; without it we can still look up the repair by the frame number."}],"structuredContent":{"passages":[{"n":1,"document":"bike-workshop-policies.md","heading":"Bike workshop policies at Café La Horquilla","position":0,"excerpt":"Bike workshop policies at Café La Horquilla Everything a customer needs to know before leaving a bicycle with us."},{"n":2,"document":"README.txt","heading":null,"position":0,"excerpt":"Sample corpus of Cited These documents describe a fictional small business, Café La Horquilla, a café and bicycle workshop. They exist so the tests, the manual verification and the RAM measurement of this repository have something real to ingest. They were written for this repository. They are not the book of Construye, not golden cases, not holdout data, not a customer document and not prices of a real business.\n- cafe-la-horquilla.md: hours, prices and policies, in Spanish.\n- bike-workshop-policies.md: bookings, storage, groups and guarantee, in English.\n- notas-del-negocio.txt: payment, invoicing, pets, accessibility, in Spanish."},{"n":3,"document":"bike-workshop-policies.md","heading":"Guarantee","position":4,"excerpt":"Guarantee Every repair carries a 90 day guarantee on the work. Parts carry the guarantee of their maker. Bring the ticket; without it we can still look up the repair by the frame number."}]}}}
```

Key numbers: **3 passages**; the 90-day guarantee text is passage **3**, `bike-workshop-policies.md · Guarantee,
position 4`.

> `cited_search` was verified to be independent of any provider: the same request was replayed on a server started with
> **no** `CHAT_PROVIDER` and **no** `EMBEDDINGS_PROVIDER`, and returned the identical 3-passage body.

---

## 3. JSON-RPC protocol over `/api/mcp`

Common request shape (all calls): `POST http://127.0.0.1:3247/api/mcp`, headers
`Authorization: Bearer <token>`, `Content-Type: application/json`, `Accept: application/json, text/event-stream`.
The bodies were supplied with `curl.exe --data-binary @<file>` because PowerShell 5.1 word-splits inline JSON that
contains spaces (see "Gotchas").

### 3.1 `initialize` (id 2)

Headers included `MCP-Protocol-Version: 2025-06-18`. Body:

```json
{"jsonrpc":"2.0","id":2,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"runbook","version":"1.0.0"}}}
```

Observed `HTTP/1.1 200 OK`, `content-type: application/json; charset=utf-8`, `cache-control: no-store`,
`transfer-encoding: chunked`. Body (exact):

```json
{"jsonrpc":"2.0","id":2,"result":{"protocolVersion":"2025-06-18","capabilities":{"tools":{}},"serverInfo":{"name":"cited","version":"0.1.0"},"instructions":"Cited answers only from the documents of this installation, and it always says where an answer came from. Call cited_search to read the passages that match a query and cite them by their number, like [1]. Call cited_ask for a written answer with its citations. When the documents do not hold the answer, Cited refuses instead of inventing it: pass that refusal to the user."}}
```

### 3.2 `notifications/initialized` (no id)

Body: `{"jsonrpc":"2.0","method":"notifications/initialized"}`

Observed `HTTP/1.1 202 Accepted`, `cache-control: no-store`, **empty body** (0 characters). This is the notification
path (`app/api/mcp/route.ts:85-87`, `lib/mcp/server.ts:131-134`).

### 3.3 `ping` (id 3)

Observed `HTTP/1.1 200 OK`: `{"jsonrpc":"2.0","id":3,"result":{}}`

### 3.4 `tools/list` (id 7)

Observed `HTTP/1.1 200 OK`, body (exact, one line):

```json
{"jsonrpc":"2.0","id":7,"result":{"tools":[{"name":"cited_search","title":"Search the documents of Cited","description":"Read the passages of the business documents that match a query, with the document, the section, the position and the text of each one. Cite them by their number. This tool never writes an answer and never calls a language model, so it costs nothing.","inputSchema":{"type":"object","properties":{"query":{"type":"string","description":"The words to look for in the documents of the business."},"limit":{"type":"integer","minimum":1,"maximum":8,"default":5,"description":"How many passages to return, between 1 and 8. Five by default."}},"required":["query"],"additionalProperties":false},"outputSchema":{"type":"object","properties":{"passages":{"type":"array","description":"The passages of the documents that match the query, best first.","items":{"type":"object","properties":{"n":{"type":"integer","description":"The number the answer cites, like [1]."},"document":{"type":"string","description":"The name of the document the passage came from."},"heading":{"type":["string","null"],"description":"The section of the document, when it has one."},"position":{"type":"integer","description":"The position of the passage inside its document."},"excerpt":{"type":"string","description":"The text of the passage, so the answer can be checked."}},"required":["n","document","heading","position","excerpt"],"additionalProperties":false}}},"required":["passages"],"additionalProperties":false},"annotations":{"readOnlyHint":true,"openWorldHint":false}},{"name":"cited_ask","title":"Ask the documents of Cited","description":"Answer a question from the documents of the business, with numbered citations and the passage each one came from. When the documents do not hold the answer, the result says refused instead of inventing it.","inputSchema":{"type":"object","properties":{"question":{"type":"string","description":"The question to answer from the documents of the business."},"sessionId":{"type":"string","description":"The same value across a conversation, so a follow-up keeps its thread."}},"required":["question"],"additionalProperties":false},"outputSchema":{"type":"object","properties":{"status":{"type":"string","enum":["answered","refused"]},"answer":{"type":"string","description":"The answer, or the sentence of the refusal."},"citations":{"type":"array","items":{"type":"object","properties":{"n":{"type":"integer","description":"The number the answer cites, like [1]."},"document":{"type":"string","description":"The name of the document the passage came from."},"heading":{"type":["string","null"],"description":"The section of the document, when it has one."},"position":{"type":"integer","description":"The position of the passage inside its document."},"excerpt":{"type":"string","description":"The text of the passage, so the answer can be checked."},"lead":{"type":"integer","description":"How many characters of the excerpt repeat the passage before it."}},"required":["n","document","heading","position","excerpt","lead"],"additionalProperties":false}}},"required":["status","answer","citations"],"additionalProperties":false},"annotations":{"readOnlyHint":true,"openWorldHint":false}}]}}
```

Exactly two tools, both with `readOnlyHint:true` and `openWorldHint:false`.

### 3.5 Full `tools/call` response for `cited_search`

Request (id 8, query `Café La Horquilla afinación de bicicleta precio`) and full body: see §2.1. The
`structuredContent.passages` array carries `n`, `document`, `heading`, `position` and `excerpt`; the first excerpt is the
`Precios` block containing `Afinación de bicicleta: 380 pesos.`

### 3.6 Full `tools/call` response for `cited_ask` (with `CHAT_PROVIDER=fake`)

Request (id 10):

```json
{"jsonrpc":"2.0","id":10,"method":"tools/call","params":{"name":"cited_ask","arguments":{"question":"Café La Horquilla afinación de bicicleta precio"}}}
```

`HTTP/1.1 200 OK`. Body (exact):

```json
{"jsonrpc":"2.0","id":10,"result":{"content":[{"type":"text","text":"Respuesta del proveedor de prueba: - Café de olla: 45 pesos. [1]\n\nSources:\n1. cafe-la-horquilla.md · Precios (position 2)"}],"structuredContent":{"status":"answered","answer":"Respuesta del proveedor de prueba: - Café de olla: 45 pesos. [1]","citations":[{"n":1,"document":"cafe-la-horquilla.md","heading":"Precios","position":2,"excerpt":"Precios\n- Espresso: 35 pesos.\n- Café de olla: 45 pesos.\n- Pan dulce del día: 30 pesos.\n- Afinación de bicicleta: 380 pesos.\n- Cambio de cámara: 120 pesos.","lead":0}]}}}
```

A second `cited_ask` (id 11, question `bike workshop guarantee repairs`) returned
`"status":"answered"` with one citation to `README.txt, position 0`, excerpt
`"Sample corpus of Cited These documents describe a fictional small business, Café La Horquilla, a café and bicycle workshop. ..."`.
This is grounded (the excerpt exists in the corpus) but **topically wrong** — see §4.

### 3.7 Session-id behaviour and statelessness

- The endpoint is **stateless**. `initialize` returns no session identifier, and **no** `Mcp-Session-Id` response header
  was present on any call (`curl -D -` on `cited_search` printed only `vary`, `cache-control`, `content-type`, `Date`,
  `Connection`, `Keep-Alive`, `Transfer-Encoding`). This matches `docs/mcp.md:47-48` ("without sessions") and
  `lib/mcp/server.ts:3-5`.
- `sessionId` is **only** a `cited_ask` argument used to store a conversation turn; it is not a transport session.
  It was accepted without error: `cited_ask` with `"sessionId":"runbook-session-1"` returned `200` and
  `status:"answered"` with citation `cafe-la-horquilla.md · Horario (position 1)`, excerpt
  `"Horario\n- Martes a viernes: 8:00 a 19:00.\n- Sábado: 9:00 a 20:00.\n- Domingo: 9:00 a 14:00.\n- Lunes: cerrado por mantenimiento del taller."`
- Only in-process state exists: the per-token hourly counter (`lib/mcp/limits.ts:25`).

### 3.8 `MCP-Protocol-Version` header

- `tools/list` with `MCP-Protocol-Version: 2024-11-05` → `HTTP/1.1 400 Bad Request`, body
  `{"jsonrpc":"2.0","id":null,"error":{"code":-32600,"message":"the protocol version 2024-11-05 is not supported"}}`
  (`app/api/mcp/route.ts:77-81`).
- `initialize` with `MCP-Protocol-Version: 1999-01-01` → `HTTP/1.1 200 OK`, `protocolVersion:"2025-06-18"`: the header
  is intentionally ignored for `initialize` and the version is negotiated from the body (`route.ts:75-79`,
  `isInitialize` at `:56-58`). This is the subject of the prebuilt fix commit.
- `Accept: application/json` alone (without `text/event-stream`) still answers `200`; the server does not enforce a
  combined `Accept`. `docs/mcp.md:50-51` promises a single JSON object, never a stream.

---

## 4. `cited_ask` without an AI

Earlier evidence: `cited_ask` answered `{"error": "the AI is not connected yet: ..."}`. What was measured:

**Without `CHAT_PROVIDER`** (only `DATABASE_URL`, `CITED_MCP_TOKEN`): the request still returns
`HTTP/1.1 200 OK`, but the JSON-RPC **result** is a tool error (not a JSON-RPC `error`):

```json
{"jsonrpc":"2.0","id":11,"result":{"content":[{"type":"text","text":"the AI is not connected yet: the owner connects it in the panel, or whoever installs Cited sets it on the server"}],"isError":true}}
```

Path: `lib/mcp/tools.ts:340-346` (`resolveChat`), `lib/settings/providers.ts:170-172` and `:353-355`
(`chatProblem` → "the AI is not connected yet"), `lib/mcp/tools.ts:33-34` (`NOT_CONNECTED` constant).

**With `CHAT_PROVIDER=fake`** — the exact env change that makes `cited_ask` work offline:

```powershell
$env:CHAT_PROVIDER = 'fake'    # no key, no base URL, no model needed
```

`cited_ask` then returns a **real grounded answer with citations and excerpts**, `status:"answered"`, e.g. the §3.6
response. No `CHAT_MODEL`, `EMBEDDINGS_PROVIDER` or API key is needed.

How the fake provider works (read from source):

- `lib/models/providers.ts:60-62` — `chatModelFrom` returns `createFakeChatModel()` when `provider === "fake"`.
- `lib/models/fake.ts:5` — tokens shorter than 4 characters are ignored.
- `lib/models/fake.ts:81-108` — `answerFrom()` parses the `<passage n="…" document="…" heading="…">…</passage>` blocks
  that `lib/answer/prompt.ts:66-76` builds, scores each passage by how many question tokens it contains, takes the
  first sentence of the best passage that shares a token with the question, and returns
  `${notes[language]} ${sentence.slice(0, 300)} [best.n]` (prefix at `lib/models/fake.ts:11-14`).
- `lib/models/fake.ts:97-99` — if no passage shares a token it returns the literal string `"NO_ANSWER"`.
- `lib/answer/ask.ts:88-90` — zero search hits → refusal; `:121-123` — model text exactly `NO_ANSWER` → refusal;
  `:125-129` — no parsed citation → refusal. `lib/answer/language.ts:3-6` holds the refusal sentences.

**Caveat that matters for a gate:** `fake` is deterministic but **lexical**. It enforces a refusal only when the
question shares no ≥4-character token with any retrieved passage. A question that shares a surface word with the corpus
(e.g. `Café La Horquilla … jabón de lavanda`) is answered with a real passage sentence that does **not** answer the
question — `status:"answered"`, real excerpt, wrong topic (measured, §6). So `CHAT_PROVIDER=fake` is sufficient to prove
the citation plumbing offline, but it is **not** a factual-answering oracle.

Refusal path measured with the fake provider and a question outside the corpus:
`{"question":"¿Tienen jabón de lavanda?"}` → `HTTP/1.1 200 OK`,

```json
{"jsonrpc":"2.0","id":14,"result":{"content":[{"type":"text","text":"No encuentro eso en los documentos de este negocio."}],"structuredContent":{"status":"refused","answer":"No encuentro eso en los documentos de este negocio.","citations":[]}}}
```

Minimal offline alternative if `fake` is unacceptable: keep `cited_ask` unexercised and assert on `cited_search` only
(no provider at all), or run a real local model via `ollama`/`lmstudio` (needs `ALLOW_LOCAL_PROVIDERS=1` and a running
server). `fake` is the only zero-dependency offline option.

---

## 5. Error shapes (status code + exact body)

All bodies below were observed literally. Source lines:

| Case | Status | Body | Source |
|---|---|---|---|
| `POST`, no `Authorization` | `401` | `unauthorized\n` + header `www-authenticate: Bearer` | `app/api/mcp/route.ts:49-51` |
| `POST`, wrong token (`Bearer wrong-token`) | `401` | `unauthorized\n` + `www-authenticate: Bearer` | same |
| `POST`, empty token (`Authorization: Bearer `) | `401` | `unauthorized\n` + `www-authenticate: Bearer` | same |
| `POST`, foreign `Origin: https://evil.example` | `403` | `forbidden\n` | `route.ts:45-47` |
| `POST`, own `Origin: http://127.0.0.1:3247` | `200` | normal body | `lib/mcp/auth.ts:21-39` |
| Route off (no `CITED_MCP_TOKEN`), POST with or without bearer | `404` | **empty** (no body, only `cache-control: no-store`) | `route.ts:32-34,41-43` |
| Route off, `GET` / `DELETE` | `404` | empty | same |
| Malformed JSON body (`{"jsonrpc":"2.0","id":20,"method":`) | `400` | `{"jsonrpc":"2.0","id":null,"error":{"code":-32700,"message":"the body is not valid JSON"}}` | `route.ts:69-73`, `lib/mcp/protocol.ts:47` |
| `MCP-Protocol-Version: 2024-11-05` on `tools/list` | `400` | `{"jsonrpc":"2.0","id":null,"error":{"code":-32600,"message":"the protocol version 2024-11-05 is not supported"}}` | `route.ts:77-81` |
| Unknown JSON-RPC method `resources/list` | `200` | `{"jsonrpc":"2.0","id":4,"error":{"code":-32601,"message":"the method resources/list is not implemented"}}` | `lib/mcp/server.ts:145-146` |
| Body missing `jsonrpc` (`{"id":21,"method":"tools/list"}`) | `200` | `{"jsonrpc":"2.0","id":21,"error":{"code":-32600,"message":"the message is not a JSON-RPC request"}}` | `lib/mcp/server.ts:127-129` |
| `tools/call` unknown tool (`"nope"`) | `200` | `{"jsonrpc":"2.0","id":22,"error":{"code":-32602,"message":"Unknown tool: nope"}}` | `lib/mcp/server.ts:90-92` |
| `initialize` without params | `200` | `{"jsonrpc":"2.0","id":23,"error":{"code":-32602,"message":"initialize needs a protocolVersion string"}}` | `lib/mcp/server.ts:61-63` |
| `tools/call` without params | `200` | `{"jsonrpc":"2.0","id":24,"error":{"code":-32602,"message":"tools/call needs the name of a tool and its arguments"}}` | `lib/mcp/server.ts:78-82` |
| `GET` (token configured, valid bearer) | `405` | `method not allowed\n` + header `allow: POST` | `route.ts:92-96` |
| `DELETE` (token configured, valid bearer) | `405` | `method not allowed\n` + `allow: POST` | `route.ts:98-101` |

Notes:
- The 401/403/405 bodies are `text/plain; charset=utf-8`; the JSON-RPC ones are `application/json; charset=utf-8`.
- The order of the guards is **off → origin → bearer** (`route.ts:38-54`): with no token the route answers `404` even
  for a foreign origin, and it never reads the body before the guards.
- Error text is sanitised through `publicMessage()` and falls back to a fixed sentence
  (`lib/mcp/protocol.ts:44-51,67-73`), so no environment-variable name or provider text leaks.
- The token never appears in any response body (verified by inspection of every body above).

---

## 6. A question the four sample documents do not answer

**Query used** (`cited_search`, id 12):

```json
{"jsonrpc":"2.0","id":12,"method":"tools/call","params":{"name":"cited_search","arguments":{"query":"Café La Horquilla precio del jabón de lavanda artesanal"}}}
```

Observed `HTTP/1.1 200 OK`, `structuredContent.passages` (5 passages, summaries):

| n | document | heading | position | excerpt (start) |
|---|---|---|---|---|
| 1 | `cafe-la-horquilla.md` | `Café La Horquilla` | 0 | `Café La Horquilla Somos un café y taller de bicicletas en el centro de la ciudad. Abrimos de martes a domingo.` |
| 2 | `notas-del-negocio.txt` | `null` | 0 | `Café La Horquilla — notas del negocio Dirección: avenida central, frente al parque. …` |
| 3 | `bike-workshop-policies.md` | `Bike workshop policies at Café La Horquilla` | 0 | `Bike workshop policies at Café La Horquilla Everything a customer needs to know before leaving a bicycle with us.` |
| 4 | `README.txt` | `null` | 0 | `Sample corpus of Cited These documents describe a fictional small business, Café La Horquilla, …` |
| 5 | `cafe-la-horquilla.md` | `Precios` | 2 | `Precios\n- Espresso: 35 pesos.\n- Café de olla: 45 pesos.\n- Pan dulce del día: 30 pesos.\n- Afinación de bicicleta: 380 pesos.\n- Cambio de cámara: 120 pesos.` |

**The samples leave it unanswered.** The retrieval is lexical/keyword, so it returns the top-5 passages that match the
words `Café`, `Horquilla` and `precio`; **none** of the five mentions lavender soap, a soap price, or any soap product.
A literal content check confirms it:

```
grep -i "lavanda|lavender|jabón|soap" samples/   →  No matches found
```

Reference content of the corpus: `samples/cafe-la-horquilla.md:12-18` (Precios: espresso, café de olla, pan dulce,
afinación, cambio de cámara), `samples/bike-workshop-policies.md:5-24` (bookings, storage, groups, guarantee),
`samples/notas-del-negocio.txt:1-17` (address, payment, invoicing, pets, accessibility, contact),
`samples/README.txt:1-13` (corpus description). No lavender/soap item exists anywhere.

**Important gate warning (measured).** `cited_ask` on the *same* question with `CHAT_PROVIDER=fake` returned
`status:"answered"` (not `refused`):

```json
{"jsonrpc":"2.0","id":13,"result":{"content":[{"type":"text","text":"Respuesta del proveedor de prueba: Café La Horquilla Somos un café y taller de bicicletas en el centro de la ciudad. [1]\n\nSources:\n1. cafe-la-horquilla.md · Café La Horquilla (position 0)"}],"structuredContent":{"status":"answered","answer":"Respuesta del proveedor de prueba: Café La Horquilla Somos un café y taller de bicicletas en el centro de la ciudad. [1]","citations":[{"n":1,"document":"cafe-la-horquilla.md","heading":"Café La Horquilla","position":0,"excerpt":"Café La Horquilla Somos un café y taller de bicicletas en el centro de la ciudad. Abrimos de martes a domingo.","lead":0}]}}}
```

The citation excerpt is real, but the answer does not answer the question. The clean refusal was only obtained when the
question shared no token with the corpus at all (`¿Tienen jabón de lavanda?` → `status:"refused"`, §4). Therefore a gate
must assert the absence of an answer on the **`cited_search` passage content**, not on `cited_ask.status`.

---

## 7. Cleanup

Exact teardown command:

```powershell
$probe = Join-Path $env:TEMP 'cited-mcp-probe'
$pid0  = Get-Content (Join-Path $probe 'server.pid')
taskkill /PID $pid0 /T /F
Start-Sleep -Milliseconds 1200
Remove-Item -LiteralPath $probe -Recurse -Force
```

Observed:

```
CORRECTO: el proceso con PID 22080 (proceso secundario de PID 32932) ha sido terminado.
CORRECTO: el proceso con PID 32932 (proceso secundario de PID 52032) ha sido terminado.
```

Post-checks:

| Check | Observed |
|---|---|
| curl `http://127.0.0.1:3247/api/mcp` after kill | `CURL_EXIT=7` ("Failed to connect … Could not connect to server") |
| `netstat -ano \| findstr :3247` | only client `TIME_WAIT` rows owned by PID 0; **no LISTENING socket** |
| node processes whose command line contains `3247` | none (only the query shell matched its own text) |
| temp dir `%TEMP%\cited-mcp-probe` | `Test-Path` → `False` (removed, with the SQLite file and logs) |
| second temp dir `%TEMP%\cited-mcp-startform` | `Test-Path` → `False` |
| `git status --porcelain` in `community-mcpfix` | empty (no product file touched) |
| `community-mcpfix\.data` | `Test-Path` → `False` (no store was ever created inside the repo) |

**Left behind:** only the shared npx download cache of Node 24 at
`C:\Users\Franc\AppData\Local\npm-cache\_npx\387698761821791d\` (created by `npx -y -p node@24`, reused by later runs;
not deleted on purpose because it is a shared cache). Nothing else. The probe **never touched** port 3240 or 3246, and
never touched `C:\Users\Franc\AppData\Local\hermes` or `~/.hermes`.

---

## Timings

All numbers are wall-clock on this machine, Node 24.21.0, warm filesystem cache, worktree already built.

| Phase | Command | Observed |
|---|---|---|
| `next build` | **not run** | The worktree already had a production `.next` (`BUILD_ID` mtime `2026-10-09 22:18:41`). A build was deliberately not executed to avoid rewriting `.next` while another agent was using the same worktree. No measured build time is available from this probe; `scripts/gate-mcp.mjs:507` runs the build and the caller should time `next build` separately. |
| Seed | `node scripts/mcp-seed.ts <store> samples` (Node 24) | **1093 ms**, 4 documents / 11 passages, exit 0 |
| Start (direct Node 24 binary), Next-internal | `node …/next start -H 127.0.0.1 -p 3247` | Next logs `Ready in 269ms` (cold: `Ready in 371ms`); `next.config.ts` 59–125 ms |
| Start → first HTTP 200, measured | `Start-Process` + curl poll | **1276 ms** (subsequent restarts: 973 / 1046 / 1072 ms) |
| Start via `npx -y -p node@24 node … next start` | npx wrapper | **5911 ms** to first HTTP answer (Next internal `Ready in 559ms`); budget ~6 s because of the npx wrapper |
| `cited_search` call | curl | < 50 ms after warm-up (5 passages) |
| `cited_ask` with `fake` | curl | < 50 ms (no network) |

Sizing suggestion for a gate: seed ≈ 1.1 s; start + readiness ≈ 1.3 s (add build time, unmeasured here); each protocol
call is milliseconds. The dominance is the build, not the runtime.

---

## Gotchas carried forward

1. **`pwsh` here is Windows PowerShell 5.1.** `Invoke-WebRequest -SkipHttpErrorCheck` throws
   `ParameterBindingException`, which a retry loop silently mistakes for "not ready". Use `curl.exe` with
   `-o NUL -w "%{http_code}"` for readiness.
2. **Inline JSON with spaces is word-split by PowerShell 5.1** when passed to `curl.exe -d`. Write the body to a temp
   file and use `--data-binary @file`; JSON `\uXXXX` escapes let the payload stay pure ASCII. (`-d '{"jsonrpc":…}'`
   without spaces happens to work, but is fragile.)
3. **Literal `npx -y -p node@24 node_modules/next/dist/bin/next …` fails**; put `node` before the script path.
4. **`TURSO_DATABASE_URL` overrides `DATABASE_URL`** (`lib/store/path.ts:6-10`). Always set it (and `TURSO_AUTH_TOKEN`)
   to empty when a throwaway local store must win.
5. **Node on PATH is v24.11.0**, below the package `engines` (`>=24.15.0`). Use `npx -y -p node@24` (v24.21.0).
6. **`cited_ask` needs a chat provider; `cited_search` never does.** `CHAT_PROVIDER=fake` gives grounded citations with
   excerpts offline, but its lexical answerer can return a topically wrong "answered" whenever the question shares a
   token with the corpus — do not gate refusal behaviour on it.
7. **Changing `CHAT_PROVIDER` requires a restart**: the route reads `process.env` per request, but the provider is
   resolved from the process environment each call, so set it before `Start-Process`.
