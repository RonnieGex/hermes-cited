# Context

Hermes Agent v0.21.6+387 (commit `dce1e9b`) is installed natively on Windows. Its plugin API is
`hermes_cli/plugins.py` (`PluginContext`), its hook allow-list is `VALID_HOOKS` in the same file, and its tool
registry is `tools/registry.py`. The verified facts this design depends on, with file and line, are in
`reports/hermes-facts.md`; the ones that decide the shape of the change are:

1. `transform_llm_output` may return a replacement string, and the first non-empty string returned by any subscriber
   replaces the final answer *before* it is persisted and shown (`agent/turn_finalizer.py:480-519`). Therefore the
   cited-mode verifier is not simulated: it really can refuse in place of the model.
2. `pre_llm_call` returns `{"context": ...}` (or a string) which is appended to the user message
   (`agent/turn_context.py:793-847`). That is where the strict cited-mode rules are injected.
3. `post_tool_call` receives `tool_name`, `args`, `result`, `session_id`, `turn_id`, `tool_call_id`
   (`model_tools.py:676-700`). That is how the verifier learns which passages Cited returned in the current turn.
4. Plugin slash commands run on the CLI (`cli.py:1276-1287`) and on the gateway
   (`gateway/run_inbound.py:1081-1102`). The gateway binds the session environment around the handler, the CLI does
   not, so mode state is resolved per session when a session key exists and per profile otherwise.
5. A plugin is installed from a local path with the `file://` scheme (`hermes_cli/plugins_cmd.py:294-330`), and
   `hermes plugins install <owner/repo>` is the published form.
6. `requires_toolsets` in a skill's frontmatter is satisfied by a plugin toolset, because the prompt builder derives
   the available toolsets from every registered tool name (`agent/system_prompt.py:301-314`). For a plugin skill the
   offer-time gate reads the frontmatter dict passed to `ctx.register_skill`, so the plugin passes it explicitly.

# Goals / Non-Goals

Goals: one-step installation, two honest routes (MCP and plugin), two modes with a deterministic refusal path, a
hash-chained log that proves what was answered and from which passage, and evidence for every claim.

Non-goals: a message-channel scene (Telegram/Slack, waiting on Franc's bot); quotations or invoices with code-set
prices (next mission); any write to Cited; any language-model call inside the plugin; any change to the visual
identity of Cited or its landing.

# Decisions

**Native tools, not MCP, for the plugin path.** The plugin registers its own tools so that installation is one step
and so that `post_tool_call` can see every result for the verifier and the log. The MCP route stays documented and
verified because it needs no installation at all.

**Two independent components.** `hermes_cited/client.py` speaks JSON-RPC to `/api/mcp` and knows nothing about
Hermes; `hermes_cited/plugin.py` adapts it to the registry. The client is exercised against a fake HTTP server in the
unit suite, so no test needs the network.

**Mode state.** `/cited` and `/dot` write to `ctx.state` (profile-scoped durable JSON). The key is the session key
when the surface exposes one, otherwise a single profile-level key. Resolution order for a turn: session entry, then
profile entry, then `CITED_DEFAULT_MODE`, then `dot`. This fails safe: an unknown state reads as `dot`, and the
cited-mode seal only ever appears when the mode was explicitly cited.

**The verifier is deterministic and bounded.** It extracts numbers, units, prices and codes from the final text with
regular expressions and checks each one against the concatenation of the excerpts Cited returned in that turn,
after normalizing thousands separators, accents, case and English/Spanish singular-plural pairs. It never calls a
model and never consults the question. A turn with no Cited result at all in cited mode cannot pass.

**One log entry per response.** The entry is appended in `transform_llm_output`, which is the single point that sees
the final text and the mode. Cited-mode entries carry the verifier outcome and the excerpt digests; dot-mode entries
carry the same schema with the verifier marked as not applied, so the log answers "what was said, in which mode".
The chain is `hash = sha256(prev_hash + canonical_json(entry))`, so removing, editing or reordering an entry breaks
verification.

**Failure is a value, not an exception.** A missing configuration, a `401`, a `403`, a `404`, a timeout and a network
failure all become a short sentence that names what is wrong and what to do; the tool returns that sentence and
Hermes keeps working.

# Risks / Trade-offs

- The verifier is strict by construction: a restated quantity that the documents do not contain turns the answer into
  a refusal. That is the requested behavior in cited mode, and the `cited` skill tells the model not to restate
  numbers that are not in a passage.
- Logging dot-mode turns means a session with no Cited call still appends an entry. The schema records
  `verificador.applied = false`, so nothing claims verification that did not happen.
- `transform_llm_output` is idempotent per `turn_id`; the plugin therefore keys its per-turn buffer by
  `(session_id, turn_id)` and falls back to the newest buffer of the session when a caller omits `turn_id`.
