# Independent installation execution, round 3

Reviewer: Codex. Date: 2026-10-12. Branch: feature/search-only-bridge.
This is task 5.3 validation evidence, not an independent approval of Codex's corrections.
The orchestration scripts and raw output remain outside the repository under
`C:/Users/Franc/Documents/katalis-dev/tasks/bridge-codex-r3-*`.

## Provisioning and isolation

The real pinned host checkout is `dce1e9b37581dd62e480a9064dc04a709c2940d3`.
An owned clone and Linux venv were provisioned outside all product repositories.
The personal Hermes checkout was only read as a Git source, never executed or modified.
The disposable Docker image is pinned by digest:
`sha256:4d1caded1f729ae443eb803f26ffde7b61e696aeaef62f099abb6dd6b14257c7`.
Linux Python is 3.12.14; pytest is 8.4.2. This is a container, not an independently provisioned VM.

After provisioning, every execution uses `--network none --cpus 2 --memory 2g --pids-limit 200`.
The product repository, release mirror, venv and review inputs are bind-mounted read-only.
The host source and its fresh native Git index are reconstructed in a disposable tmpfs.
The root/profile homes are temporary. External socket connection fails and `/proc/net/route`
has no routes. `os.access('/release', os.W_OK)` is false. No personal service or provider is used.
The outer supervisor timeout is 900 seconds, the pytest child timeout 650 seconds,
the delivered CLI timeout 600 seconds and Git helper timeout 120 seconds.

The independent test release pin is:

```json
{
  "sha": "db67d85a1a9787edac988d9531ac23223d66169a",
  "sha256": "a9fb58695e005dbb5db4337b386016ed2d03fded6eab5c6290b1bc83967693d6",
  "size": 1986560
}
```

It is a review input outside the repository, not the final archived merge release lock.
The canonical digest and byte size were independently accepted by Linux Git.

## Actual command

The external supervisor invokes `docker run --rm`, the limits and read-only mounts above,
the pinned image, and `python /review/run.py`. Its exact Windows argv is retained in the raw log.
Inside the container, the executed pytest command is:

```text
/opt/chassis/.venv/bin/python -m pytest -vv -s --showlocals -p no:cacheprovider tests/test_profile_install.py -k a_fresh_real_profile_installs
```

All four `HERMES_TEST_*` prerequisites are set to the provisioned host, read-only mirror,
explicit bridge SHA and external lock. `HERMES_TEST_NETWORK_BLOCKED=1` is backed by the
container network namespace, not only by the variable's value. The real CLI argv is:

```text
/opt/chassis/.venv/bin/hermes --profile bridge-probe plugins install file:///release/hermes-cited.git --ref db67d85a1a9787edac988d9531ac23223d66169a --enable --yes-deps
```

## Measured result

Final execution: `bridge-codex-r3-linux-native9.log`, **1 failed, 29 deselected in 37.10s**.
Supervisor: exit 1, 92.38 seconds, outer temporary home `{}` before and after,
`process_stopped=true`. The final container runs as UID 0, matching the ownership of the read-only
Windows mirror mount; it is not a successful non-root execution. The mount remains read-only even
for that UID, as verified by `os.access`. No guard, pin or archive assertion was removed.

The pin, tracked checkout cleanliness, bridge commit, read-only mirror and canonical digest/size
checks pass. The real CLI clones the bridge and exits 1 before publication. Its stdout says
`Plugin 'hermes-cited' was not published: python: install failed: download failed`.
The missing managed runtime is CPython 3.14.7 from the host's 20260901 distribution. Both the
GitHub distribution and the Hermes asset mirror fail with `Temporary failure in name resolution`.
The network restriction remains in force; no runtime code-hosting access is enabled to make the test pass.

The provisioned Python 3.12 host venv does not satisfy that separate managed-runtime dependency.
Task 5.3 remains open for complete offline provisioning and a successful installation/catalog run.
The test never reaches its final profile inventory; complete before/after profile evidence is not claimed.
The outer home inventory is a separate boundary and is not substituted for the installed profile.
The fake is stopped by the runner's finally block; the owned container exits and `--rm` removes it.
`docker ps -a --filter name=bridge-codex-r3` afterwards returns no containers. No ports were published
from the container; its loopback server and all processes die with its namespace.

Earlier setup failures are retained rather than reclassified as product defects:

- A Windows bind-mounted host checkout exceeded the Git status timeout.
- An extracted Windows Git index reported tracked changes on Linux. A fresh native clone/index
  fixed this; the complete tracked checkout then passed the delivered pin/cleanliness check.
- UID 65534 could inspect the mirror through the outer Git environment, but the pinned CLI's
  hardened Git environment rejected its different ownership during file-URL cloning. Raw logs
  `bridge-codex-r3-linux-native7.log` and `bridge-codex-r3-linux-native8.log` show the full
  `fatal: detected dubious ownership in repository at '/release/hermes-cited.git'` diagnostic.

The earlier delivery's claim that the runner could not be executed because there was no CLI or
mirror is superseded: both were provisioned, and the actual CLI was executed offline.
The Windows integration probe separately loaded the installed layout with the real pinned loader
and registry, obtained one search tool with no full hooks, and dispatched one successful fake HTTP request.
That result is recorded in task 12.1 and is not represented as a successful CLI installation.

## Issues

- NOT DONE / Major: task 5.3, a successful fully offline install with the host's managed runtime
  pre-provisioned for the disposable profile, followed by catalog dispatch and complete profile inventory.
- RISK: the delivered runner currently prints only the final profile inventory and checks absence of
  `cited/`; it does not compare every profile file against a baseline taken after setup. This is a
  source-level verification gap, not a measured claim that the plugin wrote an unexpected file here.
- UNKNOWN: the remaining runtime/catalog behavior after successful CLI installation. The independent
  Windows loader probe passed, but it does not cover this uncompleted path.
- NOT DONE: Fable's independent review and final approval.
