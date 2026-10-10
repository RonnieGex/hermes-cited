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
5. on any failure of 1 to 4, replace the answer with the fixed operational refusal with an incident code;
6. `finally`: drop the turn state.

Every step lives inside one `try`. Reading the configuration, resolving the language, rendering, escaping,
composing and appending are all covered. The mode starts **unknown**: the dot pass-through is allowed only
after dot was resolved affirmatively, for this turn or before the boundary opened (M-R4-1, round 5), so a
failure of the resolution of step 1 can never return `None` and leave the model's prose in place. The
incident code is a random hexadecimal string generated at the failure site; the error text is redacted with
the bearer and written to `stderr` and to the logger, never into the answer. Dot mode keeps its own contract
(the model's text, minus the seal) and does not answer with a refusal, because in dot mode the plugin never
promised the text.

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
- Round 5 (M-R4-3): the identifier is assigned **while the search result is built**, bound to the turn that
  identity resolves, and the annotated record is exactly what the model receives, what the render marks and
  what the log stores. `post_tool_call` reads the identifiers out of the result instead of assigning new ones,
  so the model no longer has to infer the counter of a passage it never saw.

## D16 — round 5: provenance, record, policy and diagnostics

The fourth review (`tasks/revision-codex-hermes-cited-r4.md`) rebuilt four properties that the round 4 code
only appeared to hold:

- **B-R4-2 — provenance by construction.** Only the real handlers `cited_search` and `cited_ask` feed
  `note_call`, the envelope's own `cited_tool` must match the handler that produced it, and `cited_quote` is
  recorded as a selection and never reparsed: its text is document content even when it is valid JSON. A
  document that contains an envelope can no longer fabricate a second passage and a second source.
- **M-R4-1 — atomic publication.** The append validates the chain under the inter-process lock, prepares the
  published bytes plus the new row in a temporary file of the same directory (write, flush, `fsync`, close) and
  replaces the published file as the last publishing operation. A failure of any earlier stage leaves the
  published chain byte-identical and produces the operational refusal; the refusal never asserts an absence
  when the state is indeterminate. The interruption of the process **between** publishing and delivering is
  declared, not promised away.
- **M-R4-2 — the effective policy of the host.** The snapshot reads the object the host itself loaded
  (`hermes_cli.config.load_config_readonly`) when this process carries an explicit `HERMES_HOME` and the
  host's own config path is the one of the home being asked about; otherwise a standalone run reads the file.
  An unreadable or malformed configuration withholds the seal (a syntax or type error is not a missing
  parser), and the snapshot names its `source`.
- **M-R4-4 — the visible mark.** The reserved mark is detected in the visible text of the admitted Markdown
  presentations (internal emphasis and link labels included), dot mode removes those occurrences whole, and
  cited mode withholds the seal with the fixed note. `escape_meta` escapes every interpretable Markdown
  metacharacter of a document or a section.
- **M-R4-5 — the diagnostic.** The diagnostic is built separately, the configured bearer is redacted
  recursively from the whole formatted traceback (exception, arguments and chained cause) and only that
  sanitized string is emitted; no raw `exc_info` reaches a logger.
- **M-R4-6 — the host can add text afterwards.** The real finalizer appends its file-mutation footer after the
  transformer and after the append, so the persisted row can differ from the final message. This is a third
  declared host incompatibility (`docs/upstream-proposal.md`) and the C1 promise is about the plugin's
  composition, not about the routes of the host that add text; the integration test reproduces the sequence.
- **M-R4-7 — the gate's binding.** The citation is parsed with the amount as one statement, the block is
  resolved against the evidence table the entry stores (call, `pid`, `uid`, number, document, section,
  position and lines) and the whole block is compared against the answer; `main` checks **every** block of
  every cited entry, passes each run's `turn_id` to the lookup of its row, and excludes the refusals by name.
- **Regressions.** The reproductions of the four reviews are permanent tests under `tests/regressions/`, one
  per attack, with the review and the finding id in the docstring.

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

## D17 — round 6: the seal waits for the host (D11 of `tasks/mision-cited-hermes-r6.md`)

The fifth review (`tasks/revision-codex-hermes-cited-r5.md`) showed that the round 5 code still could not
accredit what the host delivers: the plugin cannot see the effective receivers (voice, commentary, streaming)
and the finalizer can add text after the plugin composition. The scope decision D11 of the round 6 mission
(approved by Fable) settles it: **while the host does not expose an accreditable delivery contract, the mark
`Verified by Cited` is not emitted on any route.** C1 to C4 are amended by this decision, and the traceability
is the round 6 mission itself plus this design entry.

- **One capability point (D11.1).** `delivery.accredited_delivery()` is the only place that answers whether
  the host accredits a turn: a per-turn policy of the effective receivers *and* the guarantee that the
  terminal message is the plugin's composition. With Hermes v0.21.6+387 (`dce1e9b`) it answers `False` on
  every route. A future host version would turn it on there, and only with a test of the real host that
  demonstrates it. A unit fixture monkeypatches the capability to prove that the point is the only blocker.
- **The seal is retained, not assumed (M-R5-1).** The snapshot keeps resolving the surfaces it can see
  (`surface_clear`) and adds the accreditation it cannot obtain (`accredited`). `Snapshot.seal` is
  `surface_clear and accredited`, so a quiet `load_config_readonly` is not enough: the plugin withholds the
  seal on an unverifiable state and says so. `FailedConfigRead`/`read_error` from the host loader is rejected
  explicitly instead of accepted as a mapping.
- **The cited composition is unchanged (D11.2).** The answer is the render of the textual lines chosen with
  `cited_quote`, the fixed refusal, or the fixed operational refusal on any failure. The model's prose never
  enters it. What changes is that the render now always carries the fixed withheld note that names the
  unaccredited delivery, because H9 asks the answer to say that the seal was withheld.
- **The record names what it stores (D11.3).** Every cited and dot entry carries `composition_note`, which
  says in words that the row records the plugin's composition, that the host may show drafts while the answer
  is written and add its own notices at the end, and that the row is therefore not a record of the terminal
  message.
- **The reserved mark stays protected (D11.4, M-R5-3).** Dot mode removes the mark from the **whole
  document**: the visible characters of entities, soft breaks, inline links and reference links are computed
  with the span of every character, the spans are removed, the postcondition of absence is checked **after**
  concatenating and normalising, and the removal repeats a bounded number of times. If it cannot complete,
  it raises and the transformer returns a fixed safe note instead of the model's untransformed text (never
  `None`). `escape_meta` escapes every Markdown metacharacter including `&`, so a named entity in a document
  or a section can never read as the mark.
- **B-R5-1 — the incident code never breaks the boundary.** `incident_code()` returns a constant, non-empty
  reserve code when the entropy dependency fails; it never raises. The emergency exit of the transformer
  therefore does not depend on entropy, disk, configuration or the logger, and a secondary failure of the
  refusal's own construction can no longer hand the model's prose back to the host.
- **M-R5-4 — the gate binds the run and the whole render.** `blocks_are_bound` resolves the call, `pid`,
  `uid`, original number, position and the **line number with its text** against the evidence table;
  `every_block_is_bound` rejects a cited entry that is not a refusal and has no blocks; `answer_matches_entry`
  compares the **whole** answer against the plugin's fixed composition templates; `bound_amount` measures the
  amount, its unit and its citation inside the already resolved block; a run is identified by the entries it
  appended to the log, and absence, ambiguity and duplicates are rejected; and an operational refusal must
  match a validated template with a code, not a `startswith`.
- **M-R5-5 — the commands and the documentation say the implemented policy.** `/cited` states the scope of
  the final message and the condition of the seal; `/dot` states that the mark is removed from any answer.
  The READMEs, the proposal, `community-hermes/docs/mcp.md` and the public Cited table follow D11.

## D18 — round 7: the visible mark is read with the host's Markdown consumer, and the published documents say only what the plugin composes

The sixth review (`tasks/revision-codex-hermes-cited-r6.md`) found two publication blockers.

- **M-R6-1 — the mark evaded the sanitisation by combining syntax.** The round 6 detector built the
  visible characters with its own hand-written reading of the Markdown, so it copied the characters of a
  link label without decoding the entities inside it, it never resolved a shortcut reference against its
  definition, and it did not read the line break an HTML `<br>` renders. `Verified [&#98;y](url) Cited`,
  `Verified by [Ci&#116;ed](url)`, `[Verified &#98;y Cited](url)`, `Verified by [Cited]` with its
  definition, `Verified by [Ci&#116;ed][c]` with its definition and `Verified<br>by Cited` all rendered the
  reserved mark and none of them was detected. The fix of M-R6-1 is: **the detection reads the visible text
  of the same Markdown consumer the host uses**, `markdown_it` of the Hermes installation — the render is
  produced, its tags are replaced by a space, its entities are decoded and its whitespace is collapsed —
  and the removal maps the visible characters it finds back to the spans of the original document, so the
  whole presentation goes with the mark. The postcondition of `strip_mark` is checked **on that render**
  and not on the detector again, the removal repeats a bounded number of times, and when it cannot complete
  the transformer delivers the fixed safe note that already exists. In cited mode the documentary line stays
  as data and the answer carries the documentary note with `verified=false`. The nine counterexamples of the
  review's annex become permanent fixtures under `tests/regressions/`, driven by the real loader, dispatcher
  and JSONL, with compliance assertions (the mark is absent from the visible text of the render in dot mode
  and the note is present in cited mode) checked with the independent renderer.
- **M-R6-2 — the installed skill and parts of the documentation still promised the pre-D11 contract.** The
  skill `ctx.register_skill` installs still said the plugin adds the seal and showed a render that ends in
  `Verified by Cited`; `community-hermes/docs/mcp.md`, both READMEs and `docs/upstream-proposal.md` still
  universalised the terminal message and the record. They are replaced by the wording the review gives:
  *for a cited turn that reaches the hook, the plugin's composition is the documentary render, the fixed
  refusal or the operational refusal; the host may add text afterwards*. The record is described as the
  plugin's composition when the append succeeds, so a persistence refusal produces no row; dot mode is
  described as the model's text with the mark removed and a fixed note when it is left empty; and the number
  and the names of the three pending host-side contracts are aligned in every public document. A new test
  reads the skill the plugin really registers and hunts the old promises in the public documents with a list
  of forbidden phrases, instead of only checking that the new ones appear.

D11 is not changed by this round, and no Hermes change is needed to close either blocker.

## D15 — the gate measures what it names

M-R3-6 listed four predicates that accepted wrong data and one self-test that reported success while failing.
The predicates are rewritten as named properties:

- `amount_statement(text, amount, unit, mark)` parses **one** statement: an optional sign (which must match the
  literal), the exact amount as a standalone token, a unit of the required kind, and the first citation after
  the amount inside the same line. `-380 pesos [99]` is not `380`, `380 kg` is not `380 pesos`, a mark that
  names another statement is not this amount's citation (M-R4-7) and a sign separated by a space is not the
  plain amount.
- `entry_for(entries, question, mode, turn_id)` selects the entry of the run, never by question alone; `main`
  resolves each run again by the `turn_id` its own entry recorded.
- Every block of every cited answer in the log is resolved against the **evidence table** its entry stores
  (call, `pid`, `uid`, number, document, section, position and the numbered lines), the whole block is
  compared against the delivered answer, and the seal is crossed with the entry's own delivery decision.
- `gate_selftest()` returns the exact list of failing fixtures (empty = pass), and the new counterexamples of
  this review are in it.
- `finish()` writes every artifact, then scans them on disk, then emits the verdict; the report is written
  before it is scanned and re-verified if it is rewritten. `delivered_of` is renamed
  `terminal_record_of` and its claim names its scope: it measures the terminal record of a documented
  stream-json consumer, not the temporary deliveries of a real CLI, desktop, bot or TTS.
