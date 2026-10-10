# LOOP_STATE · hermes-cited, change `hermes-plugin-r3`

STATUS: DONE
CHANGE: hermes-plugin-r3 (OpenSpec), delta over the capability `hermes-plugin`
BRANCH: main (no remote and no push)
BASE: `f0ba7cc` (`feat: the cited answer written by the plugin and the fail-closed log`), round 3
VERIFIED RUN: `scripts/gate.py` with the Python of the Hermes venv, `GATE: GREEN`, 52 of 52 claims in 306 s
AGENT: DeepSeek (implementer); the publication of `RonnieGex/hermes-cited`, the review and any upstream
proposal are Fable's and Franc's
DATE: 2026-10-10
RUNTIME: Python 3.11.15 (the venv of Hermes), Hermes Agent v0.21.6+387 (commit `dce1e9b`) on Windows
CONTRACT: `tasks/mision-cited-hermes-r3.md`; review resolved: `tasks/revision-codex-hermes-cited-r2.md`
DELIVERY: `tasks/entrega-cited-hermes-r3.md`

## Objective

Resolve the three Blockers, the five Majors and the Minor of the second adversarial review of Codex, with
the design decisions D5 to D8 of the mission on top of the review, until `scripts/gate.py` prints
`GATE: GREEN`. D5 replaces D2: in cited mode the model only chooses lines and the plugin writes the answer.

## Result

`scripts/gate.py` ends with **GATE: GREEN, 52 of 52 claims in 306 s**, exit 0. Every claim asserts the
property it names:

- **D5/H4/H11/H12** the model calls `cited_search` and then `cited_quote`; the plugin discards the model's
  text whole and renders the chosen lines byte for byte with their source, their `[n]` mark and the seal;
  a changed line, a substring, a moved subject, free prose and a forged seal never reach the answer; no
  selection, a refusal or no excerpt is exactly the fixed refusal.
- **D6/H5** the append validates the whole chain and authenticates the checkpoint before writing one byte,
  crosses the result with a high-water mark per identity next to the key outside `HERMES_HOME`, allows
  genesis only for an identity registered in custody, never creates the key on a read, rolls a failed row
  back and rejects a key path inside `HERMES_HOME`. Every reproduction of B-R2-3 refuses the next append.
- **D7/H9** the delivery policy uses the host's real `gateway.config.StreamingConfig` (`is_host: true`,
  `host == plugin`); the CLI without streaming is the only explicit exception, the desktop withholds with
  the D1 warning, and `wecom`, `feishu`, `dingtalk`, `qqbot` and an unknown platform withhold.
- **D8** the gate predicates reject the fixtures of both reviews (`1380` is not `380`, `190` is not `90`,
  the refusal with a datum), the seal is crossed with the audited entry of its own turn, a delivery
  consumer measures the terminal record, and every artifact is written, redacted and scanned on disk before
  the verdict. The report counts (`4 entries`) and the literal tool order are corrected.

## Progress

- `openspec/changes/hermes-plugin-r3/`: proposal, design (D5 to D8), the spec delta (H4, H5, H9, H10
  modified; H11, H12 added), tasks and `reports/` (the red run, the facts of D5 to D7, the H1 and E2E
  transcripts, the gate table).
- `hermes_cited/`: `render.py` (new), the reduced `verifier.py`, `tools.py` (the third tool and the numbered
  lines), `plugin.py` (the render and the quote registry), `audit.py` (custody), `delivery.py` (the host
  resolver), `config.py` (`CITED_LANGUAGE`), the skill and `plugin.yaml`.
- `tests/`: 235 cases, including `test_render.py`, `test_gate.py` and the reproductions of both reviews in
  `test_adversarial.py`.
- `README.md` and `README.es.md`: the plugin-written render with a real example, the custody of D6 and the
  delivery policy of D7.
- `community-hermes` (`docs/hermes-agent`): `docs/mcp.md`, `README.md` and `README.es.md` state the new
  cited mode and link the round 3 evidence.

## Hard rules respected

- Every Hermes run of this round carried an explicit temporary `HERMES_HOME`; the gate refuses to run Hermes
  outside the temp directory and worked under a temporary home of its own. Nothing was written under
  `%LOCALAPPDATA%\hermes` or `~/.hermes`.
- Port 3240 and the live Cited were never touched. The test Cited is a temporary worktree of `origin/main`
  (`ef11f88`) built with webpack and served on 3246, stopped by PID.
- No `hermes update`, no gateway, no bot, no push, no remote, no archive of a change. `DEEPSEEK_API_KEY`
  came from the environment only. The ephemeral token was redacted before any artifact was written.
- The real home incident of round 1 is preserved as RISK in the round 2 delivery; it did not repeat.

## Earlier rounds (for the record)

- Round 2 closed `hermes-plugin-r2` with `GATE: GREEN` (38 of 38, 304 s) on `f948a91`, but the second review
  found three Blockers, five Majors and one Minor, so D5 replaces D2 and the code changes.
- Round 1 closed `hermes-plugin` with `GATE: GREEN` (25 of 25, 248 s) on `a1ba154`; B2, B3, M2, M3 and M7
  of that round stay solved and were not undone.
