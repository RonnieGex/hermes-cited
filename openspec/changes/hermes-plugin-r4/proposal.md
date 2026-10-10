# Why

Round 3 of `hermes-plugin` closed with `GATE: GREEN` (52 of 52 claims), but the third independent adversarial
review of Codex (`tasks/revision-codex-hermes-cited-r3.md`, verdict **CAMBIOS**) found three Blockers, seven
Majors and two Minors. The review separated what the plugin can promise from what the host does not let it do:

- an exception anywhere in the transformer leaves the model's prose in place (the host dispatcher logs it and
  keeps the answer), so the "the model never writes in cited mode" promise had a hole outside the append;
- the local custody of the log (HMAC key, checkpoint, high-water mark) can be restarted on Windows by changing
  the casing of a path, and its transaction could authenticate a response that was never delivered: whoever
  controls the PC can revert any local custody;
- the host withholds nothing from the desktop SSE route, from streaming TTS or from interim commentary, and it
  never calls `transform_llm_output` when the model's text is empty (`agent/turn_finalizer.py:501`), so a cited
  turn with an empty model answer is delivered empty.

The mission `tasks/mision-cited-hermes-r4.md` (the contract approved by Fable) keeps the design of D5 and turns
those limits into explicit contract. **D9 replaces D3 and D6**: the local custody is retired and what remains is
a consistency record.

# What Changes

- **C1 — the final answer in cited mode is shielded (B-R3-1, M-R3-1, M-R3-2, M-R3-3, m-R3-1).** For every
  cited turn that reaches `transform_llm_output`, the delivered text is exactly one of three: the render of
  chosen literal lines, the fixed localized refusal, or a fixed localized operational refusal with an incident
  code and no interpolated error. A boundary around the **whole** transformer turns any exception (reading the
  configuration, resolving, rendering, persisting) into the operational refusal, and the turn state is dropped
  in `finally`. A Cited refusal anywhere in the turn blocks every selection, before or after it, and yields the
  fixed refusal with no seal. Every passage gets a unique identifier inside the turn, with its mapping to the
  call, the original number, the document and the position, and that same identifier travels through
  `cited_quote`, the render and the log; when more than one turn of a session is active and the turn cannot be
  told apart, the selection is rejected instead of guessed. The seal is written only by the plugin: dot mode
  loses every occurrence of it, Markdown included; the document and the section are shown escaped in a single
  line; when a block or metadata carries the mark the seal is withheld and a fixed note is delivered; the text
  recorded in the log is the text delivered. `cited_quote` accepts only positive integers of the schema and
  never raises into Hermes.
- **C2 — what the host does not let the plugin guarantee is declared, not faked (M-R3-4, M-R3-5).** The
  promise is about the **final message**, not about everything that passed through the screen. The seal is
  withheld on every surface where something else could have been seen: `api_server` (the SSE route of the
  desktop app), messaging with streaming, active TTS, active interim commentary, and any case that cannot be
  determined. The decision is taken from a snapshot of the effective configuration at the **start** of the
  turn, not by re-reading the YAML at the end. The empty response is declared a host incompatibility, with an
  integration test of the real finalizer that proves it, and never presented as covered.
  `docs/upstream-proposal.md` asks Hermes for the two missing contracts (synchronous retention of the delivery
  and a final composition step even when the response is empty). No PR and no issue is opened upstream.
- **C3 — the local log is a consistency record (D9 replaces D3 and D6).** The HMAC custody (key, checkpoint,
  high-water mark, custody record, pending transaction) is removed with its history. What remains is a
  hash-chained JSONL with an inter-process lock that records what was really delivered after composing; if the
  append fails the answer is the operational refusal without a seal. `verify_log` checks the internal
  consistency and says so in those words. The README explains in plain language that the record is for
  reviewing and reproducing each answer but is not tamper-proof against whoever controls the PC, and that
  audited custody arrives with Cited Ledger, on the server side.
- **C4 — gate, documentation and SDD closure (M-R3-6, m-R3-2, M-R3-7).** The gate predicates parse the sign,
  the value and the unit as one assertion and resolve every citation against the selection, the source and the
  turn identifier of that run; every block of every audited answer is checked; the new negatives enter the
  self-test; the artifact consumer is named for its exact scope; `finish` writes every artifact, including the
  report, scans them on disk and only then emits the verdict. The round 1 to 3 changes are regularized without
  losing traceability, the step 0 branch is `feature/hermes-plugin`, every task carries its command and result,
  the CI workflow steps run locally, and `STATUS` tells the truth: DONE only with a green gate, with the Codex
  review still pending.

# Impact

- Capability: `hermes-plugin`.
- Code: `hermes_cited/audit.py` (reduced), `render.py`, `verifier.py`, `delivery.py`, `plugin.py`, `modes.py`,
  `tools.py`, `verify_log.py`, `plugin.yaml`.
- Tests: `tests/test_audit.py`, `test_verify_log.py`, `test_plugin.py`, `test_delivery.py`, `test_tools.py`,
  `test_modes.py`, `test_render.py`, `test_adversarial.py`, `test_gate.py` and a new host integration test.
- Evidence: `scripts/gate.py` and `openspec/changes/hermes-plugin-r4/reports/`.
- Documentation: both READMEs, the skill, `docs/upstream-proposal.md` and the Cited docs of `community-hermes`.
- Not touched: the real `%LOCALAPPDATA%\hermes`, port 3240, upstream, any remote.
