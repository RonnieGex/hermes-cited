# Execution of the hermes-plugin change

Contract: `tasks/mision-cited-hermes.md`. Prove every task with a command and its outcome before checking it.

- [x] 0. Bootstrap the repository: `git init` on `main`, Apache-2.0 `LICENSE`, `NOTICE` "Built by Katalis", `openspec init`, and this change with proposal, design, spec and tasks.
- [x] 1. H0 — read the Hermes source and write `reports/hermes-facts.md` with file and line for every fact the plugin depends on. Re-verified against `dce1e9b` after the update of 2026-10-09.
- [x] 2. Write the failing tests first (unit, verifier, chain, mode, plugin load) and record the red run under `reports/`. Evidence: `reports/2026-10-09-step-2-red.md` (7 collection errors).
- [x] 3. H2/H6 — implement the JSON-RPC client and the two native tools with clear unconfigured errors and redaction.
- [x] 4. H5 — implement the hash-chained audit log and `python -m hermes_cited.verify_log`.
- [x] 5. H4 — implement `/cited`, `/dot`, the `pre_llm_call` rules and the deterministic `transform_llm_output` verifier.
- [x] 6. H3 — package the `cited` skill and register it from the plugin.
- [x] 7. H1 — verify the MCP route end to end in a temporary `HERMES_HOME` and store the evidence. Evidence: `reports/2026-10-09-step-4-h1-mcp.md`.
- [x] 8. H8 — run the unit suite, the plugin load under the Hermes venv, and the end-to-end Cited runs (price, guarantee, refusal, cited-mode log). Evidence: `reports/2026-10-09-step-5-e2e.md`.
- [x] 9. H7 — write `README.md` and `README.es.md`, then the Cited worktree documentation changes.
- [x] 10. `scripts/gate.py` affirms H0–H8 and prints `GATE: GREEN`. Evidence: `reports/2026-10-09-step-6-gate.md` (25 of 25 claims, 283 s).
- [x] 11. Close: `tasks/entrega-cited-hermes.md`, `LOOP_STATE.md` with `STATUS: DONE`, and the `tasks/todo.md` boxes.

Evidence lives in `reports/` and `openspec/changes/hermes-plugin/reports/`; filenames carry a date prefix.
