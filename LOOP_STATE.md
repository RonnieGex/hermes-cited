# LOOP_STATE · hermes-cited, change `hermes-plugin`

STATUS: DONE
CHANGE: hermes-plugin (OpenSpec), new capability `hermes-plugin`
BRANCH: main (new repository, `git init`; no remote and no push)
BASE: none — the first commit of the repository
VERIFIED COMMIT: a1ba154 (`fix: retry the removal of the temporary trees until the killed processes release them`)
AGENT: DeepSeek (implementer); the publication of `RonnieGex/hermes-cited` and the review are Fable's
DATE: 2026-10-09
RUNTIME: Python 3.11.15 (the venv of Hermes), Hermes Agent v0.21.6+387 (main `dce1e9b`) on Windows

## Objective

Cited in Hermes Agent as a native Python plugin: `cited_search` and `cited_ask` over
`POST <CITED_URL>/api/mcp`, the `/cited` and `/dot` modes, a deterministic verifier that replaces an
answer no passage grounds, the hash-chained log of `$HERMES_HOME/cited/audit.jsonl`, tests and
documentation, until `scripts/gate.py` prints `GATE: GREEN`.

## Result

`scripts/gate.py`, run with the Python of the Hermes venv, ends with **GATE: GREEN, 25 of 25 claims in
248 s**, exit 0, on the commit `a1ba154`. It affirms H0 to H8: the fact sheet of H0, the unit suite
(92 cases green), `hermes mcp add` and `hermes mcp test cited` against a local Cited of `samples/` on
`127.0.0.1:3246`, a natural question over MCP that calls `mcp__cited__cited_ask` and answers 380 pesos
with its citation, the plugin installed with `hermes plugins install "file:///…" --enable --yes-deps`,
the price question in cited mode (native `cited_search` first, 380 pesos, seal `Verified by Cited`),
the English guarantee question (90 days), an unanswered question refused without inventing a price, the
chain of the log verifying with `python -m hermes_cited.verify_log`, dot mode without the seal, and the
documentation of both READMEs and of the Cited worktree. The gate removes every temporary `HERMES_HOME`
it creates and stops the Cited server by its PID.

## Phase

Closed. The delivery Franc reads is `katalis-dev/tasks/entrega-cited-hermes.md`, in Mexican Spanish,
with the table of the gate, the evidence and the `## Issues`. The review, the archive of the change and
the publication of the repository are Fable's.

## Progress

- **Bootstrap** (`a5fab51`): `git init` on `main`, Apache-2.0 `LICENSE`, `NOTICE` "Built by Katalis",
  `openspec init` and the change `hermes-plugin` (proposal, design, spec with requirements and
  scenarios, tasks).
- **H0** (`f07b9fa`): `reports/hermes-facts.md`, read in the source of the installed Hermes and
  re-verified against `dce1e9b` after the update of 2026-10-09, plus `reports/2026-10-09-cited-runbook.md`
  with the exact commands of the local Cited.
- **Tests first** (`7609c5b`): `tests/` with the fake `/api/mcp`, the client, the two tools, the
  verifier, the chain, the modes, the registration and the packaged skill; red with seven collection
  errors (`reports/2026-10-09-step-2-red.md`).
- **Implementation** (`f4ce1f1`): `hermes_cited/` (config, client, tools, verifier, audit, verify_log,
  modes, plugin, the `cited` skill) and the entry point `__init__.py` with `plugin.yaml`.
- **Gate and documentation** (`aeadb17`, `a1ba154`): `scripts/gate.py`, `README.md`, `README.es.md` and
  the evidence of the steps.

## Evidence

- `reports/2026-10-09-step-6-gate.md`: the table of the 25 claims and the `GATE: GREEN` line.
- `reports/2026-10-09-step-4-h1-mcp.md`: the output of `hermes mcp add`, the config fragment it wrote,
  `hermes mcp test cited` and the MCP question.
- `reports/2026-10-09-step-5-e2e.md`: the four end-to-end runs (price, guarantee, unanswered, dot) and
  the verification of the log.
- `reports/hermes-facts.md`: H0, with file and line.
- `reports/2026-10-09-cited-runbook.md`: the startup, the seed and the protocol of the test Cited.
- `.tmp/gate/` (not versioned): the raw logs of each command the gate runs.

## Hard rules respected

- No byte was written under `%LOCALAPPDATA%\hermes` or `~/.hermes`: every Hermes run used a temporary
  `HERMES_HOME`, and the gate refuses to start one that is not under the temp directory. One
  `hermes mcp test cited` was run without `HERMES_HOME` early in the mission and read the real config
  (a read-only connection test); it is reported as a RISK in the delivery.
- No `hermes update`, no `hermes gateway`, no bot; port 3240 and the live Cited of Franc were never
  used as the target of a test.
- `DEEPSEEK_API_KEY` was read from the environment only; no secret is in a file, a report or a commit;
  the test token is random and lives only in the temporary homes; `gitleaks git` is clean over the
  history.
- No push, no remote, no commit on `main` of the Cited worktree (its documentation is committed on the
  branch `docs/hermes-agent`), no archive of the OpenSpec change.
- The Cited worktree was not rebuilt and no process of another session was stopped.
- Commits in English, small, one per step; the code, the specs, the tests and this file are in English;
  the delivery Franc reads is in Mexican Spanish.
