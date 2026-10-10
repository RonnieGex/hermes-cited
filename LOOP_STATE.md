# LOOP_STATE · hermes-cited, change `hermes-plugin-r4`

STATUS: DONE (gate green)
CHANGE: hermes-plugin-r4 (OpenSpec), delta over the capability `hermes-plugin`
BRANCH: feature/hermes-plugin (no remote and no push)
BASE: `63959cd` (`docs: the round 3 READMEs, the loop state and the green gate evidence`), round 3
VERIFIED RUN: `scripts/gate.py` with the Python of the Hermes venv, `GATE: GREEN`, **58 of 58 claims in 660 s**
REVIEW: **pending**. The third Codex review (`tasks/revision-codex-hermes-cited-r3.md`) is answered finding by
finding in `tasks/entrega-cited-hermes-r4.md`; no fourth review has been asked for or run.
AGENT: DeepSeek (implementer); the publication of `RonnieGex/hermes-cited`, the review and any upstream
proposal are Fable's and Franc's
DATE: 2026-10-10
RUNTIME: Python 3.11.15 (the venv of Hermes), Hermes Agent v0.21.6+387 (commit `dce1e9b`) on Windows
CONTRACT: `tasks/mision-cited-hermes-r4.md`; review answered: `tasks/revision-codex-hermes-cited-r3.md`
DELIVERY: `tasks/entrega-cited-hermes-r4.md`

## Objective

Resolve the three Blockers, the seven Majors and the two Minors of the third adversarial review with the
contract of Fable (C1 to C4, D9 to D15): one boundary around the whole cited transformer, a final answer that
is always one of three fixed forms, one unique identifier per passage bound to the turn of the execution, the
seal written only by the plugin with its metadata escaped, a delivery policy taken from a snapshot at the
start of the turn, the retired local custody replaced by a consistency record, the declared host
incompatibilities, and the SDD closure, until `scripts/gate.py` prints `GATE: GREEN`.

## Result

`scripts/gate.py` ends with **GATE: GREEN, 58 of 58 claims in 660 s**, exit 0. Every claim asserts the
property it names:

- **C1 / H10 / H13 / H14 / H12** the whole transformer is one boundary: any exception of reading the
  configuration, resolving, rendering, composing or persisting produces the fixed operational refusal with an
  incident code, without a seal and without the error text, and the turn state is dropped in `finally`. A
  Cited refusal blocks every selection of the turn, before or after it. Every passage carries a per-turn
  `pid` that is the model's argument, the `[n]` mark of the render and the row of the log; an ambiguous
  number or an ambiguous turn is rejected instead of guessed. Dot mode loses every occurrence of the
  reserved mark, Markdown included; document and section are escaped into one line; a block or metadata that
  carries the mark withholds the seal and delivers a fixed note; the recorded text is the delivered text;
  `cited_quote` accepts only positive integers of the schema and never raises into Hermes.
- **C2 / H9 / H15** the delivery policy is a snapshot taken at the start of the turn that covers `api_server`
  (the SSE route of the desktop app), the desktop, streaming per platform, interim assistant commentary,
  streaming TTS, an unknown platform and an unreadable configuration. The empty response is declared as a
  host incompatibility with the integration test of the real finalizer that proves it, and
  `docs/upstream-proposal.md` asks for the two missing contracts without opening a PR.
- **C3 / D9 / H5** the local custody is retired with its history. What remains is a hash-chained JSONL with an
  inter-process lock that records what was really delivered; a broken chain refuses the append, a partial
  write is detected and blocks the next one, and a failed append makes the answer the operational refusal
  without a seal. `verify_log` reports internal consistency and says that it is what it checked.
- **C4 / D8 / H7 / M-R3-7** the gate predicates parse the sign, the value, the unit and the citation of one
  statement bound to the selected passage; every block of every audited answer is resolved against its own
  turn; the self-test names its failing fixtures; `finish` writes the artifacts, scans them on disk and only
  then emits the verdict. Rounds 1 and 2 are archived, round 3 stays open and is marked not archived with its
  Blockers, every task of `tasks.md` carries a command and a result, the CI steps ran locally and `STATUS`
  says what actually happened.

## Progress

- `openspec/changes/hermes-plugin-r4/`: proposal, design (D9 to D15), the spec delta (H4, H5, H9, H10
  modified; H13, H14, H15 added), tasks and `reports/` (branch, red run, facts of the host, H1 and E2E
  transcripts, docs, CI, gate).
- `openspec/changes/archive/`: `2026-10-10-hermes-plugin` and `2026-10-10-hermes-plugin-r2`, regularized with
  their history intact. `hermes-plugin-r3` stays open and is marked as not archived.
- `hermes_cited/`: `audit.py` (custody retired), `messages.py` (new), `render.py`, `verifier.py`,
  `delivery.py`, `plugin.py`, `modes.py`, `tools.py`, `verify_log.py`, the skill and `plugin.yaml`.
- `tests/`: 309 cases, including `test_host.py` (the real loader, dispatcher, finalizer and stream receiver)
  and the reproductions of the three reviews in `test_adversarial.py` and `test_gate.py`.
- `README.md`, `README.es.md`, `docs/upstream-proposal.md`, `.githooks/pre-commit` (the local gitleaks scan).
- `community-hermes` (`docs/hermes-agent`): `docs/mcp.md`, `README.md` and `README.es.md` state the round 4
  contract.

## Hard rules respected

- Every Hermes run of this round carried an explicit temporary `HERMES_HOME`; the gate refuses to run Hermes
  outside the temp directory. Nothing was written under `%LOCALAPPDATA%\hermes` or `~/.hermes`.
- Port 3240 and the live Cited were never touched; the test Cited is a temporary worktree of `origin/main`
  (`ef11f88`) built with webpack and served on 3246, stopped by PID.
- No `hermes update`, no gateway, no bot, no push, no remote, no archive of a change with Blockers.
  `DEEPSEEK_API_KEY` came from the Windows user environment (read through `winreg`) and was never printed.
- gitleaks before every commit through `.githooks/pre-commit` (staged snapshot) and over the whole history:
  `no leaks found` in 16 commits.

## Earlier rounds (for the record)

- Round 3 closed `hermes-plugin-r3` with `GATE: GREEN` (52 of 52, 306 s) on `63959cd`, but the third review
  found three Blockers, seven Majors and two Minors, so D9 to D15 replace the custody of D3/D6, the delivery
  policy of D7 and the gate of D8.
- Round 2 closed `hermes-plugin-r2` with `GATE: GREEN` (38 of 38, 304 s) on `f948a91`; round 1 closed
  `hermes-plugin` with `GATE: GREEN` (25 of 25, 248 s) on `a1ba154`.
