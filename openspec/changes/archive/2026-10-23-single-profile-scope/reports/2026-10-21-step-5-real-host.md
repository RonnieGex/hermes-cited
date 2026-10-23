# Step 5: the real host of v0.22.4, in a subprocess

Date: 2026-10-21, America/Mexico_City. Agent: Fable. Windows 11. Nothing here opened the personal installation of
Hermes (`%LOCALAPPDATA%\hermes`, pinned at `dce1e9b`, v0.21.6) or any socket.

## The source

```
git clone --quiet --depth 1 --branch v0.22.4 https://github.com/NousResearch/hermes-agent.git hermes-0.22.4
git rev-parse HEAD      -> 4d04303818b61bf3aa09278af48356315515965b
git describe --tags     -> v0.22.4
git log -1              -> 4d043038 2026-10-21 fix(ci): desktop Pre-build setup gets room to verify the archived inputs
```

Facts read in that checkout (file:line):

| Fact | Where |
|---|---|
| "Nothing is bound while single-profile, so its reads keep the process-env semantics they always had" | `tui_gateway/launch_profile_policy.py:171-183`, `launch_body` |
| `get_secret`: with no scope, multiplex INACTIVE reads `os.environ`; ACTIVE raises `UnscopedSecretError` | `agent/secret_scope.py:230-261` |
| `owner_secret_scope(home)`: `launch_secret_scope` for the process home, `build_profile_secret_scope` otherwise | `tui_gateway/launch_profile_policy.py:157-167` |
| `launch_secret_scope`: the launch environment without global names, `<home>/.env` over it; `.env` wins | `tui_gateway/launch_profile_policy.py:134-155` |
| The launch environment is the live `os.environ` while multiplexing is inactive | `tui_gateway/launch_profile_policy.py:117-122` |
| The isolated plugin host binds a profile scope only `if is_multiplex_active()` | `hermes_cli/plugin_host.py:97-100` |

In the local `dce1e9b` checkout `tui_gateway/launch_profile_policy.py` has `launch_secret_scope` (line 129) and no
`owner_secret_scope`; the plugin's import of the builder fails there and the refusal of 0.2.0 stays.

## The probe by hand

The host's own modules, imported from that checkout with an interpreter that has `ruamel.yaml` (a scratch venv,
Python 3.12.0, `pip install ruamel.yaml`), `HERMES_HOME` pointing at a temporary home whose `.env` holds
`CITED_URL=http://127.0.0.1:60123` and a synthetic `CITED_MCP_TOKEN`, `APPDATA` and `LOCALAPPDATA` temporary:

```
scope= None multiplex= False
keys = ['CITED_MCP_TOKEN', 'CITED_URL'] url = http://127.0.0.1:60123 token ok = True
host get_secret CITED_URL (no scope, single profile, env unset) = None
host get_secret with env = http://env.example | owner scope url = http://127.0.0.1:60123
multiplex active, no scope -> UnscopedSecretError
```

So, on the real host: no scope is bound and multiplexing is inactive by default; `owner_secret_scope(process home)`
reads `<home>/.env`; the host's unscoped `get_secret` reads the process environment; for a key present in both, the
builder answers the `.env` value while the unscoped read answers the environment (design D2 records it as a RISK);
and with `set_multiplex_active(True)` the unscoped read raises `UnscopedSecretError`.

## The test

`tests/test_single_profile_host.py` runs the plugin in a subprocess (`python -I -c <driver> <source> <repo>`) under the
real `agent.secret_scope`, `hermes_constants` and `tui_gateway.launch_profile_policy`, with a contradictory
`CITED_URL=http://127.0.0.1:1` in the process environment, and asserts: no scope and no multiplexing before the plugin
runs; the scope's source is `hermes`, its home is the process home, it has no getter, its URL is the `.env` one and
its token equals the synthetic one; full registers `cited_ask`, `cited_quote` and `cited_search`; after
`set_multiplex_active(True)` the scope is refused with the redacted sentence and nothing registers; the synthetic
token never appears on stderr.

```
HERMES_HOST_0_22_SOURCE=<scratch>/upstream/hermes-0.22.4
HERMES_HOST_0_22_PYTHON=<scratch>/host-venv/Scripts/python.exe
PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python.exe -m pytest -q tests/test_single_profile_scope.py tests/test_profile_scope.py tests/test_single_profile_host.py -p no:cacheprovider -rs -v
```

```
tests\test_single_profile_host.py::test_the_pinned_source_carries_the_single_profile_builder PASSED
tests\test_single_profile_host.py::test_the_plugin_registers_on_the_real_single_profile_host_and_refuses_under_multiplex PASSED
40 passed in 34.67s
exit=0
```

Without the two variables, as in CI:

```
SKIPPED [1] tests\test_single_profile_host.py:83: HERMES_HOST_0_22_SOURCE does not name a checkout of Hermes Agent v0.22.4
SKIPPED [1] tests\test_single_profile_host.py:94: HERMES_HOST_0_22_SOURCE does not name a checkout of Hermes Agent v0.22.4
2 skipped in 0.16s
```

## Issues of this step

- NOT DONE: an end-to-end `hermes plugins install` and a real turn on a 0.22.4 host. The only 0.22.4 host of Katalis
  is the server the brief asks not to use; the local patch (`hermes-cited-single-profile.diff`) was verified there by
  the session that wrote it, with the same branch of `active_scope()`.
- UNKNOWN: the external secret sources and the managed `.env` that `build_profile_secret_scope` folds in were empty in
  the probe home; their precedence is the host's and is not exercised here.
