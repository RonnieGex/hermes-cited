# Step 8: independent adversarial review (Codex) and its resolution

- Date: 2026-10-21, America/Mexico_City.
- Reviewed: branch `feature/single-profile-scope`, HEAD `d0704b6`, base `58fa6cd`.
- Reviewer: Codex CLI 0.157.0, model `gpt-6-astra`, reasoning effort `high`, sandbox `read-only`, run by Fable from
  the clone with the prompt below. Fable implemented and does not review; Codex modified no file. The reviewer was
  given the read-only shallow clone of Hermes v0.22.4 (commit `4d043038`) and checked every file:line the design
  cites against it.

```
codex exec -s read-only --skip-git-repo-check -C <clone> "<prompt>" < /dev/null
```

The prompt named the scope (`git diff main...HEAD` and `openspec/changes/single-profile-scope/`), the rules
(`openspec/config.yaml`, H19 to H22, design D2 of `search-only-bridge`), seven points to check (the host contract and
every host state, fail-closed order and redaction, precedence and rotation, regressions, tests, documentation,
portability) and the output structure (Verdict, Findings as Blocker/Major/Minor, Checked, Not verified).

## Verdict of the reviewer

**FAIL**: "the fallback can accept another profile's registration and secrets, and it rejects a launch-body state
that the pinned host explicitly supports."

## Findings and their resolution

| Severity | Finding | Resolution |
| --- | --- | --- |
| Blocker | Pinned identity and live process home can select different profiles. With the process home pinned to A, the task override on A and B mirrored into `HERMES_HOME`, the real host answers `serves_routed_profile() == False` while `get_process_hermes_home()` is B; the plugin built B's mapping and `_check_registration` accepted B's registration for a task of A. Reproduced by the reviewer with the real routing functions and synthetic mappings. | `_single_profile_scope()` reads both `get_routing_process_hermes_home()` (the pinned identity, the home the host compares in `_is_process_home`) and `get_process_hermes_home()` (the live home); when they name different homes, canonically, the scope is refused before the builder is called; when they agree, the builder is called with the pinned identity and the scope's home is the pinned identity. H23 states it; design D1 and D4.5 record it; `test_a_live_home_that_disagrees_with_the_pinned_identity_is_refused` and `test_the_scope_home_is_the_pinned_identity_when_both_agree` cover it; the real-host probe asserts both homes equal the temporary `HERMES_HOME`. |
| Major | Multiplexing rejection ignores the host's launch-body exception: inside `launch_body()` with the flip done, the host's `get_secret` answers from `_LAUNCH_BODY_SCOPE` while `current_secret_scope()` is `None`; the plugin refused, and the READMEs and the manual said "the host raises" unconditionally. | **Resolved with a recorded deviation.** The plugin keeps failing closed in that state: the launch-body scope is a private context variable of the host with no public accessor, the state is transitional (v0.22.4 activates multiplexing eagerly at boot, so the mid-body flip is the lazy backstop), and reading private state would tie the plugin to the host's internals. H23, design D4.3, both READMEs and the manual now say precisely that the host's unscoped read raises there *or answers from a launch body armed before the flip*, and that the plugin refuses both. The real-host probe enters `launch_body()`, flips multiplexing and records both facts: the host's `get_secret` answers the `.env` value, the plugin raises the fixed sentence. Recorded as a RISK of the delivery. |
| Major | A builder exception can bypass the fixed-message redaction: `except CitedScopeError: raise` also re-raised a `CitedScopeError` raised by the builder, so its text reached `_refuse_registration`. | The host calls run inside `try` blocks that turn every exception, whatever its type, into a fresh `CitedScopeError(SCOPE_SENTENCE) from None`; the plugin's own refusals are raised outside those blocks. `test_a_builder_that_raises_the_plugins_own_error_is_still_the_fixed_sentence` asserts the sentence and the registration diagnostic on stderr. |
| Minor | `-I` ignores `PYTHONDONTWRITEBYTECODE`, so the real-host subprocess could write `__pycache__` into the checkout. | The subprocess runs with `-I -B`; the probe reports `sys.dont_write_bytecode` and the test compares the `__pycache__` inventory of `hermes_cited/` and `tests/` before and after. |
| Minor | The rotation test could pass with a cached mapping, because it mutated the one dictionary the builder returned and registration alone calls the scope twice. | The builder answers an independent snapshot per call, the backing mapping is replaced (not mutated) between the two handler calls, and the test asserts the builder count grows on every handler call. |
| Minor | `host_commit()` accepted an empty revision, so an unrelated branch with the named functions passed the pin check. | The revision is read with `git rev-parse HEAD`; a checkout whose revision cannot be read is skipped with the reason, and another commit fails the test. The pinned-source test also requires `serves_routed_profile` and `get_routing_process_hermes_home` in the source. |

Runs after the resolution (the real-host probe with `HERMES_HOST_0_22_SOURCE` and `HERMES_HOST_0_22_PYTHON` set):

```
.venv/Scripts/python.exe -m pytest -q tests/test_single_profile_scope.py tests/test_profile_scope.py tests/test_single_profile_host.py -p no:cacheprovider -rs
45 passed in 9.38s
exit=0
```

The strict OpenSpec validation and the documentation tests after the rewording, and the whole suite, are recorded in
the step 4 report (second section) and in the step 7 report with the pipeline of the fix commit.

## The re-check of the reviewer

The same reviewer (Codex, `gpt-6-astra`, `high`, `read-only`) re-checked the six findings on `cc2be14`:

**PASS WITH GAPS**: "all six previous findings are resolved, including one acceptable documented deviation, with one
minor documentation inconsistency and integration checks not independently rerun."

- 1 Blocker, resolved: its file-free probe with the real routing functions (pinned A, override A, live `HERMES_HOME`
  B) saw zero builder calls and no registration; with the homes agreeing, the builder and the scope use the pinned
  identity.
- 2 Major, resolved with deviation: refusing the launch-body transition is "an acceptable conservative compatibility
  limitation"; H23, D4.3, both READMEs and the manual record it consistently; the real-host test asserts both
  outcomes and its probe reproduced them.
- 3 Major, resolved: every builder exception, `CitedScopeError` included, becomes the fixed sentence with the chain
  suppressed; the registration diagnostic omits the synthetic text.
- 4, 5, 6 Minor, resolved: `-I -B` with `sys.dont_write_bytecode` asserted; independent snapshots and growing builder
  counts; `git rev-parse` with skip, fail and pass exercised.
- New Minor: the module docstring of `tests/test_single_profile_host.py` promised a skip for a different revision while
  the code fails it. Resolved in the evidence commit: the docstring now says an unreadable revision skips and another
  commit fails the pin. The implementation was judged correct.

Not independently rerun by the reviewer (no writable temporary directory in its sandbox): the pytest suites, the
filesystem-backed real-host test, the `.env` loading and the bearer transmission; those are the implementer's runs of
steps 1, 4 and 5, and the pipeline of step 7.

## What the reviewer could not run, and who ran it

Codex's read-only sandbox had no writable temporary directory, so both permitted pytest commands exited before
collection; it ran file-free Python 3.11 probes with `-I -B` against the real routing functions of the host (they
reproduced the three findings above and confirmed the installed-scope path, the refusals before the builder, the fresh
builder calls and the search path's silence about `CITED_MCP_TOKEN`). The pytest runs, the whole suite, the strict
validation and the pipeline were run by Fable: steps 1, 4, 5 and 7 of this folder.

## Observations of a sibling session

A duplicated session of the same brief (local `a44040ff`) left read-only notes on the host contract: the precedence of
`.env` over the launch environment in `owner_secret_scope` (design D2, a RISK of the delivery) and the task routed
through a `HERMES_HOME` override without multiplexing (`serves_routed_profile()`), which was adopted before this
review (design D4.4). Its third note, the cost of rebuilding the mapping on every read, is recorded in design D4.
