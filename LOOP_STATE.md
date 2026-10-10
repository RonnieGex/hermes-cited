# LOOP_STATE · hermes-cited, change `hermes-plugin-r4`

STATUS: DONE (gate green), round 8
CHANGE: hermes-plugin-r4 (OpenSpec), delta over the capability `hermes-plugin`
BRANCH: feature/hermes-plugin (no remote and no push)
BASE: `06c4efd` (`docs: the round 7 gate run on the clean frozen tree`), round 7
VERIFIED RUN: `scripts/gate.py` with the Python of the Hermes venv, `GATE: GREEN`, **67 of 67 claims in 648 s**,
on the clean frozen tree of `54599e8` with both repositories clean; the cross-repository document check ran
with `CITED_DOCS_REPO` set and the exact SHA of `community-hermes` (`3a636f8`) recorded in
`openspec/changes/hermes-plugin-r4/reports/2026-10-10-step-5b-docs-repo.md`
REVIEW: **pending**. The seventh Codex review (`tasks/revision-codex-hermes-cited-r7.md`) is answered finding
by finding in `tasks/entrega-cited-hermes-r8.md`, by the scope decision D12 of
`tasks/mision-cited-hermes-r8.md`; no eighth review has been asked for or run.
AGENT: DeepSeek (implementer); the publication of `RonnieGex/hermes-cited`, the review and any upstream
proposal are Fable's and Franc's
DATE: 2026-10-10
RUNTIME: Python 3.11.15 (the venv of Hermes), Hermes Agent v0.21.6+387 (commit `dce1e9b`) on Windows
CONTRACT: `tasks/mision-cited-hermes-r8.md` (D12) over `tasks/revision-codex-hermes-cited-r7.md` (M-R7-1 and
M-R7-2), over C1 to C4 of `tasks/mision-cited-hermes-r4.md` **amended by D11**
(`tasks/mision-cited-hermes-r6.md`); reviews answered: rounds 4 to 7
(`tasks/revision-codex-hermes-cited-r4.md` to `tasks/revision-codex-hermes-cited-r7.md`)
DELIVERY: `tasks/entrega-cited-hermes-r8.md`

## Objective (round 8)

Apply **D12** of the round 8 mission with its exact scope and close **M-R7-2**. **D12:** with D11 the plugin
emits no seal on any route, so no authentic seal exists that anyone could forge; the protection of the
reserved mark is retired from the product (`strip_mark`, `contains_mark`, `consumer_visible`,
`SanitizationFailed` and the fixed sanitisation notes), dot mode delivers the model's text **intact** and its
row records exactly that string, a cited documentary line that carries the phrase is data with the general
withheld note, the public documents say in plain language that nothing in dot mode is verified and that the
phrase never comes from the plugin, and the activation of the seal requires protecting the mark again with the
render semantics of the host checked against its consumer. **M-R7-2:** the cross-repository check of
`community-hermes/docs/mcp.md` runs only when `CITED_DOCS_REPO` names a checkout and is skipped with an
explicit reason without it; the local gate always runs it, records the exact SHA of `community-hermes` and
leaves the evidence in its own report; the CI workflow declares the omission; and the isolated extraction of
the final SHA runs the suite green with the omission announced. D11 is unchanged by this round.

## Result

`scripts/gate.py` ends with **GATE: GREEN, 67 of 67 claims in 648 s**, exit 0, on the clean frozen tree of
`54599e8`. The suite reports **694 passed** with `CITED_DOCS_REPO` set and **691 passed, 3 skipped** in the
isolated extraction. Every claim asserts the property it names:

- **D12.1 / H18** no module of the product reads or removes the reserved mark (`render.py`, `verifier.py`,
  `messages.py` and `plugin.py`); `_deliver_dot` returns `None` and the entry records the model's text byte for
  byte with `applied: false`; `escape_meta` still escapes every interpretable metacharacter of the metadata.
- **D12.2 / H18** a cited documentary row that carries the phrase is data, with the general withheld note and
  `verified=false`/`seal_withheld=true`; `answer_matches_entry` accepts the phrase only where the audited
  `quoted_lines` record it.
- **D12.3 / H17** the packaged skill and the five public documents state the retired mark; the forbidden
  phrases of the previous contract are still hunted by `tests/regressions/test_r6_docs.py`.
- **D12.4 / H18** `docs/upstream-proposal.md` and D19 of the design require protecting the reserved mark again
  with the render semantics of the host checked against its consumer.
- **M-R7-2 / H17** the cross-repository check resolves its checkout from `CITED_DOCS_REPO`, the gate sets it,
  records the SHA of `community-hermes` (`3a636f8`) in `reports/2026-10-10-step-5b-docs-repo.md`, and the
  workflow declares the omission; the isolated extraction proves the skip reason is announced.
- **Regressions** `tests/regressions/` holds the round 8 modules (`test_r8_dot_passthrough.py`,
  `test_r8_docs_repo.py`, `test_r8_docs.py`) and the D12 cases of the older regression modules; the two
  modules whose whole subject D12 retired (`test_r5_render.py`, `test_r6_mark.py`) were removed and the gate
  runs the directory twice.

## Progress

- `hermes_cited/render.py`: the reader of the Markdown consumer, the span map, `strip_mark`, `mark_spans` and
  `SanitizationFailed` are gone; `escape_meta` keeps the metadata shielding and `Line` keeps no `has_mark`.
- `hermes_cited/verifier.py`, `messages.py`, `plugin.py`: `strip_seal` and the three fixed notes are gone;
  dot passes the text through and records it; cited keeps the documentary line as data with the general note.
- `hermes_cited/skills/cited/SKILL.md`, `README.md`, `README.es.md` and `docs/upstream-proposal.md`: the D12
  wording and the requirement of the activation.
- `community-hermes/docs/mcp.md`: the same wording in the Hermes Agent route (branch `docs/hermes-agent`).
- `tests/`: the round 8 regressions and the updated D12 assertions; `tests/regressions/test_r6_docs.py`
  resolves its cross-repository checkout from `CITED_DOCS_REPO`.
- `.github/workflows/tests.yml`: declares the cross-repository omission and drops the retired consumer.
- `scripts/gate.py`: the D12 fixtures and the docs-repo claim; `openspec/changes/hermes-plugin-r4/`: D19, the
  spec delta (H4, H16, H17 amended and the new H18) and the reports of the red run, the fixes, the docs, the
  standalone run, the suite and the gate.
- Small commits in `feature/hermes-plugin` (contract, code, tests, documentation, gate, reports) and one in
  `community-hermes`, each with its local gitleaks scan.

## Hard rules respected

- Every Hermes run of this round carried an explicit temporary `HERMES_HOME`; the gate refuses to run Hermes
  outside the temp directory. Nothing was written under `%LOCALAPPDATA%\hermes` or `~/.hermes`.
- Port 3240 and the live Cited were never touched; the test Cited is a temporary worktree of `origin/main` of
  `community-hermes`, served on 3246 and stopped by PID.
- No `hermes update`, no gateway, no bot, no push, no remote, no archive of a change with Blockers.
  `DEEPSEEK_API_KEY` came from the environment and was never printed. No secret was read or published.
- gitleaks before every commit through `.githooks/pre-commit`, and a full `gitleaks git` over both histories.

## Earlier rounds (for the record)

- Round 7 closed `hermes-plugin-r4` with `GATE: GREEN` (66 of 66, 695 s) on `06c4efd`; the seventh review
  found two Majors, M-R7-1 and M-R7-2, so round 8 retired the mark protection by D12 and made the
  cross-repository check explicit.
- Round 6 closed `hermes-plugin-r4` with `GATE: GREEN` (66 of 66, 660 s) on `0e0c0cf`; it recorded D11: the
  seal waits for an accreditable host.
- Round 5 closed `hermes-plugin-r4` with `GATE: GREEN` (59 of 59, 616 s) on `bb4686d`.
- Round 4 closed `hermes-plugin-r4` with `GATE: GREEN` (58 of 58, 660 s) on `6a45132`.
- Round 3 closed `hermes-plugin-r3` with `GATE: GREEN` (52 of 52, 306 s) on `63959cd`.
- Round 2 closed `hermes-plugin-r2` with `GATE: GREEN` (38 of 38, 304 s) on `f948a91`; round 1 closed
  `hermes-plugin` with `GATE: GREEN` (25 of 25, 248 s) on `a1ba154`.
