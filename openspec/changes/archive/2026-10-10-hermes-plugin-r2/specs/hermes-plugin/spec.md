## MODIFIED Requirements

### Requirement: H4 — Two modes with a deterministic verifier

The plugin SHALL register `/cited` and `/dot`, changing the mode of the conversation, and SHALL read the initial mode from `CITED_DEFAULT_MODE`, defaulting to `dot`. In cited mode the plugin SHALL inject the strict rules through `pre_llm_call` and SHALL run a deterministic, non-AI verifier on the final text. The verifier SHALL work over segments (sentence or line) and SHALL accept a segment that carries a datum (number, unit, currency, date or code) only when that segment appears verbatim, after Unicode (NFKC) and whitespace normalisation applied to both sides, inside an excerpt Cited returned in that same turn. Its evidence SHALL be only the non-empty `passages[].excerpt` and `citations[].excerpt` of the turn: never the query, the generated `cited_ask` answer, a heading, a position, a count or the transport text. With zero excerpts there is no seal. Free text outside `« »` (or `"` `“”`) SHALL NOT carry a datum. Citation marks `[n]` SHALL be validated separately against the citation map of the turn and SHALL NOT count as data. A `status: refused` of `cited_ask` SHALL be answered with an explicit refusal, never with a seal. An answer that fails SHALL be replaced by a refusal naming what could not be verified. An answer that passes SHALL end with `Verified by Cited` and its sources, unless the delivery policy of the surface withholds the seal. In dot mode the seal SHALL never appear.

#### Scenario: the mode command changes the mode
- **WHEN** `/cited` runs
- **THEN** the next turn SHALL be cited, and after `/dot` the next turn SHALL be dot again

#### Scenario: a reworded datum is refused
- **WHEN** the final text of a cited-mode turn states a datum in its own words instead of copying a segment of an excerpt
- **THEN** the text SHALL be replaced by a refusal that names the segment it could not verify

#### Scenario: a copied segment is sealed
- **WHEN** every datum-bearing segment of the final text appears verbatim inside an excerpt of the same turn, inside `« »`
- **THEN** the text SHALL be kept and SHALL end with `Verified by Cited` and the sources

#### Scenario: a query echo is not evidence
- **WHEN** a `cited_search` turn returns zero passages and its transport text reflects the query
- **THEN** no seal SHALL be emitted and the answer SHALL be refused

#### Scenario: the generated answer is not evidence
- **WHEN** a `cited_ask` turn generates an answer that no `citations[].excerpt` contains
- **THEN** that answer SHALL NOT ground itself and the turn SHALL be refused

#### Scenario: a citation mark is checked against the map
- **WHEN** the text carries `[3]` and the turn has no third passage or citation
- **THEN** the mark SHALL be reported as ungrounded

#### Scenario: dot mode is untouched
- **WHEN** the mode is dot
- **THEN** the final text SHALL be returned unchanged and SHALL NOT carry the seal

### Requirement: H5 — Auditable hash-chained log

The plugin SHALL append one entry per response to `$HERMES_HOME/cited/audit.jsonl` with: UTC timestamp, a monotonic `seq` starting at 1, the identity of the log, platform, session, turn identifier, user when available, mode, question, the tool calls with their arguments and with the SHA-256 and the text of every returned excerpt, the final response, the verifier result, and the `prev_hash` and `hash` of the chain. The append SHALL hold an exclusive inter-process lock over a lock file of the log while it reads and validates the tail, computes the hash, appends and flushes to disk, and it SHALL NOT restart from genesis when the tail is invalid: it SHALL fail instead. The schema SHALL be validated before hashing and again at verification. A verifier runnable as `python -m hermes_cited.verify_log <file>` SHALL detect an entry that was altered, removed or reordered, and SHALL require an HMAC-authenticated checkpoint of the count, the final hash and the log identity whose key lives outside `HERMES_HOME`, at `%APPDATA%\Katalis\hermes-cited\audit.key` by default. The token SHALL never appear in the file.

#### Scenario: the chain verifies
- **WHEN** `python -m hermes_cited.verify_log` runs on a log the plugin wrote
- **THEN** it SHALL report the number of entries and exit zero

#### Scenario: tampering is detected
- **WHEN** an entry is altered, removed or reordered
- **THEN** the verifier SHALL exit non-zero and SHALL name the first broken entry

#### Scenario: a cut suffix is detected
- **WHEN** the last entry or a suffix of entries is removed
- **THEN** the verifier SHALL exit non-zero because the log no longer matches its checkpoint

#### Scenario: a recomputed chain is detected
- **WHEN** the responses are rewritten and every hash is recomputed without the key
- **THEN** the checkpoint SHALL not authenticate the new final hash and the verifier SHALL exit non-zero

#### Scenario: a rolled-back checkpoint is detected
- **WHEN** the checkpoint is replaced by an older one while the log keeps its entries
- **THEN** the verifier SHALL exit non-zero because count and final hash disagree

#### Scenario: concurrent writers keep one chain
- **WHEN** several processes append to the same log at the same time
- **THEN** every entry SHALL have a unique `seq`, the count SHALL be exact and the chain SHALL verify

### Requirement: H6 — The token never travels anywhere else

The plugin SHALL send the token only in the `Authorization` header of a request to the configured `CITED_URL`, and it SHALL refuse to follow a redirect that would send it to another origin: a `3xx` SHALL become a redacted sentence and no second request SHALL be made. Before building any visible result, success or error, the client SHALL reject, with a redacted sentence, a response that reflects the token in any string. Before hashing and appending, every field of the audit entry, including the question, the arguments, the excerpts, the response and the errors, SHALL be redacted recursively. `401`, `403`, `404`, a timeout and a network failure SHALL each become a distinct sentence the model can read, and the gate's raw logs SHALL be redacted before they are written.

#### Scenario: a wrong token is a sentence
- **WHEN** Cited answers `401`
- **THEN** the tool SHALL return a sentence about the token and SHALL NOT include the token's value

#### Scenario: a redirect is refused
- **WHEN** the configured origin answers `301`, `302`, `303`, `307` or `308` to a location on another origin
- **THEN** the client SHALL raise a redacted sentence and SHALL make zero requests to that location

#### Scenario: a reflected token is rejected
- **WHEN** a successful Cited response carries the token in its content or structured content
- **THEN** the client SHALL reject the response with a redacted sentence instead of returning it

### Requirement: H7 — Documentation

The repository SHALL document, in English (`README.md`) and Spanish (`README.es.md`), the one-step installation, the configuration, the two modes, the delivery policy of cited mode per surface, the audit log with its checkpoint and the key outside `HERMES_HOME`, and what was actually tested with its date. It SHALL state the exact scope of the custody: a change made without the key is detected; remote custody arrives with Cited Ledger. It SHALL identify the plugin repository explicitly as `RonnieGex/hermes-cited`. In the Cited worktree the change SHALL add an "Hermes Agent" section to `docs/mcp.md` describing both routes, and SHALL add the Hermes Agent row to the "Works with your agent" table of `README.md` and `README.es.md`, stating only what was verified and linking durable evidence.

#### Scenario: the Cited README names Hermes
- **WHEN** the two READMEs are read after the change
- **THEN** each SHALL contain a Hermes Agent row whose text matches the evidence, and no graphic SHALL have changed

### Requirement: H8 — Tests and evidence

The repository SHALL prove the contract with: unit tests under pytest against a local fake HTTP server that imitates `/api/mcp`, including one adversarial test per finding B1 to B3 and M1 to M7; verifier and hash-chain cases that must fail; a load of the plugin using the installed Hermes venv; and an end-to-end run in a temporary `HERMES_HOME` with the DeepSeek model and a local Cited built from `origin/main` of the Cited repository in its own temporary worktree and served on port 3246, covering the price question, the English guarantee question, an unanswered question that must be refused, dot mode, and a cited-mode log whose chain and checkpoint verify from the installed plugin. Evidence SHALL live inside the change (`openspec/changes/hermes-plugin-r2/reports/`), SHALL be redacted before it is written, and SHALL NOT contain the token. `scripts/gate.py` SHALL affirm the named property of every claim, and SHALL reject a claim with an adversarial fixture rather than with a substring.

#### Scenario: the gate is green
- **WHEN** `python scripts/gate.py` runs with the Python of the Hermes venv
- **THEN** it SHALL affirm the properties and print `GATE: GREEN`
- **AND** on any failure it SHALL print `GATE: RED` naming the failed claim

## ADDED Requirements

### Requirement: H9 — The delivery policy of cited mode is explicit and enforced where it can be

The plugin SHALL read the effective streaming configuration of the run at load and per turn. On a messaging surface (Telegram, Slack, Discord and the like) whose effective streaming is on, cited mode SHALL withhold the seal in that platform and the answer SHALL say that a draft may have been visible and how to turn streaming off. The READMEs SHALL give the exact configuration for each surface: `streaming.enabled` and `display.platforms.<platform>.streaming` for the gateway, `display.streaming` for the CLI, the `--format stream-json` rule that only the terminal `result` record is shown, and the desktop limitation that a draft may be seen while the answer is written. `docs/upstream-proposal.md` SHALL specify, in English and with file and line, the per-turn delivery-policy hook Hermes would need to retain text, reasoning, intermediate comments and voice until a verdict, including the SSE route.

#### Scenario: a messaging surface with streaming on withholds the seal
- **WHEN** the effective streaming for the platform is on, the mode is cited and the answer is grounded
- **THEN** the final text SHALL NOT carry `Verified by Cited` and SHALL say that the seal was withheld because streaming is on

#### Scenario: a messaging surface with streaming off seals
- **WHEN** the effective streaming for the platform is off
- **THEN** a grounded cited-mode answer SHALL carry the seal

#### Scenario: the desktop limitation is documented
- **WHEN** a README is read
- **THEN** it SHALL say that the desktop app may show the draft while the answer is written, and it SHALL NOT promise that no draft is visible

### Requirement: H10 — A persistence failure never yields a sealed answer

The plugin SHALL keep the session and turn identifiers of a turn, write them in the audit entry, and treat the audit append as a step that can fail. In cited mode, a failure to persist SHALL produce an operational refusal without the seal and a redacted diagnostic, and the turn state SHALL be discarded only after the append result is known. A log with an invalid tail SHALL refuse the append instead of starting a new chain.

#### Scenario: the log cannot be written
- **WHEN** the audit append raises a permission or disk error
- **THEN** the cited-mode answer SHALL be a refusal that says it could not be recorded, SHALL NOT carry the seal and SHALL report the verifier as not applied

#### Scenario: the session is recorded
- **WHEN** the hooks carry a `session_id` and a `turn_id`
- **THEN** both SHALL appear in the audit entry

#### Scenario: an invalid tail refuses the append
- **WHEN** the last line of the log is not a valid entry
- **THEN** the append SHALL raise and the cited-mode answer SHALL be an operational refusal
