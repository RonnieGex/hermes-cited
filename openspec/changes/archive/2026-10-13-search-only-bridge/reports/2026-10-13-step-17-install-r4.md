# Step 17 — task 13.4 / D9, offline install of the pinned bridge (bridge2 round 3)

Agent: DeepSeek. Date: 2026-10-13. Branch: `feature/search-only-bridge`.
Delivery commit of the run: `7e211baf096ce92bb07be1f8211c5759bd60ba66` (the product fix of this round).
External supervisor: `C:/Users/Franc/Documents/katalis-dev/tasks/bridge2-ds-r3-install.py`.
Raw log: `C:/Users/Franc/Documents/katalis-dev/tasks/bridge2-ds-r3-install.log`.

This re-executes task 5.3 and closes 13.4/11.4 with the fresh mirror, the canonical archive and the real CLI
of this round. The runner is the D9 one: it provisions the pinned host's managed runtimes before the network
closes, then installs the bridge offline and compares the complete profile inventory after setup.

## Command

The external supervisor cloned a fresh read-only mirror of the repository at HEAD, wrote the canonical
`git archive --format=tar` bytes of that commit into `bridge.lock`, and ran the provisioned container:

```text
docker run --rm --name bridge2-ds-r3-install --network none --user 0:0 --cpus 2 --memory 4g \
  --pids-limit 300 --tmpfs /opt/chassis:rw,exec,size=1g,mode=1777 \
  --tmpfs /opt/runtime:rw,exec,size=2g,mode=1777 \
  --env HERMES_TEST_BRIDGE_REF=7e211baf096ce92bb07be1f8211c5759bd60ba66 \
  --mount type=bind,source=.../bridge-codex-r3-host/.venv,target=/opt/chassis/.venv,readonly \
  --mount type=bind,source=.../bridge-codex-r3-linux,target=/inputs,readonly \
  --mount type=bind,source=.../bridge-r4-linux,target=/provision,readonly \
  --mount type=bind,source=.../bridge-r4-linux/upstream,target=/upstream,readonly \
  --mount type=bind,source=.../bridge-r4-linux/uv-cache,target=/opt/uv-cache,readonly \
  --mount type=bind,source=.../bridge-r4-linux/wheelhouse,target=/wheelhouse,readonly \
  --mount type=bind,source=.../bridge2-ds-r3-linux,target=/review,readonly \
  --mount type=bind,source=.../bridge2-ds-r3-linux/release,target=/release,readonly \
  --mount type=bind,source=.../hermes-cited,target=/repo,readonly \
  sha256:4d1caded1f729ae443eb803f26ffde7b61e696aeaef62f099abb6dd6b14257c7 \
  python /provision/run.py
```

Inside the container the provisioned runner executed, from `/repo`:

```text
/opt/chassis/.venv/bin/python -m pytest -vv -s --showlocals -p no:cacheprovider \
  tests/test_profile_install.py -k a_fresh_real_profile_installs
```

## Result

```text
1 passed, 29 deselected in 471.62s (0:07:51)
{"exit": 0, "seconds": 525.44}
{"container_removed": true, "seconds_total": 527.16}
SUPERVISOR_EXIT=0
```

The selected case is `test_a_fresh_real_profile_installs_the_search_bridge` (the ordinary suite skips it
without the four `HERMES_TEST_*` variables).

## Measured invariants

- **Host pin:** `dce1e9b37581dd62e480a9064dc04a709c2940d3`, checked with a clean tracked tree.
- **Bridge ref and canonical archive:** `7e211baf096ce92bb07be1f8211c5759bd60ba66`, SHA-256
  `d456cd45eeac62fd07c7358afb77d0938f34ac5bcd99f114ea81bba5c564f5be`, size `2129920` bytes, equal to the
  freshly written `bridge.lock` (the runner recomputes the archive with the isolated Git configuration).
- **Network:** `--network none`; the runner measured `external_connect_refused: true` and the route table of
  the closed namespace; `download failed` never appears in the install output. A download attempt would have
  failed, never skipped.
- **Read-only inputs:** `mirror_writable: false`; mirror, host venv, `/inputs`, `/provision`, `/upstream`,
  `/opt/uv-cache`, `/wheelhouse` and `/repo` were mounted read-only.
- **Offline runtime provisioning (D9):** managed CPython `3.14.7+20260901`, SHA-256
  `0ab3305457051cd3e7c031857e005f1bda17c218a1990567dacaaac6dd1d14f0`, and uv `0.12.3`, SHA-256
  `600cf9a742aca00d292673b16b5acffaa7b8c269a364ad0c2e79498dcb1fe101`, copied into the store before the
  network closed; the build-backend wheelhouse was served on a loopback-only index.
- **Catalog after install:** `hermes-cited` 0.2.0 `enabled: true`, `tools: 1`, `hooks: 0`, `middleware: 0`,
  `commands: 0`; the scoped dispatch returned the `cited_search` model envelope (one passage of `sample.md`).
- **Writes:** the complete profile home inventory after setup equals its baseline, and no `cited/` directory
  exists; the removed `--user 0:0` ownerships of the mounted mirror stay read-only.
- **Cleanup:** the disposable container was removed and no container of this name remains.

## Limits

- The container is disposable and its image is the pinned `sha256:4d1caded…` (Python 3.12); it is not an
  independent VM and its digest is only reproducible while that local image is present.
- The bridge pin is a review artifact of this round, not the lock of an archived merge.
- The fake chassis surface serves the one dispatch; this run does not accredit the real Harness service.
