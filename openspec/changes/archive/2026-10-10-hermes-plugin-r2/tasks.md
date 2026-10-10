> **Regularized in round 4 (2026-10-10).** This change was archived as
> `openspec/changes/archive/2026-10-10-hermes-plugin-r2` when `hermes-plugin-r4` opened, to obey the limit of
> two open changes per repository. Its boxes are exactly as round 2 left them, with their evidence; the verifier
> it specified was replaced by D5 (round 3) and its custody by D9 (round 4). The historical reports travel with
> it.

# Execution of the hermes-plugin-r2 change

Contract: `tasks/mision-cited-hermes-r2.md`, with the decisions D1 to D4 on top of `tasks/revision-codex-hermes-cited.md`.
Proof first: every task is checked only after its command ran and its outcome was recorded under
`openspec/changes/hermes-plugin-r2/reports/`. Filenames carry a date prefix.

- [x] 0. Open the change `hermes-plugin-r2` with this proposal, the design (D1 to D4), the spec delta and these tasks.
- [x] 1. Write the failing tests of B1 to B3, M1 to M7 and m1 and record the red run. Evidence: `reports/2026-10-10-step-1-red.md`.
- [x] 2. B2/D2/M1 — the extractive verifier: segments, `« »` quotations, evidence only from excerpts, citation map, `refused`. Evidence: `tests/test_verifier.py`, `tests/test_tools.py`.
- [x] 3. B3 — the private opener that refuses every redirect; tests of 301/302/303/307/308 and the HTTPS downgrade. Evidence: `tests/test_client.py`.
- [x] 4. M2 — the reflection check of the client, the redaction of the tool results and of every audit field. Evidence: `tests/test_client.py`, `tests/test_tools.py`, `tests/test_plugin.py`.
- [x] 5. M3 — the exclusive inter-process lock of the append, with a multi-process test. Evidence: `tests/test_audit.py`.
- [x] 6. M4/D3 — `seq`, log identity, the authenticated checkpoint and the key outside `HERMES_HOME`. Evidence: `tests/test_audit.py`, `tests/test_verify_log.py`.
- [x] 7. M5/H10 — session and turn in the entry, schema validation, an operational refusal on a failed append. Evidence: `tests/test_plugin.py`.
- [x] 8. D1/B1/H9 — the delivery policy: the effective streaming configuration, the withheld seal, the load-time diagnostic, the exact READMEs and `docs/upstream-proposal.md`. Evidence: `tests/test_delivery.py`, `tests/test_plugin.py`.
- [x] 9. M7 — the audit command from the installed plugin, outside the checkout. Evidence: `reports/2026-10-10-step-12-gate.md` (the two H5 claims).
- [x] 10. M6 — rewrite `scripts/gate.py` with one predicate per named property, the adversarial fixtures and the redaction of every artifact, and test the installed command from a foreign directory.
- [x] 11. m1 — correct both READMEs, the skill, `docs/mcp.md` and the Cited READMEs; move the round 1 reports into `openspec/changes/hermes-plugin/reports/` and fix the links. In `community-hermes`: `git merge origin/main` first.
- [x] 12. Run `scripts/gate.py` with the Python of the Hermes venv until it prints `GATE: GREEN`. Evidence: `reports/2026-10-10-step-12-gate.md` (38 of 38, 304 s).
- [x] 13. Close: `tasks/entrega-cited-hermes-r2.md` with the finding-to-fix table and the `## Issues`, and `LOOP_STATE.md` with `STATUS: DONE`.
