# hermes-plugin

H0 to H18 and H20 to H22 are unchanged. H19 is modified in one clause and one scenario; H23 is added.

## MODIFIED Requirements

### Requirement: H19 - Closed mode and profile-scoped configuration

The plugin SHALL select full for absent/empty CITED_BRIDGE_TOOLS and search for search, reject every other value
before registration, and read configuration from the active profile as design D2 specifies without cross-profile
fallback. When the host binds no scope because it serves a single profile, the active profile SHALL be the launch
profile as H23 specifies. Registration mode SHALL be immutable until registration is repeated.

#### Scenario: Defaults and unknown mode
- **WHEN** registration runs with absent, empty, full, search and all values in separate scoped mappings
- **THEN** the first three register full, search registers only search, and all registers nothing with a redacted error

#### Scenario: Concurrent scopes and missing scope
- **WHEN** profiles A/B register and call concurrently with different tokens, URLs and modes and a contradictory root environment
- **THEN** each uses only its own values, and a missing scope while multiplexing is active, a changed-home or a failing scope sends zero requests

#### Scenario: Identical execution identifiers in two profiles are two turns
- **WHEN** two full registrations with different homes open turns with the same session and turn identifiers through the real secret scope
- **THEN** each pre-hook SHALL return its own profile's rules, nothing SHALL raise, and dropping one turn SHALL leave the other intact

#### Scenario: A refused foreign callback leaves the owner's turn intact
- **WHEN** an owner opens a turn and a callback with the same identifiers runs under another profile's scope
- **THEN** the call SHALL be refused before any turn is read or dropped, and the owner's later lookup SHALL return its live turn

#### Scenario: Failure diagnostics keep the profile redaction
- **WHEN** a command or transformer callback fails with an exception that includes the profile's synthetic secret while the root environment holds a different synthetic secret
- **THEN** no returned message, log record or traceback SHALL contain the profile's secret, and the profile's identity and configuration SHALL remain valid for its next call

## ADDED Requirements

### Requirement: H23 - The single-profile contract of Hermes 0.22

The plugin SHALL read its configuration from the launch profile when the `agent` package of Hermes is present,
`current_secret_scope()` answers `None` and `is_multiplex_active()` answers false: the mapping
`owner_secret_scope(get_process_hermes_home())` of `tui_gateway.launch_profile_policy`, the builder Hermes v0.22.4
(upstream commit `4d043038`) binds for every launch-profile body, `<HERMES_HOME>/.env` over the launch environment
(`tui_gateway/launch_profile_policy.py`, `launch_body` and `owner_secret_scope`; `agent/secret_scope.py`,
`get_secret`). That scope SHALL carry the process
home as its profile home, no host getter and the source `hermes`, and the builder SHALL be called on every read so a
rotated value is sent on the next call. While `is_multiplex_active()` answers true the plugin SHALL refuse the
missing scope with the redacted sentence, as the host's `get_secret` raises `UnscopedSecretError` there, and SHALL
register nothing; it SHALL refuse it the same way while `serves_routed_profile()` answers true (a `HERMES_HOME`
override that names another home), because the launch profile is then not the profile of the task. A host without
that builder, a blank process home, a builder that raises or one that answers a non-mapping SHALL be refused with the
same redacted sentence, which SHALL carry no part of the host's exception. An installed scope SHALL be used as
before, without consulting the builder, and the plugin SHALL NOT read `os.environ` in any of these cases.

#### Scenario: An installed scope is used as before
- **WHEN** the host answers a mapping and a home from `current_secret_scope()` and `current_secret_scope_home()`
- **THEN** the scope is that mapping with that home and the host's `get_secret`, and `owner_secret_scope` is never called

#### Scenario: A single-profile host without a bound scope
- **WHEN** the host answers `None`, `is_multiplex_active()` is false and the process environment holds a contradictory `CITED_URL`
- **THEN** the scope's values are the mapping `owner_secret_scope` answered for the process home, its home is the process home, it has no getter and its source is `hermes`; full registers its three tools and search its one tool, and the first call of `cited_search` carries the bearer of that mapping to the endpoint of that mapping, never the environment's

#### Scenario: A rotated launch profile is read on the next call
- **WHEN** the mapping of the launch profile changes its token between two calls of a registered handler
- **THEN** the second call carries the new bearer, and the builder was called at least once per read

#### Scenario: A multiplexing host without a bound scope
- **WHEN** the host answers `None` and `is_multiplex_active()` is true, in full and in search
- **THEN** `active_scope()` raises the redacted sentence, `owner_secret_scope` is never called, and registration installs no tool, hook, command or skill

#### Scenario: A task routed to another profile without a bound scope
- **WHEN** the host answers `None`, `is_multiplex_active()` is false and `serves_routed_profile()` is true, in full and in search
- **THEN** `active_scope()` raises the redacted sentence, `owner_secret_scope` is never called, and registration installs nothing

#### Scenario: A host without the builder, a blank home or a failing builder
- **WHEN** `tui_gateway.launch_profile_policy` has no `owner_secret_scope`, or `get_process_hermes_home()` is blank, or the builder raises an exception that carries a synthetic secret, or it answers a list
- **THEN** `active_scope()` raises the redacted sentence, the sentence does not contain the secret, and registration installs nothing

#### Scenario: The real host of v0.22.4
- **WHEN** the plugin registers under the real `agent.secret_scope`, `hermes_constants` and `tui_gateway.launch_profile_policy` of commit `4d043038`, in a temporary `HERMES_HOME` whose `.env` holds `CITED_URL` and a synthetic `CITED_MCP_TOKEN`, with a contradictory `CITED_URL` in the process environment
- **THEN** no scope is bound and multiplexing is inactive before the plugin runs, the scope holds the `.env` values with the process home and no getter, full registers `cited_search`, `cited_ask` and `cited_quote`, and after `set_multiplex_active(True)` the scope is refused and nothing registers
