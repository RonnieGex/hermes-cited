# Context

Round 1 of `hermes-plugin` closed with `GATE: GREEN` (25 of 25 claims) and the independent adversarial
review of Codex (`tasks/revision-codex-hermes-cited.md`) returned **CAMBIOS**: three Blockers, seven Majors
and one Minor. The mission `tasks/mision-cited-hermes-r2.md` fixes the resolution with four design decisions,
D1 to D4, which take precedence over the literal fix the review proposes. Every fact this design depends on,
with file and line, is in `reports/hermes-facts-r2.md` (delivery paths) and in the round 1
`hermes-facts.md` (plugin API). The reviewed objects are those of the review: plugin
`a1ba1540cdb0dd0b5564ea8b5091e2aa98610ac4` (HEAD `afccfa8` adds only `LOOP_STATE.md`).

# Goals / Non-Goals

Goals: no unverified value can be *presented* as verified; the verifier's evidence is only what Cited
returned in the turn; the bearer never leaves the configured origin; the log survives two writers and
detects a removed tail; an answer without a record is never sealed; the gate proves the property it names;
the documentation claims only what was verified.

Non-goals: a host change in Hermes (proposed, not done); a message-channel bot (no real bot is run);
computed totals (next mission); any write under the real `HERMES_HOME`; any push.

# Decisions

**D1 — the delivery policy is explicit and enforced where it can be (B1).** Hermes delivers every text
delta at `agent/stream_delivery.py:35` and only then enqueues the observer hook (`:331-332`), and the final
transform runs afterwards (`agent/turn_finalizer.py:628`). No plugin hook can retain a delta. The plugin
therefore reads the effective streaming configuration of the run — `streaming.enabled` plus
`display.platforms.<platform>.streaming` for the gateway, `display.streaming` for the CLI — and on a
**messaging** surface whose streaming is on it withholds the seal and says so in the answer. The CLI keeps
the seal; `--format stream-json` reattaches the text emitter (`hermes_cli/stream_json.py:46-51`), so the
READMEs require a consumer of that format to show only the terminal `result` record. The desktop app wires
its own SSE stream, outside the gateway switch (`gateway/platforms/api_server.py:4256-4260`), so its README
says plainly that a draft may be visible. `docs/upstream-proposal.md` specifies the per-turn delivery-policy
hook, with the file and line of every point it would touch. No PR and no issue upstream.

Note against the round 1 fact sheet: the CLI default is `streaming: true` in `_cli_config_defaults()`
(`hermes_cli/cli_config_load.py:210`) and this installation has `display.streaming: true`; the round 1 note
assumed `false`. The READMEs state the real default and the consumer rule, and the delivery report records
the correction.

**D2 — cited mode is extractive (B2, M1).** The verifier stops comparing loose tokens. It splits the
response into segments (sentence or line), splits quoted from free text, and for every segment that carries
a datum (a digit, a currency symbol or word, or a written numeral) it requires the segment to appear
verbatim — after NFKC, accents off, case-folded, whitespace collapsed and digit-group spaces merged on both
sides — inside a non-empty `passages[].excerpt` or `citations[].excerpt` of the turn, and inside `« »`.
Free text may not carry a datum. Citation marks `[n]` are removed before the check and validated separately
against the turn's citation map. The query, the generated `cited_ask` answer, the headings, the positions,
the counts and the transport text are never evidence; zero excerpts means no seal. A `status: refused`
becomes an explicit refusal. This subsumes M1: a changed sign, currency, date, code, numeral word, unit,
superscript or swapped subject is refused because the segment is not verbatim, while fullwidth digits and a
narrow no-break space used as a thousands separator are still accepted because the normalisation is applied
to both sides. An ambiguous `1.200`/`1,200` is literal, as the review asks. Calculations stay out.

**D3 — the log is anchored in custody (M4).** The log gains `seq` and a `log_id`; the append holds an
exclusive inter-process lock over `<log>.lock` around reading and validating the tail, hashing, appending
and flushing (`M3`); and after each append an HMAC-authenticated checkpoint of the count, the final hash and
the log identity is rewritten atomically. Its key lives **outside `HERMES_HOME`**, at
`%APPDATA%\Katalis\hermes-cited\audit.key` by default (`CITED_AUDIT_KEY_PATH` overrides it for tests and
for the gate) and is never the Cited bearer. The verifier requires the checkpoint, so a removed last entry,
a cut suffix, a rewritten and recomputed chain and a rolled-back checkpoint all fail. The README states the
exact scope: a change by someone without the key is detected; rolling back log and checkpoint together needs
the remote custody that Cited Ledger will bring.

**D4 — the rest exactly as the review asks.** B3: a private opener whose redirect handler refuses every
`3xx` before a second request, so the bearer never leaves the configured origin, with no global opener
installed. M2: the client rejects, redacted, any response that reflects the token in any string (success or
error), and every field of the audit entry is redacted recursively before hashing. M5/H10: the session and
the turn identifier are written, the schema is validated before hashing and at verification, and a failed
append becomes an operational refusal without a seal; the turn state is dropped only after the append
result is known. M6: `scripts/gate.py` is rewritten so every claim asserts the property it names, with
adversarial fixtures, exact entry counting, digest recomputation from the stored excerpt text, an explicit
allow-list of discovery tools before Cited, and redaction of every artifact before it is written. M7: the
audit command is documented and tested from the installed plugin directory, outside the checkout. m1: both
READMEs, the skill, the Cited docs and the change status are corrected to claim only the verified facts,
and the round 1 reports move inside their change.

# Risks / Trade-offs

- The extractive rule is strict: a model that answers with the right value in its own words is refused. That
  is the point of D2, and the injected rules and the skill give the exact `« »` format with a worked
  example. The refusal names the segment so the next turn can copy it.
- Withholding the seal on a streaming messaging surface means those answers are verified but unsealed. The
  note names the exact configuration to fix it, and the alternative — sealing an answer whose draft was
  already visible — is the defect B1.
- The checkpoint can be rolled back together with the log by an actor with write access to both files. No
  local scheme can detect that; the README states the limit instead of overclaiming, and remote custody is
  the next step.
- Verifying the whole chain on every append is O(n) per append. The gate's logs are tiny and correctness is
  worth more than the linear read here.
