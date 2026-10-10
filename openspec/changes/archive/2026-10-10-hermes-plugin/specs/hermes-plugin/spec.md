## ADDED Requirements

### Requirement: H0 — Facts verified in the Hermes source

The repository SHALL record, in `reports/hermes-facts.md`, every Hermes fact the plugin depends on with the file and line where it was read: the plugin hook names and the payload each one receives; whether a hook can replace the final answer before it leaves; whether plugin slash commands run on the CLI and on the gateway; how a plugin is installed from a local path; and whether `requires_toolsets` is satisfied by a plugin toolset.

#### Scenario: a hook can replace the final answer
- **WHEN** the hook list and the `transform_llm_output` call site are read
- **THEN** the report SHALL name `agent/turn_finalizer.py` and the lines where a returned string replaces the text
- **AND** it SHALL state that H4 is implementable rather than blocked

### Requirement: H1 — The MCP route works with no installation

The repository SHALL document and verify the MCP-configuration route in a temporary `HERMES_HOME`: the `mcp_servers.cited` fragment of `config.yaml`, the equivalent `hermes mcp add` command, a green `hermes mcp test cited`, and one natural question that makes the model call `mcp__cited__cited_search` or `mcp__cited__cited_ask` and answer with the citation.

#### Scenario: the configured server answers
- **WHEN** `hermes mcp test cited` runs against a live Cited in a temporary `HERMES_HOME`
- **THEN** it SHALL report success and list both Cited tools

#### Scenario: a natural question is answered from Cited
- **WHEN** the model is asked a question the sample documents answer
- **THEN** the stream SHALL contain a `tool_use` of a Cited tool and the final text SHALL carry the cited value

### Requirement: H2 — One-step native plugin

The plugin SHALL register `cited_search` and `cited_ask` as native tools with the same parameters as the Cited MCP tools, calling the endpoint with `Authorization: Bearer <CITED_MCP_TOKEN>`. The timeout SHALL be configurable and 30 seconds by default. Without configuration each tool SHALL answer an error that names the missing setting and SHALL NOT raise into Hermes.

#### Scenario: configuration is missing
- **WHEN** `cited_search` is called with no `CITED_URL`
- **THEN** the tool SHALL return a sentence naming `CITED_URL` and SHALL NOT raise

#### Scenario: both tools answer with passages
- **WHEN** `cited_search` and `cited_ask` are called against a live Cited
- **THEN** each SHALL return the passages or citations with their excerpts exactly as Cited sent them

### Requirement: H3 — The cited skill ships inside the plugin

The plugin SHALL register a skill named `cited` from a `SKILL.md` packaged in the repository, describing when to use each tool, that the answer and its citations are transmitted without changing a datum, that a refusal of Cited is passed on, and that in cited mode the model never completes from its own knowledge.

#### Scenario: the skill is registered
- **WHEN** the plugin loads under the installed Hermes
- **THEN** the skill `cited` SHALL be registered through `ctx.register_skill` and its file SHALL exist

### Requirement: H4 — Two modes with a deterministic verifier

The plugin SHALL register `/cited` and `/dot`, changing the mode of the conversation, and SHALL read the initial mode from `CITED_DEFAULT_MODE`, defaulting to `dot`. In cited mode the plugin SHALL inject the strict rules through `pre_llm_call` and SHALL run a deterministic, non-AI verifier on the final text: every number, unit, price and code SHALL appear in an excerpt or passage Cited returned in that same turn. An answer that fails SHALL be replaced by a refusal naming what could not be verified. An answer that passes SHALL end with `Verified by Cited` and its sources. In dot mode the seal SHALL never appear.

#### Scenario: the mode command changes the mode
- **WHEN** `/cited` runs
- **THEN** the next turn SHALL be cited, and after `/dot` the next turn SHALL be dot again

#### Scenario: an ungrounded number is refused
- **WHEN** the final text of a cited-mode turn contains a number that no excerpt of that turn contains
- **THEN** the text SHALL be replaced by a refusal that names the unverified token

#### Scenario: a grounded answer is sealed
- **WHEN** every number, unit, price and code of the final text appears in an excerpt of the same turn
- **THEN** the text SHALL be kept and SHALL end with `Verified by Cited` and the sources

#### Scenario: dot mode is untouched
- **WHEN** the mode is dot
- **THEN** the final text SHALL be returned unchanged and SHALL NOT carry the seal

### Requirement: H5 — Auditable hash-chained log

The plugin SHALL append one entry per response to `$HERMES_HOME/cited/audit.jsonl` with: UTC timestamp, platform, session, user when available, mode, question, the tool calls with their arguments, the SHA-256 of every returned excerpt, the final response, the verifier result, and the `prev_hash` and `hash` of the chain. A verifier runnable as `python -m hermes_cited.verify_log <file>` SHALL detect an entry that was altered, removed or reordered. The token SHALL never appear in the file.

#### Scenario: the chain verifies
- **WHEN** `python -m hermes_cited.verify_log` runs on a log the plugin wrote
- **THEN** it SHALL report the number of entries and exit zero

#### Scenario: tampering is detected
- **WHEN** an entry is altered, removed or reordered
- **THEN** the verifier SHALL exit non-zero and SHALL name the first broken entry

### Requirement: H6 — The token never travels anywhere else

The plugin SHALL send the token only in the `Authorization` header of a request to the configured `CITED_URL`. It SHALL NOT write it to a log, a tool result, the audit file or the evidence. `401`, `403`, `404`, a timeout and a network failure SHALL each become a distinct sentence the model can read.

#### Scenario: a wrong token is a sentence
- **WHEN** Cited answers `401`
- **THEN** the tool SHALL return a sentence about the token and SHALL NOT include the token's value

### Requirement: H7 — Documentation

The repository SHALL document, in English (`README.md`) and Spanish (`README.es.md`), the one-step installation, the configuration, the two modes, the log, and what was actually tested with its date. In the Cited worktree the change SHALL add an "Hermes Agent" section to `docs/mcp.md` describing both routes, and SHALL add the Hermes Agent row to the "Works with your agent" table of `README.md` and `README.es.md`, stating only what was verified.

#### Scenario: the Cited README names Hermes
- **WHEN** the two READMEs are read after the change
- **THEN** each SHALL contain a Hermes Agent row whose text matches the evidence, and no graphic SHALL have changed

### Requirement: H8 — Tests and evidence

The repository SHALL prove the contract with: unit tests under pytest against a local fake HTTP server that imitates `/api/mcp`; verifier and hash-chain cases that must fail; a load of the plugin using the installed Hermes venv; and an end-to-end run in a temporary `HERMES_HOME` with the DeepSeek model and a local Cited seeded from `samples/`, covering the price question, the English guarantee question, an unanswered question that must be refused, and a cited-mode log entry whose chain verifies. Evidence SHALL live in `reports/` and SHALL NOT contain the token.

#### Scenario: the gate is green
- **WHEN** `python scripts/gate.py` runs with the Python of the Hermes venv
- **THEN** it SHALL affirm H0 through H8 and print `GATE: GREEN`
- **AND** on any failure it SHALL print `GATE: RED` naming the failed claim
