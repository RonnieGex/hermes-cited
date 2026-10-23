# Design: single-profile-scope

## D1. The host contract, with its source

Every line below is of Hermes Agent v0.22.4, upstream commit `4d04303818b61bf3aa09278af48356315515965b`, tag
`v0.22.4` of `NousResearch/hermes-agent`, read in a shallow clone of that tag.

| Fact | Where |
|---|---|
| Nothing is bound while a process serves one profile; its reads keep the process-environment semantics | `tui_gateway/launch_profile_policy.py:171-183` (`launch_body`) |
| `get_secret` with no scope: multiplexing inactive reads `os.environ`; active raises `UnscopedSecretError` | `agent/secret_scope.py:230-261` |
| `is_multiplex_active()` is the process flag or the task context | `agent/secret_scope.py:76-78` |
| `current_secret_scope()` and `current_secret_scope_home()` answer `None` when no scope is installed | `agent/secret_scope.py:169-178` |
| `owner_secret_scope(home)`: the launch mapping for the process home, the profile's files for any other | `tui_gateway/launch_profile_policy.py:157-167` |
| `launch_secret_scope(home)`: the launch environment without the global names, with `<home>/.env` (and the external and managed sources) over it; `.env` wins for a key present in both | `tui_gateway/launch_profile_policy.py:134-155` |
| The launch environment is the live `os.environ` while multiplexing is inactive and the frozen snapshot after | `tui_gateway/launch_profile_policy.py:117-122` |
| `get_process_hermes_home()` follows `HERMES_HOME` live | `hermes_constants.py:237-246` |
| `get_routing_process_hermes_home()` is the pinned identity of the process, else the live home; a host that mirrors a served profile into `HERMES_HOME` pins its own home with `pin_process_hermes_home` | `hermes_constants.py:249-279` |
| `serves_routed_profile()`: true under multiplexing, when a bound scope is stamped with a foreign home, or when a `HERMES_HOME` override names a home other than the pinned identity | `agent/secret_scope.py:91-108` |
| A launch body armed before the multiplexing flip (`set_launch_body_scope`, private `_LAUNCH_BODY_SCOPE`) lets the host's unscoped `get_secret` answer from the frozen launch scope while `current_secret_scope()` stays `None` | `agent/secret_scope.py:118-124, 248-251`; `tui_gateway/launch_profile_policy.py:171-183` |
| The isolated plugin host binds a profile scope only `if is_multiplex_active()` | `hermes_cli/plugin_host.py:97-100` |

In v0.21.6 (`dce1e9b`, the pin of H0 to H22) `owner_secret_scope` does not exist; `launch_secret_scope` does.

## D2. The host's builder, not `os.environ`

D2 of `search-only-bridge` forbade a fallback to the process environment while the `agent` package is present, and
that rule stands: the plugin does not read `os.environ`. The launch profile comes from `owner_secret_scope`, the
builder the host binds for every launch-profile body (routed turns, cron fires, kanban ticks), called with the
process home. It is called on every `active_scope()`, so the URL, the token and the timeout are read fresh on every
handler call, as the installed-scope path already does; the builder reads `<home>/.env` each time.

The mapping is the one Hermes would bind; its precedence is the host's: for a key present in both `<home>/.env`
and the launch environment, `.env` wins (`launch_secret_scope`), while an unscoped `get_secret` of the same host
reads the environment. In a normal launch both agree, because the host loads `<home>/.env` into the environment at
start; they differ only when an operator injects an environment-only value that contradicts `.env`, and then the
plugin follows the mapping the host documents as the launch profile's own. This is recorded as a RISK of the
delivery, not hidden.

## D3. The gate is `values is None`

Only a missing scope consults the host. A non-mapping value, a blank home of an installed scope, a failing accessor
and a broken host dependency keep their refusals (B01, m01). An explicit scope bound through the test seam wins over
everything, as before.

## D4. Fail closed, in order

1. The five imports (`is_multiplex_active`, `serves_routed_profile`, `get_process_hermes_home`,
   `get_routing_process_hermes_home`, `owner_secret_scope`): any failure is the redacted sentence. This is the branch
   a 0.21 host takes, and the branch the existing stand-in hosts of the suite take, so every existing refusal test
   keeps its meaning.
2. The four reads of the host's state (`is_multiplex_active()`, `serves_routed_profile()`, the pinned identity and
   the live home) run inside one `try`: any exception of the host, whatever its type, is a fresh
   `CitedScopeError(SCOPE_SENTENCE) from None`. The plugin's own refusals are raised outside that `try`, so a host that
   raises the plugin's own error type with another text cannot pass its text through (the adversarial review found
   the earlier `except CitedScopeError: raise` did exactly that).
3. `is_multiplex_active()` true: the redacted sentence, before the builder is called. The host's unscoped read raises
   `UnscopedSecretError` there, with one exception: a launch body armed before the flip (`launch_body`,
   `_LAUNCH_BODY_SCOPE`) answers from the frozen launch scope. That state is private to the host (no public accessor),
   transitional (in v0.22.4 multiplexing is activated eagerly at boot, so the mid-body flip is the lazy backstop) and
   the plugin fails closed in it rather than read a private context variable; the real-host probe records both facts
   (the host answers, the plugin refuses). Recorded as a RISK of the delivery.
4. `serves_routed_profile()` true (a `HERMES_HOME` override that names another home, as the dashboard backend or the
   per-profile cron ticker set, while multiplexing is inactive): the redacted sentence, before the builder is called.
   In that state the host's own unscoped `get_secret` would read the launch profile's environment for a task of another
   profile; the plugin promises to refuse a call of another home, so it closes here instead of mirroring the host.
   This point was raised by the read-only notes of a sibling session on 2026-10-21 and adopted.
5. The pinned identity (`get_routing_process_hermes_home()`) and the live home (`get_process_hermes_home()`) must name
   the same home, canonically; otherwise the redacted sentence, before the builder is called. A host that mirrors a
   served profile into `HERMES_HOME` pins its own home, and then the live home is the served profile's while the task
   may be the launch profile's (or the reverse): `owner_secret_scope` would build the mirrored profile's mapping and
   `_check_registration` would accept a registration of that profile for a task of another. The builder is called with
   the pinned identity, which is the home the host itself compares in `_is_process_home`. The Blocker of the
   adversarial review.
6. A blank home: the redacted sentence, before the builder is called.
7. A builder that raises: the redacted sentence, with no part of the exception (it may carry a secret).
8. A builder that answers a non-mapping: the redacted sentence.

The builder runs on every read. `load_env_file` is cached by the host and the external secret sources are read
again each time, which is the cost of every launch-profile binding the host itself performs per turn; the plugin
adds no cache, so a rotation in `.env` is seen on the next call, as the installed-scope path promises.

The `ProfileScope` of the launch profile carries `getter=None`: the host's `get_secret` would read `os.environ` for a
miss in this state, and the plugin's rule is the documented default for an absent key. `source` is `hermes`, so the
registration is not `explicit` and the callbacks keep their profile check against the canonical process home.

## D5. Tests

- `tests/test_single_profile_scope.py` installs stand-ins of `agent.secret_scope` (with `is_multiplex_active` and
  `serves_routed_profile`), `hermes_constants` and `tui_gateway.launch_profile_policy` and proves: the installed
  scope path untouched (builder never called); the single-profile path (values are the builder's mapping, home is
  the process home, no getter, source `hermes`, the builder called with the process home, a contradictory
  `os.environ` never used, full registration calling the fake Cited with the launch profile's bearer, search
  registration calling the chassis fake, rotation read fresh from independent snapshots with the builder count
  growing on every handler call); the multiplexing refusal and the routed-task refusal in both modes (builder never
  called); the refusal of a live home that disagrees with the pinned identity, and the pinned identity as the scope's
  home when both agree in different spellings; and the refusals of a host without the builder, a blank home, a
  raising builder (redacted, the plugin's own error type with another text included, in the sentence and in the
  registration diagnostic) and a non-mapping answer.
- `tests/test_single_profile_host.py` is opt-in: with `HERMES_HOST_0_22_SOURCE` naming a checkout whose `git
  rev-parse HEAD` is `4d043038` (skipped with the reason when the revision cannot be read, failed when it is another
  commit) and `HERMES_HOST_0_22_PYTHON` an interpreter with `ruamel.yaml`, it runs the plugin in a subprocess (`-I -B`,
  the `__pycache__` inventory of the checkout compared before and after) under the real `agent.secret_scope`,
  `hermes_constants` and `tui_gateway.launch_profile_policy`, in a temporary `HERMES_HOME` whose `.env` holds a
  synthetic token and with a contradictory `CITED_URL` in the environment: no scope, multiplexing inactive, the pinned
  identity equal to the live home, full registers the three tools and the scope holds the `.env` values; inside a
  `launch_body()` with the multiplexing flip the host's unscoped read still answers while the plugin refuses; after the
  flip the scope is refused and nothing registers. Skipped elsewhere, CI included, with the reason.
- `tests/conftest.py` adds `tui_gateway` to the host namespaces it removes after a test.
- The docstring of `test_a_missing_host_scope_registers_nothing` now says what its stand-in is: a host without the
  builder, the shape of 0.21.

## D6. Documentation

`README.md` and `README.es.md`: a Requirements bullet for Hermes 0.22 with the pin, one sentence in the scope
paragraph of the mode switch, and a bullet in Host incompatibilities that states the contract and that the plugin
handles it. `docs/technical-manual.md` section 2: the paragraph and two rows of the failure table.
`openspec/config.yaml`: the context sentence about the missing scope.

## Decisions taken by the implementer

- The version of the manifest stays `0.2.0`: six tests and the manual pin it, the install is pinned by commit, and
  the brief asks for no release.
- The real-host probe runs in a subprocess instead of importing the host into the test process, so the global
  `set_multiplex_active(True)` of the probe can never leak into another test.
