# Design of hermes-plugin-r4

Contract: `tasks/mision-cited-hermes-r4.md` (approved by Fable; answers M-R3-7 of
`tasks/revision-codex-hermes-cited-r3.md`). Round 3 kept the design of D5; this round keeps D5, D7 and D8, and
replaces the custody decisions.

## D9 — the local custody is retired; what remains is a consistency record

*Replaces D3 and D6.*

Whoever controls the PC can revert any local custody, and each round opened a new hole in Windows: B-R3-2
restarted the identity by changing the casing of a file name, and B-R3-3 authenticated a response that was
never delivered when two steps of the transaction failed. Both are consequences of defending a local file
against its own owner. The plugin stops defending it.

- **Kept:** one JSONL line per delivered response, chained by `hash = sha256(prev_hash + canonical_json(entry
  without hash))`, with a monotonic `seq`, a `log_id` and `prev_hash`; an exclusive inter-process lock over a
  lock file of the log; a full validation of the chain before writing one byte, so a broken tail refuses the
  append instead of restarting from genesis.
- **Removed with its history:** the HMAC key (`CITED_AUDIT_KEY_PATH`), the checkpoint, the high-water mark per
  identity, the custody record, the pending transaction and the file-identity (`_identifier`) logic. No file is
  written outside `HERMES_HOME` any more. `git log` keeps the code and the reports of rounds 2 and 3 recoverable
  if Franc wants the custody back.
- **Failure mode:** if the append fails, `transform_llm_output` returns the fixed operational refusal (C1c)
  without a seal. A refused answer is not a delivered one.
- **`verify_log`:** reports internal consistency of the chain and says exactly that. It no longer authenticates
  anything, and its message never claims custody.
- **Honesty:** the README states in plain language that the record is for reviewing and reproducing each
  answer, that it is not tamper-proof against whoever controls the PC, and that audited custody arrives with
  Cited Ledger, on the server side.

Alternative rejected: keeping the checkpoint without the key (it proves nothing), and keeping the key in the
Hermes profile (it travels with the log it is meant to defend).

## D10 — one boundary around the whole transformer

B-R3-1 showed that guarding only the append leaves the model's answer in place: the real dispatcher logs the
exception of a hook and keeps the original text (`agent/turn_finalizer.py:104`, `507`; the hook is called with
`_invoke_hook_safely`). The fix is not another guard around another call: it is a single boundary.

`transform_llm_output` in cited mode is:

1. resolve the turn, the mode and the delivery snapshot;
2. build the answer (render or fixed refusal);
3. compose the delivered text, seal included;
4. append the audit entry of **that** text;
5. on any failure of 2 to 4, replace the answer with the fixed operational refusal with an incident code;
6. `finally`: drop the turn state.

Every step lives inside one `try`. Reading the configuration, resolving the language, rendering, escaping,
composing and appending are all covered. The incident code is a random hexadecimal string generated at the
failure site; the error text is redacted with the bearer and written to `stderr` and to the logger, never into
the answer. Dot mode keeps its own contract (the model's text, minus the seal) and does not answer with a
refusal, because in dot mode the plugin never promised the text.

## D11 — the text that is recorded is the text that is delivered

M-R3-3 pointed at the last discrepancy: with an answer that is only the seal, dot mode recorded the empty
string while delivering the note "The reserved seal was removed from this answer.". The order is fixed: the
final text is composed **first** (render, seal or withheld note, or the dot-mode strip and its note when the
strip empties the text), the append records exactly that string, and only then is it returned. The audit entry
carries `response` (the delivered text), `transcript` (what the plugin would have returned without the seal)
and `delivery` (the snapshot and the decision), so a reader can reconstruct both without guessing.

## D12 — one identifier per passage, bound to the turn of the execution

M-R3-2 showed two things: local numbers collide between two searches of the same turn, and the handler guessed
the turn by "last active of the session". Both are fixed the same way.

- Each passage gets a per-turn identifier `pid` (`P1`, `P2`, ... in the order the calls returned them), with an
  explicit mapping to the call index, the original `n` of the Cited envelope, the document, the section and the
  position. `cited_quote` takes that `pid`. A numeric `passage` is still accepted while it identifies exactly
  one passage of the turn; when it is ambiguous the selection is rejected and the error asks for the `pid`.
- The `[n] mark` of the render uses the same `pid` number, so the mark the user reads, the selection the model
  made and the log row are the same reference.
- `cited_quote` binds to the real execution identity: the turn of the `turn_id` the host passed, else the only
  active turn of the session. With more than one active turn and no identity, the selection is **rejected**;
  the plugin never guesses. `turn_id`, `session_id` and `task_id` are all read from the hook arguments.

## D13 — the delivery snapshot and the surfaces the host does not retain

M-R3-4 established that the class of `StreamingConfig` can be right while the data differs: the plugin re-read
the YAML at the end of the turn, and `api_server`, TTS and interim commentary were not covered. The plugin
cannot read live callbacks, so it reads the effective configuration **at the start of the turn** and freezes it
in the turn object:

| Surface | Withholds the seal when | Reason |
|---|---|---|
| `api_server` | always | it is the SSE route of the desktop app (`gateway/platforms/api_server.py:2394`) |
| `desktop` | always | the app wires its own SSE stream (D1) |
| `cli` | `display.streaming` is on, or interim commentary is on | the delta callback of the CLI is wired by that configuration |
| messaging platform | top-level `streaming` (with the platform override) is on, or interim commentary is on for that platform | deltas can be delivered before the transform |
| unknown platform | always | it cannot be determined |
| any surface | streaming TTS is on (`tts.auto_tts`) | voice is a delivery that the turn cannot take back |

The comment of interim commentary is resolved the way the host resolves it
(`display.platforms.<p>.interim_assistant_messages` → `display.interim_assistant_messages` → the platform
default, read from the pinned copy of `gateway/display_config.py`). The seal is granted only when the snapshot
affirmatively shows that nothing else could have been seen. The withheld note says which surface withheld and
what to turn off. The snapshot, its reasons and the decision go into the audit entry (`delivery`).

The plugin still cannot retain the deltas of the surfaces it accepts; that limit is stated in the README and in
`docs/upstream-proposal.md`, which asks Hermes for synchronous retention of the delivery.

## D14 — the empty response is a host incompatibility

`agent/turn_finalizer.py:501` returns before invoking the hook when `final_response` is false, so in the real
host a cited turn whose model answer is empty is delivered empty and never reaches the plugin. The plugin does
not present that as covered. The contract asks Hermes for a final composition step executed once per cited turn
before persisting and delivering, even when the text is empty. Until the host offers it: `tests/test_host.py`
runs the real `apply_llm_output_transform` with `""`, records `("", False, None)`, and the README and the
delivery report state the incompatibility and its consequence (a turn with an empty model answer gets no
render; the log gets no row for it, because nothing was composed and nothing was delivered by the plugin).

## D15 — the gate measures what it names

M-R3-6 listed four predicates that accepted wrong data and one self-test that reported success while failing.
The predicates are rewritten as named properties:

- `amount_statement(text, amount, unit, mark)` parses **one** statement: an optional sign (which must match the
  literal), the exact amount as a standalone token, a unit of the required kind, and a citation mark that
  resolves to the passage the run selected. `-380 pesos [99]` is not `380`, `380 kg` is not `380 pesos` and a
  mark that names another passage is not a bound citation.
- `entry_for(entries, question, mode, turn_id)` selects the entry of the run, never by question alone.
- Every block of every cited answer in the log is checked against a full line of an excerpt stored in its own
  entry, and the seal is crossed with the entry's own delivery decision.
- `gate_selftest()` returns the exact list of failing fixtures (empty = pass), and the new counterexamples of
  this review are in it.
- `finish()` writes every artifact, then scans them on disk, then emits the verdict; the report is written
  before it is scanned and re-verified if it is rewritten. `delivered_of` is renamed
  `terminal_record_of` and its claim names its scope: it measures the terminal record of a documented
  stream-json consumer, not the temporary deliveries of a real CLI, desktop, bot or TTS.
