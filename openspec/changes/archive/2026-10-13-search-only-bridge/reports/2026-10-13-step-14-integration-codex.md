# Bridge2 round 1: independently executed HTTP and installation evidence

Date: 2026-10-13. Reviewer: Codex. Branch: feature/search-only-bridge.
This report is integration evidence required by review instruction 1b. The review and new probes remain
outside the repository in `C:/Users/Franc/Documents/katalis-dev/tasks/`.

## HTTP, eight new cases

Command from the repository, under the external supervisor's temporary HERMES_HOME:

```text
.venv/Scripts/python ../tasks/bridge2-codex-r1-run.py curl C:/Users/Franc/Documents/katalis-dev/hermes-cited/.venv/Scripts/python.exe ../tasks/bridge2-codex-r1-curl.py
```

The probe starts the delivered fake as a separate process with `--port 0 --record <temporary-log>` and
uses curl.exe for every call. Actual selected port: 64404, loopback only. Every curl invocation uses:

```text
curl.exe --silent --show-error --max-time 15 --request POST http://127.0.0.1:64404/api/chassis/mcp --header @<synthetic-header-file> --data-binary @<temporary-body.json> --write-out "\n%{http_code}"
```

| New input | Actual status/result |
| --- | --- |
| Query of 1000 U+1F9EA code points, limit 1 | 200, one unsealed passage |
| Query of 1001 U+1F9EA code points | 200, -32602 |
| Query U+2003, U+2009, CR and LF only | 200, -32602 |
| Numeric string limit `"8"` | 200, -32602 |
| Attempt to call cited_quote on the search surface | 200, -32601 |
| Wrong synthetic bearer and query of 17000 characters | 401, unauthorized before parsing |
| Negative request id -3 | 400, -32600, null response id |
| tools/list with string id bridge2-list | 200, one cited_search and its exact schema |

Measured result: **8 passed**, supervisor exit 0 in 1.62s. Full requests and responses:
`bridge2-codex-r1-curl.log`. The child home was empty before and after; the request log contained no bearer.
Request-log SHA-256: `6c4ab2a0fa3bbaa2e765d3c6f7ff39a2bcee375a8b96702b7c20f5037f4b3e3a`.
The probe terminated its child, waited, and connected again to prove refusal:
`{"server_stopped": true, "port_closed": true}`. Temporary headers and request files were removed.

## Real offline CLI installation

Command: `.venv/Scripts/python ../tasks/bridge2-codex-r1-install.py`.
It creates a new read-only release mirror and a canonical archive/lock of the current product commit.
Exact Docker argv, runtime hashes, complete profile inventory, catalog and assertions are retained in
`bridge2-codex-r1-install.log`; the launcher and pin are outside the repository.

```json
{
  "sha": "9a5066ab2dad310dd5a1843a882e7d72aeb43ed5",
  "sha256": "4605505f6cf7ecc173c3d57a585a4f9f5697cb3891ad302477d74e90e6301a41",
  "size": 2048000
}
```

The Docker image is `sha256:4d1caded1f729ae443eb803f26ffde7b61e696aeaef62f099abb6dd6b14257c7`.
Flags: `--network none --user 0:0 --cpus 2 --memory 4g --pids-limit 300`; disposable tmpfs at
`/opt/chassis` and `/opt/runtime`. Host venv, host source archive, runtime archives, warmed uv cache,
wheelhouse, release mirror, review inputs and repository are all mounted read-only.
Measured `external_connect_refused=true`, `mirror_writable=false`. Nothing publishes a host port.

The already provisioned CPython archive is version `3.14.7+20260901`, SHA-256
`0ab3305457051cd3e7c031857e005f1bda17c218a1990567dacaaac6dd1d14f0`; uv is `0.12.3`, SHA-256
`600cf9a742aca00d292673b16b5acffaa7b8c269a364ad0c2e79498dcb1fe101`.
The runner verifies these bytes before placing them in `/opt/runtime/fetch-<sha256>/` and supplies
`HERMES_RUNTIME_DIR=/opt/runtime`, `HERMES_TEST_RUNTIME_DIR=/opt/runtime`,
`HERMES_TEST_WHEELHOUSE=/wheelhouse`, and a loopback PEP 503 wheel index through
`UV_INDEX_URL=http://127.0.0.1:43679/simple` and `UV_INSECURE_HOST=127.0.0.1`.
The local wheelhouse serves pre-provisioned artifacts; external network access stays blocked.
This is the same provisioning mechanism described in D9's delivery, reexecuted independently.

The test invokes this real command via `_install_argv` and `subprocess.run` with an isolated root home:

```text
/opt/chassis/.venv/bin/hermes --profile bridge-probe plugins install file:///release/hermes-cited.git --ref 9a5066ab2dad310dd5a1843a882e7d72aeb43ed5 --enable --yes-deps
```

Hermes host pin: `dce1e9b37581dd62e480a9064dc04a709c2940d3`; its clean tracked checkout and the
bridge archive digest/size are verified before installation. Actual test command and result:

```text
/opt/chassis/.venv/bin/python -m pytest -vv -s --showlocals -p no:cacheprovider tests/test_profile_install.py -k a_fresh_real_profile_installs
1 passed, 29 deselected in 291.99s (0:04:51)
supervisor: exit 0, 375.19s
{"container_removed": true}
```

The first loader invocation completes host reload/readiness, including its own config backup. The next
invocation is compared against the complete post-setup profile inventory, with no plugin-created file
excluded. The test executes `after = inventory(profile_home); assert after == baseline`, asserts the
absence of `cited/`, verifies the installed commit and clean tree, and checks real scoped dispatch.
Inventory: 266 regular files; canonical JSON SHA-256 `d0fd6414968c4079e17dd9af516851fd70cb9f0e19430e4575f142eb728ab473`. The full sorted list of path,
size and SHA-256 is in the external raw log, not replaced by a test of the cited/ directory alone.

Effective plugin catalog and actual model envelope:

```json
{
  "plugins": [
    {
      "name": "hermes-cited",
      "key": "hermes-cited",
      "kind": "standalone",
      "version": "0.2.0",
      "description": "Full mode provides cited composition and audit; search mode provides only unsealed cited_search over the dedicated search surface. Tool and hook lists are potential catalogs; registration depends on CITED_BRIDGE_TOOLS.",
      "source": "user",
      "enabled": true,
      "tools": 1,
      "hooks": 0,
      "middleware": 0,
      "commands": 0,
      "error": null
    }
  ],
  "hooks": {
    "pre_llm_call": 0,
    "post_tool_call": 0,
    "transform_llm_output": 0
  },
  "commands": [],
  "call": {
    "cited_tool": "cited_search",
    "query": "hours",
    "text": "[1] sample.md\nHours\nOpen Monday to Friday.",
    "passages": [
      {
        "n": 1,
        "document": "sample.md",
        "heading": "Hours",
        "position": 0,
        "excerpt": "Open Monday to Friday.",
        "lines": [
          {
            "line": 1,
            "text": "Open Monday to Friday."
          }
        ]
      }
    ]
  }
}
```

The owned fake and local index stop in finally blocks; the supervisor confirms the container no longer
exists. Personal Hermes was not started or modified. Ports 3240/3241 were never used.

## Task reconciliation and limits

The guard/fake/manifest/docs command ran under another temporary home:
`.venv/Scripts/python -m pytest -q -p no:cacheprovider tests/test_chassis_fake.py tests/test_search_guard.py tests/test_manifest_modes.py tests/test_docs_bridge.py`
returned **63 passed in 13.37s**; log `bridge2-codex-r1-guard-fake-manifest.log`.
This supplements the historical RED evidence and closes the stale guard/install flags 1.1, 1.4, 9.4 and 9.6.
5.1 and 5.3 receive new independent execution evidence. No frontend exists; Playwright has no page to
exercise here. CLI installation, catalog and dispatch are the user-visible integration under review.

Installation passed at the product commit above. Subsequent test/documentation-only commits are not
claimed to have this archive digest. This is a review pin, not an archived/merged release pin.
The full-mode turn counterexamples remain open in the external review; integration success does not
close them. One intermediate Windows suite recorded WinError 10053 on the fake's wrong-path request;
the focused fake run above passed. Remote CI and the actual Harness service are not accredited here.
