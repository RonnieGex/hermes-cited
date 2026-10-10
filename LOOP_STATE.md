# LOOP_STATE · hermes-cited, change `hermes-plugin-r2`

STATUS: DONE
CHANGE: hermes-plugin-r2 (OpenSpec), delta over the capability `hermes-plugin`
BRANCH: main (new repository, `git init`; no remote and no push)
BASE: afccfa8 (`docs: the loop state closes the hermes-plugin change with GATE: GREEN`), round 1
VERIFIED RUN: `scripts/gate.py` with the Python of the Hermes venv, `GATE: GREEN`, 38 of 38 claims in 304 s
AGENT: DeepSeek (implementer); the publication of `RonnieGex/hermes-cited`, the review and any upstream
proposal are Fable's and Franc's
DATE: 2026-10-10
RUNTIME: Python 3.11.15 (the venv of Hermes), Hermes Agent v0.21.6+387 (commit `dce1e9b`) on Windows
CONTRACT: `tasks/mision-cited-hermes-r2.md`; review resolved: `tasks/revision-codex-hermes-cited.md`
DELIVERY: `tasks/entrega-cited-hermes-r2.md`

## Objective

Resolve the three Blockers, the seven Majors and the Minor of the adversarial review of round 1, with the
design decisions D1 to D4 of the mission on top of the review, until `scripts/gate.py` prints `GATE: GREEN`.

## Result

`scripts/gate.py` ends with **GATE: GREEN, 38 of 38 claims in 304 s**, exit 0. Every claim asserts the
property it names:

- **D1/B1** the delivery policy: the effective streaming configuration is read and the seal is withheld on a
  messaging surface whose streaming is on, with `docs/upstream-proposal.md` specifying the host hook (no PR
  and no issue upstream).
- **D2/B2/M1** the extractive verifier: the evidence is only a non-empty excerpt of the turn; a datum-bearing
  reader-visible line is accepted only when it appears verbatim, quoted between `« »`; free text cannot carry
  a datum; the citation marks are validated against the turn's map; a `refused` is an explicit refusal.
- **D3/M3/M4** the log: `seq`, log identity, an exclusive inter-process lock around the append, a schema
  validated before hashing and at verification, and an HMAC-authenticated checkpoint whose key lives outside
  `HERMES_HOME`. Removing the last entry, cutting a suffix, rewriting and recomputing, rolling back the
  checkpoint and a missing checkpoint all fail the verifier.
- **D4/B3/M2/M5/M6/M7/m1** the redirect is refused before the second request; a reflected token is rejected in
  success and error and redacted recursively in the log; a failed append is an operational refusal without a
  seal; the gate was rewritten and proves the installed audit command from outside the checkout; the
  documentation and the change status claim only what was verified.

## Progress

- `openspec/changes/hermes-plugin-r2/`: proposal, design (D1 to D4), the spec delta (H4-H10) and tasks.
- `openspec/changes/hermes-plugin-r2/reports/`: `hermes-facts-r2.md` (the delivery paths read in the Hermes
  source), the gate table, the H1 and H8 transcripts.
- `hermes_cited/`: `verifier.py` (extractive), `audit.py` (lock, `seq`, log identity, checkpoint, key outside
  the home), `client.py` (private opener, reflection check), `tools.py` (excerpt evidence), `plugin.py`
  (session/turn, delivery policy, operational refusal), `delivery.py` (new).
- `tests/`: 189 cases, including `test_adversarial.py` (one fixture per finding) and `test_delivery.py`.
- `docs/upstream-proposal.md` (English) and `.github/workflows/tests.yml` (added, not yet executed).
- Round 1 reports moved to `openspec/changes/hermes-plugin/reports/`; `tasks.md`, `design.md`, `README.md`,
  `README.es.md` and the skill corrected per m1.
- `community-hermes` (`docs/hermes-agent`): `git merge origin/main` (`ef11f88`, PR #21 merged) and the
  Hermes Agent documentation corrected in `docs/mcp.md`, `README.md` and `README.es.md`.

## Hard rules respected

- Every Hermes run of this round carried an explicit temporary `HERMES_HOME`; the gate refuses to run Hermes
  outside the temp directory. Nothing was written under `%LOCALAPPDATA%\hermes` or `~/.hermes`.
- Port 3240 and the live Cited were never touched. The test Cited is a temporary `git` worktree of
  `origin/main` (`ef11f88`) built with webpack and served on 3246, stopped by PID.
- No `hermes update`, no gateway, no bot, no push, no remote, no archive of a change. `DEEPSEEK_API_KEY` came
  from the environment only. The ephemeral token was redacted before any artifact was written.
- The real home incident of round 1 is preserved as RISK 3 in the delivery; it did not repeat.

## Round 1 (for the record)

The previous state closed `hermes-plugin` with `GATE: GREEN` (25 of 25, 248 s) on `a1ba154`. That state is
superseded by this change: the review found Blockers the historical gate could not see, and the round 1 fact
sheet assumed `display.streaming: false` on the CLI when the real default of `_cli_config_defaults()` is
`true`.
