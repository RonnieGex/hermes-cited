# hermes-plugin

Additions for the `search` mode of the plugin, the bridge of Cited Harness. Requirements H0 to H11 describe the
`full` mode and are unchanged.

## ADDED Requirements

### Requirement: H12 — The mode is a closed environment variable

The plugin SHALL read `CITED_BRIDGE_TOOLS` at registration with the closed values `full` and `search`, SHALL default
to `full` when the variable is absent or empty, and SHALL refuse to register with a sentence that names the variable
and the two values when it carries any other value.

#### Scenario: Absent means full

- **WHEN** the plugin registers with `CITED_BRIDGE_TOOLS` absent
- **THEN** it registers the three tools, the two commands, the hooks and the skill of the `full` mode

#### Scenario: An unknown value refuses registration

- **WHEN** the plugin registers with `CITED_BRIDGE_TOOLS=all`
- **THEN** it registers nothing and the registration error names `CITED_BRIDGE_TOOLS`, `full` and `search`

### Requirement: H13 — In search mode the plugin is one tool and nothing else

In `search` mode the plugin SHALL register exactly the tool `cited_search` with its current schema and description,
and SHALL register no other tool, no command, no hook and no skill, and SHALL write no audit record.

#### Scenario: Exactly one tool

- **WHEN** the plugin registers with `CITED_BRIDGE_TOOLS=search` against a recording context
- **THEN** the context recorded one `register_tool` call with the name `cited_search`, zero `register_command`, zero
  `register_hook` and zero `register_skill` calls

#### Scenario: No audit record in search mode

- **WHEN** `cited_search` runs in `search` mode against the fake surface
- **THEN** `$HERMES_HOME/cited/audit.jsonl` does not exist after the call

### Requirement: H14 — The search surface and its own token

In `search` mode `cited_search` SHALL call `POST <CITED_URL>/api/chassis/mcp` with the JSON-RPC `tools/call` request
`{ "name": "cited_search", "arguments": { "query", "limit"? } }` and `Authorization: Bearer <CITED_SEARCH_TOKEN>`,
SHALL return the same envelope as the `full` mode's `cited_search`, SHALL require `CITED_URL` and
`CITED_SEARCH_TOKEN` and name the missing one in its sentence, SHALL never read `CITED_MCP_TOKEN` in this mode, and
SHALL send the token to no other path and no other host, with the redirect refusal of H6.

#### Scenario: The request shape and the token

- **WHEN** `cited_search` is called with `{ "query": "horario", "limit": 3 }` in `search` mode against a fake surface
  on loopback
- **THEN** the fake surface received one `POST /api/chassis/mcp` with `Authorization: Bearer <CITED_SEARCH_TOKEN>` and
  a JSON-RPC body whose `params.name` is `cited_search` and `params.arguments` is `{ "query": "horario", "limit": 3 }`,
  and the tool returned the passages of the fake's answer in the envelope of the `full` mode

#### Scenario: The MCP token is never read

- **WHEN** `CITED_BRIDGE_TOOLS=search`, `CITED_SEARCH_TOKEN` is set and `CITED_MCP_TOKEN` carries a sentinel value
- **THEN** no request carries the sentinel and the sentinel appears in no log line

#### Scenario: A missing search token is named

- **WHEN** `CITED_BRIDGE_TOOLS=search` and `CITED_SEARCH_TOKEN` is absent
- **THEN** `cited_search` returns a sentence that names `CITED_SEARCH_TOKEN` and sends no request

#### Scenario: A redirect is refused

- **WHEN** the fake surface answers `302` to another host
- **THEN** the tool returns the refusal sentence of H6 and the token was not sent to the other host

### Requirement: H15 — Documentation and the pinned install

`README.md` and `README.es.md` SHALL document the `search` mode, its two variables, the surface it calls, what it does
not register, and the install command pinned by commit that Cited Harness uses
(`hermes plugins install RonnieGex/hermes-cited@<commit> --enable`), and `openspec/config.yaml` SHALL name the mode.

#### Scenario: The two READMEs agree

- **WHEN** the readme test runs
- **THEN** both READMEs carry the `search` mode section with the same variables and the same install command, and
  the Spanish one is a full translation
