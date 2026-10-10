# LOOP_STATE · hermes-cited, change `hermes-plugin-r4`

STATUS: DONE (gate green), round 6
CHANGE: hermes-plugin-r4 (OpenSpec), delta over the capability `hermes-plugin`
BRANCH: feature/hermes-plugin (no remote and no push)
BASE: `bb4686d` (`docs: the round 5 closing evidence of the loop state`), round 5
VERIFIED RUN: `scripts/gate.py` with the Python of the Hermes venv, `GATE: GREEN`, **66 of 66 claims in 644 s**
REVIEW: **pending**. The fifth Codex review (`tasks/revision-codex-hermes-cited-r5.md`) is answered finding by
finding in `tasks/entrega-cited-hermes-r6.md`; no sixth review has been asked for or run.
AGENT: DeepSeek (implementer); the publication of `RonnieGex/hermes-cited`, the review and any upstream
proposal are Fable's and Franc's
DATE: 2026-10-10
RUNTIME: Python 3.11.15 (the venv of Hermes), Hermes Agent v0.21.6+387 (commit `dce1e9b`) on Windows
CONTRACT: `tasks/mision-cited-hermes-r6.md` (with the scope decision D11 approved by Fable) over
`tasks/mision-cited-hermes-r4.md` (C1 to C4, **amended by D11**); reviews answered:
`tasks/revision-codex-hermes-cited-r4.md` (round 5) and `tasks/revision-codex-hermes-cited-r5.md` (round 6)
DELIVERY: `tasks/entrega-cited-hermes-r6.md`

## Objective (round 6)

Resolve the Blocker, the five Majors and the Minor of the fifth adversarial review with the exact fix it
wrote, without widening the contract: the incident code never breaks its own boundary; the snapshot separates
the surfaces it can read from the accreditation the host does not give and rejects a `FailedConfigRead`; the
sanitisation of dot mode covers the whole document (entities, soft breaks, inline and reference links),
checks the postcondition of absence and gives a fixed safe note when it cannot complete; the gate binds the
original number and the line number with its text, compares the whole answer against the plugin's fixed
templates, measures the amount inside the resolved block and identifies a run by the entries its execution
appended; the commands and the documentation say the implemented policy. **D11 applies to all of it**: while
the host exposes no accreditable delivery contract, the mark `Verified by Cited` is not emitted on any route,
the code keeps one capability point that answers "not accredited", and the record says in words that it
registers the plugin's composition and not the terminal message.

## Result

`scripts/gate.py` ends with **GATE: GREEN, 66 of 66 claims in 644 s**, exit 0. The suite reports **713
passed**. Every claim asserts the property it names:

- **B-R5-1 / H10** `incident_code()` never raises: a failure of `secrets.token_hex` returns the constant
  reserve code, and the emergency exit depends on no entropy, no disk, no configuration and no logger. The
  real loader and dispatcher return the fixed operational refusal with no seal and no model prose.
- **M-R5-1 / H16 / D11** `delivery.accredited_delivery()` is the single capability point and answers `False`;
  `Snapshot` records `surface_clear` and `accredited` separately and `seal` requires both; a `FailedConfigRead`
  is unreadable; no route emits the mark and the answer carries the fixed note. The real
  `TurnRunner._setup_stream_consumer` reproduction, with no double, shows the disagreement between the file
  and the receivers.
- **M-R5-2 / H16** the real footer and a complete `finalize_turn` record the plugin's composition with no seal
  and a `composition_note` that says what the row is.
- **M-R5-3 / H4** dot mode removes the mark over the whole document, in every presentation the consumer
  renders, repeats the removal a bounded number of times and delivers a fixed safe note when it cannot
  complete; `escape_meta` escapes the entity ampersand.
- **M-R5-4 / H5** the gate resolves each selection by call, `pid`, original number, position and line number
  with its text, compares the whole answer, measures the amount inside the resolved block, binds a run to what
  its execution appended and matches an operational refusal against the validated template.
- **M-R5-5** the handlers of `/cited` and `/dot` state the scope of the final message, the retention and the
  removal of the mark in any answer; both READMEs, `docs/mcp.md`, the proposal and the two `community-hermes`
  READMEs follow them.
- **Regressions** `tests/regressions/` holds 404 tests: 46 of R1, 51 of R2, 139 of R3, 104 of R4 and 64 of R5,
  one per attack, with the review and the finding id in the docstring. The gate runs the directory twice.

## Progress

- `hermes_cited/`: `plugin.py` (the safe incident code, the dot-mode safety note, the `composition_note`),
  `delivery.py` (the capability point, the two halves, the `read_error` rejection), `render.py` (the
  document-wide sanitisation, the bounded repetition, the entity ampersand), `messages.py` (the new mode
  texts and the two fixed sentences).
- `scripts/gate.py`: the hardened predicates, the new self-test cases and the new claims (`H16`, the run
  binding, the whole-answer comparison).
- `tests/regressions/`: `test_r5_transformer.py`, `test_r5_delivery.py`, `test_r5_host.py`,
  `test_r5_render.py`, `test_r5_gate.py` and `test_r5_messages.py`; the R1 to R4 corpus updated so every
  assertion that expected the seal requires its absence.
- `openspec/changes/hermes-plugin-r4/`: design (D17), spec delta (H16 and the amended H4, H9, H10, H15),
  tasks with the command and result of every round 6 task, and the reports of the red run, the fixes, the
  documentation, the traceability, the suite and the gate.
- `README.md`, `README.es.md`, `docs/upstream-proposal.md` and the Cited documentation of `community-hermes`
  (`docs/hermes-agent`) state the round 6 contract and its limits.
- Small commits in `feature/hermes-plugin` (docs, tests, code, spec scenarios, gate wording and the
  green-gate reports with this loop state) and one in `community-hermes`, each with its local gitleaks scan.

## Hard rules respected

- Every Hermes run of this round carried an explicit temporary `HERMES_HOME`; the gate refuses to run Hermes
  outside the temp directory. Nothing was written under `%LOCALAPPDATA%\hermes` or `~/.hermes`.
- Port 3240 and the live Cited were never touched; the test Cited is a temporary worktree of `origin/main`,
  served on 3246 and stopped by PID.
- No `hermes update`, no gateway, no bot, no push, no remote, no archive of a change with Blockers.
  `DEEPSEEK_API_KEY` came from the environment and was never printed. No secret was read or published.
- gitleaks before every commit through `.githooks/pre-commit`.

## Earlier rounds (for the record)

- Round 5 closed `hermes-plugin-r4` with `GATE: GREEN` (59 of 59, 616 s) on `bb4686d`; the fifth review found
  one Blocker, five Majors and one Minor, so round 6 hardened the boundary of the incident code, the
  accreditation of the delivery, the sanitisation, the gate and the documentation.
- Round 4 closed `hermes-plugin-r4` with `GATE: GREEN` (58 of 58, 660 s) on `6a45132`.
- Round 3 closed `hermes-plugin-r3` with `GATE: GREEN` (52 of 52, 306 s) on `63959cd`.
- Round 2 closed `hermes-plugin-r2` with `GATE: GREEN` (38 of 38, 304 s) on `f948a91`; round 1 closed
  `hermes-plugin` with `GATE: GREEN` (25 of 25, 248 s) on `a1ba154`.
