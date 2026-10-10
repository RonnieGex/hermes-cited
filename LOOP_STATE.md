# LOOP_STATE · hermes-cited, change `hermes-plugin-r4`

STATUS: DONE (gate green)
CHANGE: hermes-plugin-r4 (OpenSpec), delta over the capability `hermes-plugin`
BRANCH: feature/hermes-plugin (no remote and no push)
BASE: `6a45132` (`docs: the loop state of the round 4 gate`), round 4
VERIFIED RUN: `scripts/gate.py` with the Python of the Hermes venv, `GATE: GREEN`, **59 of 59 claims in 616 s**
REVIEW: **pending**. The fourth Codex review (`tasks/revision-codex-hermes-cited-r4.md`) is answered finding by
finding in `tasks/entrega-cited-hermes-r5.md`; no fifth review has been asked for or run.
AGENT: DeepSeek (implementer); the publication of `RonnieGex/hermes-cited`, the review and any upstream
proposal are Fable's and Franc's
DATE: 2026-10-10
RUNTIME: Python 3.11.15 (the venv of Hermes), Hermes Agent v0.21.6+387 (commit `dce1e9b`) on Windows
CONTRACT: `tasks/mision-cited-hermes-r5.md` over `tasks/mision-cited-hermes-r4.md` (C1 to C4); reviews answered:
`tasks/revision-codex-hermes-cited-r3.md` (round 4) and `tasks/revision-codex-hermes-cited-r4.md` (round 5)
DELIVERY: `tasks/entrega-cited-hermes-r5.md`

## Objective

Resolve the two Blockers, the eight Majors and the Minor of the fourth adversarial review with the exact fix
it wrote, without widening the contract: the transformer never returns `None` on a resolution failure and
starts in an unknown mode; only the real `cited_search` and `cited_ask` handlers feed evidence and the
envelope type must match; the passage identifier is assigned while the result is built and reaches the model;
the consistency record publishes atomically; the delivery policy comes from the object the host loaded and an
invalid YAML is unreadable; the reserved mark is read in the visible text of Markdown and the metadata escapes
every interpretable metacharacter; the diagnostic redacts the bearer recursively; the host footer is a
declared limit; the gate binds a block to its evidence table and checks every block from `main`; and the
documentation transcribes C3. All of it under the same change, with the red tests first, and the
reproductions of the four reviews as permanent tests in `tests/regressions/`.

## Result

`scripts/gate.py` ends with **GATE: GREEN, 59 of 59 claims in 616 s**, exit 0. The suite reports **648
passed**. Every claim asserts the property it names:

- **B-R4-1 / H10** the mode starts unknown; the dot pass-through needs an affirmative resolution, and a
  failure of the turn lookup or of the mode state produces the fixed operational refusal, never `None`,
  through the loader and the dispatcher of the real host.
- **B-R4-2 / H14** a `cited_quote` result is a selection and its text is never reparsed as evidence; the
  envelope's `cited_tool` must match the handler, and the reproduction `search -> quote -> post_tool_call ->
  quote` leaves one passage and no fabricated source.
- **M-R4-1 / H5** the append prepares the new file beside the published one and replaces it as the last
  publishing operation: a failure at write, flush, `fsync`, close or replace leaves the published bytes
  identical and the next append is accepted.
- **M-R4-2 / H9** the snapshot reads the object the host loaded, names its `source`, withholds when the host
  cannot answer, and treats an invalid YAML as unreadable.
- **M-R4-3 / H14** the `pid` is in the JSON the model receives and the hook reuses it.
- **M-R4-4 / H12** the mark is detected in the visible text of the admitted Markdown presentations and the
  metadata escapes every interpretable metacharacter.
- **M-R4-5 / H10** the bearer is redacted from the whole formatted traceback, chained cause included.
- **M-R4-6 / H15** the integration test reproduces the real footer sequence and declares the third host
  incompatibility.
- **M-R4-7 / D8** the citation is parsed with the amount and the block resolves against the evidence table;
  `main` checks every block of every cited entry and excludes the refusals by name.
- **M-R4-8 / H5 / H7** the documentation transcribes C3, corrects the R4 seal row, separates the two HTTP
  calls from the local selection and conditions the mode messages.
- **Regressions** `tests/regressions/` holds 339 tests: 45 of R1, 51 of R2, 139 of R3 and 104 of R4, one per
  attack, with the review and the finding id in the docstring. The gate runs the directory twice.

## Progress

- `hermes_cited/`: `plugin.py` (the unknown mode, the evidence handler, the sanitized diagnostic and the
  evidence table), `tools.py` (identity of the envelope and the bound places), `render.py` (the visible mark
  and the metadata escape), `audit.py` (the atomic publication), `delivery.py` (the host object, the strict
  YAML and the `source`), `verify_log.py` (docstring).
- `scripts/gate.py`: `amount_statement` binds the sign, the amount, the unit and the citation of one line;
  `blocks_are_bound` resolves against the evidence table; `main` checks every block, passes each run's
  `turn_id` and uses the bound amount; the self-test carries the three counterexamples of M-R4-7.
- `tests/regressions/`: the permanent corpus of the four reviews.
- `openspec/changes/hermes-plugin-r4/`: design (D16), spec delta (round 5 scenarios), tasks with the command
  and result of every task, and the reports of the red run and of the corpus.
- `README.md`, `README.es.md`, `docs/upstream-proposal.md` and the Cited documentation of `community-hermes`
  (`docs/hermes-agent`) state the round 5 contract and its limits.
- Five commits in `feature/hermes-plugin` (docs, tests, code, spec scenarios, gate wording) and one in
  `community-hermes`, each with its local gitleaks scan.

## Hard rules respected

- Every Hermes run of this round carried an explicit temporary `HERMES_HOME`; the gate refuses to run Hermes
  outside the temp directory. Nothing was written under `%LOCALAPPDATA%\hermes` or `~/.hermes`.
- Port 3240 and the live Cited were never touched; the test Cited is a temporary worktree of `origin/main`,
  served on 3246 and stopped by PID.
- No `hermes update`, no gateway, no bot, no push, no remote, no archive of a change with Blockers.
  `DEEPSEEK_API_KEY` came from the environment and was never printed. No secret was read or published.
- gitleaks before every commit through `.githooks/pre-commit`.

## Earlier rounds (for the record)

- Round 4 closed `hermes-plugin-r4` with `GATE: GREEN` (58 of 58, 660 s) on `6a45132`, but the fourth review
  found two Blockers, eight Majors and one Minor, so round 5 hardened the boundary, the provenance, the
  record, the host policy, the render, the diagnostic, the gate and the documentation.
- Round 3 closed `hermes-plugin-r3` with `GATE: GREEN` (52 of 52, 306 s) on `63959cd`.
- Round 2 closed `hermes-plugin-r2` with `GATE: GREEN` (38 of 38, 304 s) on `f948a91`; round 1 closed
  `hermes-plugin` with `GATE: GREEN` (25 of 25, 248 s) on `a1ba154`.
