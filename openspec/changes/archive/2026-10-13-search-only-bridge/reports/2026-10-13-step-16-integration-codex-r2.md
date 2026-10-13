# Independent HTTP and offline installation evidence

Date: 2026-10-13. Agent: Codex. Change: search-only-bridge.
This file contains the in-change integration evidence explicitly required by review instruction 1b.
The review and all new probe sources remain outside the repository in
`C:/Users/Franc/Documents/katalis-dev/tasks/`.

## HTTP through a real curl process

Executed command, from the repository root:

```text
.venv/Scripts/python.exe ../tasks/bridge2-codex-r2-run.py bridge2-codex-r2-curl .venv/Scripts/python.exe ../tasks/bridge2-codex-r2-curl.py
```

The new script starts `tests/fakes/chassis_surface.py --port 0 --record <temporary-log>` with a synthetic
bearer, an isolated HERMES_HOME and PYTHONDONTWRITEBYTECODE=1. Each request uses
`curl.exe --silent --show-error --max-time 10 --request POST <origin>/api/chassis/mcp
--header @<temporary-authorization-file> --data-binary @<request-file> --output <response-file>
--write-out %{http_code}`, with an additional 15-second subprocess timeout.
No personal service is contacted. The fake selected port **50574**; neither 3240 nor 3241 was used.

| New input | Expected and measured result |
| --- | --- |
| Valid JSON request padded with spaces to exactly 16384 bytes | HTTP 200, one search passage |
| The same request with one more padding byte | HTTP 413, body_too_large |
| Query with overlong UTF-8 bytes c0 af | HTTP 400, -32700, null id |
| String id containing 128 CJK code points | HTTP 200, exact id echoed |
| String id containing 129 CJK code points | HTTP 400, -32600, null id |
| Numeric id 9007199254740991 | HTTP 200, exact id echoed |
| Numeric id 9007199254740992 | HTTP 400, -32600, null id |
| Query combining an accent, NUL and CRLF, numeric id 0 | HTTP 200, valid search result |

All eight cases pass; supervisor exit 0 in **2.45 seconds**. Full argv, request byte lengths, request digests
and response bodies are in external `bridge2-codex-r2-curl-result.json` and `bridge2-codex-r2-curl.log`.
The request construction is retained in `bridge2-codex-r2-curl.py` for reproduction.

The owned server PID **13456** terminated. A fresh socket connection confirmed its port was closed.
The authorization file was deleted. The complete profile inventory before and after was identical:

```json
{"preserve.bin":"40aff2e9d2d8922e47afd4648e6967497158785fbd1da870e7110266bf944880"}
```

The log contains no bearer. The outer supervisor home also remained empty before and after.
This validates the delivered contractual fake; it does not claim a live Harness service was tested.

## Visible interface coverage

This change has no browser frontend, so there is no applicable Playwright page. The visible interface is the
Hermes CLI and native catalog/dispatch. Its real offline installation is measured separately below.

## Offline installation through the pinned CLI

Executed command:

```text
.venv/Scripts/python.exe ../tasks/bridge2-codex-r2-run.py bridge2-codex-r2-install-supervisor .venv/Scripts/python.exe ../tasks/bridge2-codex-r2-install.py
```

The independent supervisor creates a fresh mirror and canonical tar of product commit
`b747a57f0d54c9c8f44acea31fee30937d1fc6e4`, then reuses the provisioned runner inputs, not an earlier result.
The canonical archive uses Git binary `--output`, no prefix/compression, and isolated Git configuration:

```json
{"sha":"b747a57f0d54c9c8f44acea31fee30937d1fc6e4","sha256":"c121ad5608b41dcbcb9bcec82b8dc37febe9ebc1e716b614d2493ed9595d3d09","size":2109440}
```

Container `bridge2-codex-r2-install` uses image
`sha256:4d1caded1f729ae443eb803f26ffde7b61e696aeaef62f099abb6dd6b14257c7`, `--network none`,
`--user 0:0 --cpus 2 --memory 4g --pids-limit 300`, disposable tmpfs roots, and read-only mounts for the
host venv, host archive, provisioner, managed archives, uv cache, wheelhouse, bridge mirror and repository.
No ports are published. The runner verifies `external_connect_refused=true` and `mirror_writable=false`.

The required managed archives are checked against the pinned host's lock before use:

| Runtime | Version | Archive SHA-256 |
| --- | --- | --- |
| CPython | 3.14.7+20260901 | 0ab3305457051cd3e7c031857e005f1bda17c218a1990567dacaaac6dd1d14f0 |
| uv | 0.12.3 | 600cf9a742aca00d292673b16b5acffaa7b8c269a364ad0c2e79498dcb1fe101 |

`HERMES_RUNTIME_DIR=/opt/runtime`; archives occupy `/opt/runtime/fetch-<sha256>/`.
The prepared wheelhouse contains setuptools 83.0.0, wheel 0.48.0 and packaging 26.0. A loopback-only PEP 503
index serves these local wheels through UV_INDEX_URL; external networking stays disabled.
Full wheel digests and environment settings are retained in external `bridge2-codex-r2-install.log`.

Host checkout verified: `dce1e9b37581dd62e480a9064dc04a709c2940d3`, without tracked modifications.
The actual CLI command is:

```text
/opt/chassis/.venv/bin/hermes --profile bridge-probe plugins install file:///release/hermes-cited.git --ref b747a57f0d54c9c8f44acea31fee30937d1fc6e4 --enable --yes-deps
```

The selected E2E runs with all four prerequisite HERMES_TEST variables, PYTHONDONTWRITEBYTECODE=1 and
temporary homes:

```text
/opt/chassis/.venv/bin/python -m pytest -vv -s --showlocals -p no:cacheprovider tests/test_profile_install.py -k a_fresh_real_profile_installs
1 passed, 29 deselected in 334.44s (0:05:34)
supervisor: exit 0, 391.74 seconds; container_removed=true
```

The installed plugin has `enabled=true`, version 0.2.0, one tool, zero hooks and zero commands. All three
full-mode hook counts are zero. Dispatch through the scoped native registry returns:

```json
{"cited_tool":"cited_search","query":"hours","text":"[1] sample.md\nHours\nOpen Monday to Friday.","passages":[{"n":1,"document":"sample.md","heading":"Hours","position":0,"excerpt":"Open Monday to Friday.","lines":[{"line":1,"text":"Open Monday to Friday."}]}]}
```

The complete post-setup baseline contains **271 files**. The second catalog/dispatch run leaves every
relative path, size and SHA-256 identical (`assert after == baseline` passed), and cited/ is absent.
The inventory's compact sorted JSON has SHA-256
`209240007ed910a48302940282930fcfd573ad8855f2aec29e389f3f2fee24d8`.
The full inventory is retained in external `bridge2-codex-r2-install.log`; its extracted facts are in
`bridge2-codex-r2-install-summary.json`. No plugin-created file is excluded. The fake stops in the E2E's
finally block; removal of the container terminates its entire network namespace and local wheel index.

This refreshes 5.1/5.3 and the D4/D5/D9 evidence behind 11.4/13.4. It establishes the search installation
path, not full-mode turn compatibility. The independent full-mode dispatcher counterexample remains open.
The pin above is a review artifact, not an archived merge/release lock.
