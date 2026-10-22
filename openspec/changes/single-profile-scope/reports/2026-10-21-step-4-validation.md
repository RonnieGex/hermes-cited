# Step 4: the whole suite and the strict specification check

Date: 2026-10-21. Agent: Fable. Repository venv (Python 3.11.15, pytest 9.1.1), Windows 11,
`PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 PYTHONUTF8=1`, `-p no:cacheprovider`.

## The whole suite, twice

Run 1, on the tree with the single-profile branch and before the routed-task refusal was added:

```
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider -rs
946 passed, 6 skipped in 581.70s (0:09:41)
exit=0
```

Run 2, on the final tree (the routed-task refusal, its two parametrized cases and the documentation wording):

```
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider -rs
948 passed, 6 skipped in 399.24s (0:06:39)
exit=0
```

The six skips are the same in both runs and none is new to this change but the last two, which are the opt-in
real-host probe and are run in step 5:

| Skip | Reason printed |
| --- | --- |
| `tests/regressions/test_r6_docs.py` (two) and `tests/regressions/test_r8_docs.py` (one) | `CITED_DOCS_REPO is not set: the cross-repository check of community-hermes/docs/mcp.md is omitted` |
| `tests/test_profile_install.py:600` | `the disposable VM is not available in this run: HERMES_TEST_HOST_ROOT, HERMES_TEST_MIRROR, HERMES_TEST_BRIDGE_REF, HERMES_TEST_BRIDGE_LOCK are not all set` |
| `tests/test_single_profile_host.py:83` and `:94` | `HERMES_HOST_0_22_SOURCE does not name a checkout of Hermes Agent v0.22.4` |

Run 1 printed one line of noise from a loopback fake in the middle of the dots (`Exception occurred during processing
of request from ('127.0.0.1', 60245)`), the known chatter of `ThreadingHTTPServer` when a client closes first; the
test that owned it passed and run 2 printed nothing of the kind.

## The specification

```
npx --yes @fission-ai/openspec@1.1.1 validate --all --strict
```

First run: `✗ change/single-profile-scope`, `ADDED "H23 - The single-profile contract of Hermes 0.22" must contain SHALL
or MUST`. The validator reads the first line of a requirement's text; the first line of H23 carried its condition and
its SHALL came on the second. The requirement was reworded so its first line reads "The plugin SHALL read its
configuration from the launch profile when ...", with the same content. Second run:

```
✓ spec/hermes-plugin
✓ change/single-profile-scope
Totals: 2 passed, 0 failed (2 items)
```

## State of the checkout

There is no plugin database. `git status --short` after both runs lists only the files of this change: no test left a
file in the checkout, and the temporary homes of the probes live under the system temp directory.

## Not run locally

The `tests` workflow of GitHub Actions (Ubuntu and Windows, Python 3.11) runs on the pull request and is recorded from
it in the step 7 report. The pre-commit hook runs `gitleaks` on the staged snapshot of every commit.
