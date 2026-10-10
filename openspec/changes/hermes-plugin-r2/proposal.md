# Why

The round 1 change `hermes-plugin` closed with `GATE: GREEN`, but the independent adversarial review
(`tasks/revision-codex-hermes-cited.md`, verdict **CAMBIOS**) found three Blockers, seven Majors and one Minor
that the historical gate could not see. Franc asked for round 2 in `tasks/mision-cited-hermes-r2.md`: resolve
every finding, with the design decisions D1 to D4 of that mission taking precedence over what the review
proposes.

The three Blockers are the product risks:

- **B1** — Hermes hands every text delta to the screen/TTS before `transform_llm_output` decides, so the user can
  see an unverified draft even when the final answer is refused.
- **B2** — the verifier's corpus included the transport text, the query echo and the `cited_ask` answer, so a turn
  with zero passages could verify its own invented datum.
- **B3** — `urllib.request.urlopen` follows redirects, so a `302` from the configured origin re-sent the bearer to
  a different origin.

# What Changes

- **D1 (B1).** The plugin states and checks the delivery policy it can actually enforce: cited mode requires
  streaming off per platform. The effective configuration is read at load and per turn; on a messaging surface
  whose streaming is on, the seal is withheld and the answer says why. The READMEs document the exact YAML, the
  CLI `--format stream-json` consumer rule and the desktop limitation. `docs/upstream-proposal.md` (English)
  specifies the per-turn delivery-policy hook Hermes would need, with file and line of every point it touches.
  No PR and no issue is opened in the upstream repository.
- **D2 (B2, M1).** Cited mode becomes extractive: every response segment (sentence or line) that carries a datum
  (number, unit, currency, date, code) must appear verbatim, after Unicode and whitespace normalisation on both
  sides, inside an excerpt Cited returned in that same turn. The evidence is only `passages[].excerpt` and
  `citations[].excerpt`; the query, the `cited_ask` answer, headings, counts and transport text are never
  evidence. Free text outside `« »` cannot carry a datum. Citation marks `[n]` are validated separately against
  the turn's citation map. A `refused` of `cited_ask` becomes an explicit refusal. Calculations stay out.
- **D3 (M4).** The log gains `seq` and a log identity, and its count and final hash are anchored in an
  HMAC-authenticated checkpoint whose key lives outside `HERMES_HOME`
  (`%APPDATA%\Katalis\hermes-cited\audit.key`). The verifier requires the checkpoint and detects a removed
  entry, a cut suffix, a rewritten and recomputed chain, and a log that no longer matches its checkpoint.
- **D4 (B3, M2, M3, M5, M6, M7, m1).** Exactly as the review proposes, each with its adversarial test: a private
  opener that refuses every redirect before a second request; reflection of the token rejected in success and
  error paths and redacted in every audit field; an exclusive inter-process lock around the append; the session
  and turn identifiers written, the schema validated before hashing and at verification, and a persistence
  failure turned into an operational refusal without a seal; a gate whose predicates match the properties they
  name; and the audit command documented and tested from the installed plugin, outside the checkout.
- **m1.** The documentation and the change status are corrected to claim only what was verified: the
  singular/plural claim, the absolute "the real home was never used", the ownership of the plugin repository,
  the plugin-only commands in the skill, the sealed wording, the historical timings, the report location inside
  the change, and the pending CI and independent review.

# Impact

`hermes-cited`: the plugin package, the unit suite, `scripts/gate.py`, both READMEs, the packaged skill, the new
`docs/upstream-proposal.md`, and a new OpenSpec change `hermes-plugin-r2` with its `reports/`. The round 1 change
`hermes-plugin` keeps its spec and gets its reports moved under `openspec/changes/hermes-plugin/reports/`.

`community-hermes` (worktree, branch `docs/hermes-agent`): `git merge origin/main` (the merged PR #21) and
documentation only in `docs/mcp.md`, `README.md` and `README.es.md`.

No product code, no graphics, no landing, no deploy, no push, no archive of a change, and not one byte written
under `%LOCALAPPDATA%\hermes` or `~/.hermes`.
