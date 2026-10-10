> **Not archived in round 4 (2026-10-10).** The third adversarial review of Codex
> (`tasks/revision-codex-hermes-cited-r3.md`, verdict CAMBIOS) found 3 Blockers, 7 Majors and 2 Minors in the
> code this change specified, so it is **not** archived as approved and its boxes are left as round 3 wrote
> them. Its path changed: rounds 1 and 2 moved to `openspec/changes/archive/`, so every reference in this
> directory to `openspec/changes/hermes-plugin/` or `openspec/changes/hermes-plugin-r2/` now points under
> `openspec/changes/archive/`. What replaces it is `hermes-plugin-r4`.

# Execution of the hermes-plugin-r3 change

Contract: `tasks/mision-cited-hermes-r3.md`, with the decisions D5 to D8 on top of
`tasks/revision-codex-hermes-cited-r2.md`. Proof first: every task is checked only after its command ran
and its outcome was recorded under `openspec/changes/hermes-plugin-r3/reports/`. Filenames carry a date
prefix. Round 1 and round 2 reports stay where they are; this change never rewrites them.

- [x] 0. Open the change `hermes-plugin-r3` with this proposal, the design (D5 to D8), the spec delta (H4, H5, H9, H10 modified; H11, H12 added) and these tasks.
- [x] 1. Write the failing tests of D5 to D8, including one fixture per finding of both reviews, and record the red run: 4 collection errors (`render` did not exist) plus the rewritten modules failing against round 2. Evidence: `reports/2026-10-10-step-1-red.md`.
- [x] 2. D5/H11 — `render.py`, the deterministic line numbering, the `cited_quote` tool and its turn registry. Evidence: `tests/test_render.py`, `tests/test_plugin.py`; gate `D5`, `H11`.
- [x] 3. D5/H4/H12 — the reduced by-construction verifier, the plugin-written render, the fixed refusal, the `CITED_LANGUAGE` templates and the dot-mode seal strip. Evidence: `tests/test_verifier.py`, `tests/test_plugin.py`; gate `H12`, `H4`.
- [x] 4. D5 — discard the model's text: the B-R2-1, B-R2-2 and M-R2-2 reproductions become cases that never reach the answer, plus the forged-seal case with valid data and streaming on. Evidence: `tests/test_adversarial.py`; gate `H4`.
- [x] 5. D6/H5 — the fail-closed append: whole-chain validation, authenticated checkpoint, the high-water mark per identity outside `HERMES_HOME`, genesis only in custody, the key created before the first row and never on a read, the recoverable transaction and the `HERMES_HOME` rejection. Evidence: `tests/test_audit.py`, `tests/test_verify_log.py`; gate `D6`.
- [x] 6. D6 — the B-R2-3 and M-R2-3 reproductions: `alter → legitimate append → verify`, the full rollback, the lost key, the first-write failure and the checkpoint failure. Evidence: `tests/test_adversarial.py`; gate `D6`.
- [x] 7. D7/H9 — the host `StreamingConfig` resolver, the versioned compatibility copy, the full platform matrix and the withheld notes. Evidence: `tests/test_delivery.py`, `tests/test_plugin.py`; gate `D7`.
- [x] 8. D8/M-R2-4 — the gate predicates: complete values with boundaries and a bound citation, the conservative refusal, the seal crossed with the audited verifier, the delivery consumer and the on-disk artifact scan. Evidence: `tests/test_gate.py`, `scripts/gate.py`; gate `D8`.
- [x] 9. D8/m-R2-1 — correct the counts, the timing, the literal tool order and the state; the change tasks record a command and a result per step. Evidence: `tasks.md`, `LOOP_STATE.md`, `reports/2026-10-10-step-5-e2e.md`, `reports/2026-10-10-step-11-gate.md`.
- [x] 10. Documentation — both READMEs, the skill, `plugin.yaml` and the Cited docs of `community-hermes` describe the new cited mode with a real render, the custody of D6 and the delivery policy of D7.
- [x] 11. Run `scripts/gate.py` with the Python of the Hermes venv until it prints `GATE: GREEN`, with the reproductions of both reviews as fixtures. Evidence: `reports/2026-10-10-step-11-gate.md` (**52 of 52, 306 s**; the two earlier red runs are recorded in the delivery).
- [x] 12. Close: `tasks/entrega-cited-hermes-r3.md` with the finding-to-fix table and the `## Issues`, and `LOOP_STATE.md` with `STATUS: DONE`.
