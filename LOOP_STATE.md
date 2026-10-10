# LOOP_STATE · hermes-cited, change `hermes-plugin-r4`

STATUS: DONE (gate green), round 7
CHANGE: hermes-plugin-r4 (OpenSpec), delta over the capability `hermes-plugin`
BRANCH: feature/hermes-plugin (no remote and no push)
BASE: `17cf4e5` (`docs: the round 6 green gate, its reports and the loop state`), round 6
VERIFIED RUN: `scripts/gate.py` with the Python of the Hermes venv, `GATE: GREEN`, **66 of 66 claims in 695 s**,
on the clean frozen tree of `a247d29` with both repositories clean
REVIEW: **pending**. The sixth Codex review (`tasks/revision-codex-hermes-cited-r6.md`) is answered finding by
finding in `tasks/entrega-cited-hermes-r7.md`; no seventh review has been asked for or run.
AGENT: DeepSeek (implementer); the publication of `RonnieGex/hermes-cited`, the review and any upstream
proposal are Fable's and Franc's
DATE: 2026-10-10
RUNTIME: Python 3.11.15 (the venv of Hermes), Hermes Agent v0.21.6+387 (commit `dce1e9b`) on Windows
CONTRACT: `tasks/mision-cited-hermes-r7.md` over `tasks/revision-codex-hermes-cited-r6.md` (M-R6-1 and
M-R6-2), over C1 to C4 of `tasks/mision-cited-hermes-r4.md` **amended by D11**
(`tasks/mision-cited-hermes-r6.md`); reviews answered: rounds 5 and 6
(`tasks/revision-codex-hermes-cited-r4.md`, `tasks/revision-codex-hermes-cited-r5.md`,
`tasks/revision-codex-hermes-cited-r6.md`)
DELIVERY: `tasks/entrega-cited-hermes-r7.md`

## Objective (round 7)

Close the only two publication blockers of the sixth review with its exact fix, without widening the contract.
**M-R6-1:** the reserved mark is detected on the **visible text of the same Markdown consumer the host uses**
(`markdown_it`): entities inside link labels, inline links, shortcut and explicit references resolved against
their definitions and the line break an HTML `<br>` renders are one mark; the visible characters are mapped
back to the spans of the original document, dot mode removes the whole presentation and re-checks the render,
cited mode keeps the documentary row as data with the documentary note and `verified=false`, and a removal
that cannot complete returns the fixed safe note. **M-R6-2:** the packaged skill the loader installs declares
that this version does not emit the seal and shows the real render with the retention note; the universal
promises of the terminal message and the record are replaced by the plugin-composition wording in both
READMEs, `docs/upstream-proposal.md` and `community-hermes/docs/mcp.md`; the record is described as the
composition when the append succeeds, dot as the model's text with the mark removed, and the three pending
host-side contracts are aligned by number and name. **D11 is unchanged.**

## Result

`scripts/gate.py` ends with **GATE: GREEN, 66 of 66 claims in 709 s**, exit 0. The suite reports **739
passed**. Every claim asserts the property it names:

- **M-R6-1 / H4** `render.consumer_visible` renders with `markdown_it`, replaces tags by a space, decodes the
  entities and collapses the whitespace; `consumer_mark` is the detection on it and `contains_mark` delegates
  to it, so the cited path and the gate predicates read the same authority. `_visible_tokens` maps entities
  inside labels, inline links, full/collapsed/shortcut references resolved against the definitions, images and
  HTML tags (the `<br>` line break included) back to the original spans. `strip_mark` checks the postcondition
  **on the render**, repeats the bounded removal and returns the fixed safe note when it cannot complete.
- **M-R6-2 / H17** the skill the plugin really registers (`plugin.register` through `ctx.register_skill`)
  declares the retention and carries no fenced render with the mark; a list of forbidden phrases of the
  previous contract is searched in the five public documents, which also carry the composition wording and the
  three pending contracts by name.
- **Regressions** `tests/regressions/` holds 430 tests: 46 of R1, 51 of R2, 139 of R3, 104 of R4, 64 of R5 and
  26 of R6 (16 of M-R6-1 and 10 of M-R6-2). The gate runs the directory twice and its self-test carries the
  nine counterexamples of the sixth review.

## Progress

- `hermes_cited/render.py`: the consumer reading (`consumer_visible`, `consumer_mark`), the reference
  definitions, the link-construct scanner, the HTML tag reader and the span map; the round 6 behaviour is kept
  for the cases it already covered.
- `hermes_cited/skills/cited/SKILL.md`: the seal is declared not emitted, the example is the real render with
  the retention note, and the promise is the plugin's composition.
- `README.md`, `README.es.md`, `docs/upstream-proposal.md` and `community-hermes/docs/mcp.md`: the composition
  wording, the record of the composition, dot with the mark removed, and the three pending contracts.
- `scripts/gate.py`: the nine counterexamples in `gate_selftest()` and the round 7 report titles.
- `.github/workflows/tests.yml`: `markdown-it-py` beside `pytest`, so the M-R6-1 regression measures the real
  consumer on a clean leg.
- `openspec/changes/hermes-plugin-r4/`: design D18, the spec amendments (H4, H5, H10) and the new H17, the
  round 7 tasks and the reports of the red run, the fixes, the documentation, the suite and the gate.
- Small commits in `feature/hermes-plugin` (spec, tests, code, documentation, reports) and one in
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

- Round 6 closed `hermes-plugin-r4` with `GATE: GREEN` (66 of 66, 660 s) on `0e0c0cf`; the sixth review found
  two Majors that blocked publication, so round 7 rewrote the reading of the visible mark and the public
  wording.
- Round 5 closed `hermes-plugin-r4` with `GATE: GREEN` (59 of 59, 616 s) on `bb4686d`.
- Round 4 closed `hermes-plugin-r4` with `GATE: GREEN` (58 of 58, 660 s) on `6a45132`.
- Round 3 closed `hermes-plugin-r3` with `GATE: GREEN` (52 of 52, 306 s) on `63959cd`.
- Round 2 closed `hermes-plugin-r2` with `GATE: GREEN` (38 of 38, 304 s) on `f948a91`; round 1 closed
  `hermes-plugin` with `GATE: GREEN` (25 of 25, 248 s) on `a1ba154`.
