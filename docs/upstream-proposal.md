# Proposal for Hermes Agent: a synchronous delivery contract and a final composition step

Status: design note for the Hermes Agent maintainers. **No pull request and no issue was opened by
this repository.** Franc (the owner of `RonnieGex/hermes-cited`) decides whether this is proposed
upstream.

Reader: someone who knows Hermes Agent v0.21.6+387 (commit `dce1e9b`) and its plugin API. Every line
number below was read in that checkout.

## What would activate the seal (D11)

Since round 6 the plugin **does not emit** the mark `Verified by Cited` on any route, because with
`dce1e9b` it cannot accredit what the host delivers. `delivery.accredited_delivery()` is the one
capability point; today it answers `False`. To turn it on, the host has to offer, per turn and to the
plugin, both halves of one contract:

1. **The effective policy of the turn.** Not a configuration file, not `load_config_readonly`: the
   receivers that are really connected for this turn — the text delta, the reasoning stream, the
   interim commentary, the voice and the SSE route — so the plugin can tell an accredited silent turn
   from a quiet-looking file. The `delivery_policy` hook of the first contract below is that half.
2. **The terminal message is the plugin's composition.** The text the user finally receives is the
   string the composition returned and nothing is appended after it (the file-mutation footer of
   `agent/turn_finalizer.py:645-647` can add text today), and the same string is the one persisted.
   The third contract below is that half.
3. **The reserved mark protected again.** Turning the seal on obliges whoever does it to protect the
   reserved mark again with the **render semantics of the host itself**, checked against the consumer that
   really reads the answer. Rounds 3 to 7 of this plugin showed that a hand-written reader of Markdown
   either opens a new evasion or deletes legitimate text, so protecting the mark again is a requirement of
   the activation and not an optional polish (D12 of the round 8 mission).

A future version of the plugin would set the capability point from the presence of both halves and
would emit the seal only for a turn the host accredits, and only with the reserved mark protected again as
above. This repository will ask for the seal back
only with a test of the real host that demonstrates the contract; until then the answer carries the
fixed note that names the retention.

## The three contracts Hermes does not offer today

1. **Synchronous retention of the delivery.** A plugin can replace the final answer
   (`transform_llm_output`), but it cannot stop the answer from being *delivered* while it is still
   being written: the draft reaches the screen, the messaging surface, the SSE route and streaming
   TTS before the verdict exists.
2. **A final composition step even when the model's response is empty.** The finalizer returns before
   the hook when the text is false, so a turn whose answer is empty is delivered empty and no plugin
   can compose it.
3. **A final composition boundary after the host's own footers.** `transform_llm_output` is not the
   last writer of the message: the real finalizer persists the row and can still append text after
   it (the file-mutation failure footer of `agent/turn_finalizer.py:645-647`), so the delivered final
   message can differ from the text the plugin composed and the record stored.

In a "cited" mode that promises that no unverified value reaches the user, these gaps are the
difference between a guarantee and a wish. The plugin's round 4 contract (D10 to D14), amended by D11,
states exactly what it can promise: for a cited turn that reaches the hook, the plugin's composition is the
documentary render, the fixed refusal or the operational refusal; the host may add text afterwards. The seal
is withheld on every surface where something else could have been seen.

## The problem

A verifier therefore runs too late: the user has
already seen the draft. Measured in `dce1e9b`, with a real agent object and a recording receiver:

- `agent/stream_delivery.py:331` delivers the delta (`delivered = self._deliver_to_stream_callbacks(text)`).
- `agent/stream_delivery.py:332` only then enqueues the observer hook (`on_stream_delta`).
- `agent/plugin_stream_hooks.py:60-83` ignores the callback's return value, and
  `agent/plugin_stream_hooks.py:42-57` drops the oldest event when the bounded queue (1024,
  `:22`) is full.
- The final transform runs in `agent/turn_finalizer.py:628`, before persistence but **after** the
  stream already showed the text; the "first non-empty string wins" rule is
  `agent/turn_finalizer.py:515-517`.

Hermes has no per-turn, plugin-visible policy that says "hold every outbound channel until a verdict".
The `on_stream_*` hooks are observers; `pre_llm_call` returns injected context, not a delivery
policy; `pre_api_request` does not consume a return value as an output policy.

## Proposal

Add a **delivery policy** that the host resolves once per turn, before the agent runs, from the
hooks a plugin already registers, and that retains every channel until the turn finalizer produces
its verdict.

### Contract

1. A new hook, `delivery_policy`, is invoked once at the start of a turn with the same identity
   payload as `pre_llm_call` (`session_id`, `turn_id`, `platform`, `model`, `task_id`) and returns
   either `None` (normal delivery) or a mapping:

   ```python
   {
       "hold_until_verdict": True,
       "channels": ("text", "reasoning", "interim", "voice"),
       "on_final": "replace",   # replace the held draft with the final text, or drop it
   }
   ```

2. While a policy is active, `agent/stream_delivery.py` buffers the deltas of the selected channels
   instead of calling their consumers. The single chokepoint already exists:
   - text: `agent/stream_delivery.py:35` (`stream_delta_callback` and `_stream_callback`),
   - reasoning: `agent/stream_delivery.py:348`,
   - interim comments: `agent/stream_delivery.py:182`.
   `_has_stream_consumers()` (`agent/stream_delivery.py:368-377`) must keep returning `True`, so the
   provider still streams and the buffer receives the text.
3. The verdict is the value `transform_llm_output` returns (or the untouched text). After it is
   known, the host flushes the buffer once: either the final text (replacing the draft) or nothing.
   TTS uses the same flushed text, never the held deltas
   (`gateway/run_turn_runner.py:966-978`, `hermes_cli/cli_chat_turn_mixin.py:311-316`).
4. On refusal, exception or cancellation the buffer is discarded and the refusal is delivered; the
   policy is released in a `finally` so the next turn is normal.
5. The policy is surfaced in the CLI's `--format stream-json` as a single terminal event, and the
   SSE route (`gateway/platforms/api_server_openai_routes.py`) honours it too, because that surface
   builds its own agent and never consults `streaming.enabled`
   (`gateway/platforms/api_server.py:4256-4260`).

### Points that must change

| # | File:line | What it is today | Change |
|---|---|---|---|
| 1 | `agent/stream_delivery.py:35` | The one fan-out of text deltas to display, gateway, SSE and streaming TTS | Route through the per-turn buffer when a policy is active |
| 2 | `agent/stream_delivery.py:331-334` | Deliver, then record what was delivered | Deliver after the verdict; keep `_record_streamed_assistant_text` for the flushed text |
| 3 | `agent/stream_delivery.py:348` | Reasoning callback | Buffer reasoning |
| 4 | `agent/stream_delivery.py:182` | `_deliver_interim` | Buffer interim comments |
| 5 | `agent/stream_delivery.py:368-377` | `_has_stream_consumers` | Keep `True` while holding, so the provider streams into the buffer |
| 6 | `agent/turn_finalizer.py:628` | `apply_llm_output_transform` before `_persist_session` | Flush or drop the buffer with the verdict |
| 7 | `agent/turn_finalizer.py:273` | `_tail["content"] = final_response` | The persisted row and the delivered text must agree |
| 8 | `agent/turn_finalizer.py:645-647` | Footer and abnormal-exit text added after persistence | Rethink so delivery and persistence stay equal |
| 9 | `gateway/run_turn_runner.py:1268` | `agent.stream_delta_callback = stream_delta_cb` | Respect the policy at the source |
| 10 | `gateway/run_turn_runner.py:966-978` | Deltas tee to messaging and streaming TTS | The same held text for both |
| 11 | `gateway/run_turn_runner.py:983-988` | Interim comment spoken by TTS | Hold with the other channels |
| 12 | `hermes_cli/cli_agent_setup_mixin.py:697` | CLI delta callback when `display.streaming` | Respect the policy |
| 13 | `hermes_cli/cli_chat_turn_mixin.py:311-316, 372` | Streaming TTS queue fed by every delta | Feed the flushed text |
| 14 | `gateway/platforms/api_server_openai_routes.py:622-624` | SSE wires text, reasoning and status unconditionally | Respect the policy (the surface has no other switch) |
| 15 | `gateway/platforms/api_server_openai_routes.py:1155-1163` | `/v1/responses` commentary | Hold commentary |
| 16 | `hermes_cli/oneshot.py:600-603` | `-z` already nulls the delta callback | This is the existing route that already behaves correctly |

Also relevant: `agent/chat_completion_helpers.py:2908, 3302, 3674, 3958`,
`agent/turn_tool_round.py:159-161, 186-189` and `agent/codex_runtime.py:1190` emit text outside
`_fire_stream_delta`; they need the same buffer.

## The second contract: compose the final answer even when the model's text is empty

`agent/turn_finalizer.py:501-502` returns before invoking any hook when ``final_response`` is false:

```python
    if not final_response:
        return final_response, False, None
```

The same early return is reached from the two call sites of the finalizer
(`agent/turn_finalizer.py:628` and `:655`). A cited-mode turn whose model answer is empty is therefore
delivered empty: the plugin's `transform_llm_output` never runs, it cannot compose the render of the
chosen lines and it cannot write the row of that answer. That is not "covered by a fallback": the
plugin cannot see the turn at all.

### The three contracts, in one line each

- **Synchronous retention of the delivery**: hold every outbound channel of the turn (text, reasoning,
  commentary and voice) until the finalizer produces its verdict, and release it then.
- **A final composition step even when the model's response is empty**: call the output hooks once with an
  empty text so the plugin can compose the answer, instead of returning before the hooks.
- **A final composition boundary after the host's footers**: compose cited after every footer or explanation
  the host adds (`agent/turn_finalizer.py:645-647`) and before the terminal delivery, so the persisted render
  and the final message cannot diverge.

### Proposal

A cited-mode plugin has already declared, at the start of the turn, that it wants to compose the
answer (`pre_llm_call` returned its context). Give that a consequence:

1. Add to the delivery policy of the first contract a flag
   ``compose_on_empty: True``, resolved once per turn.
2. When the turn ends with an empty or whitespace-only ``final_response`` and the flag is set, call
   the output hooks **once** with ``response_text=""``, before persisting and before delivering, and
   use the returned string as the final answer. The hook is then the only composer, exactly as it is
   for a non-empty turn.
3. Keep the call idempotent per ``turn_id`` (the guard at `agent/turn_finalizer.py:497-500`) so a
   recovery path that also calls the finalizer cannot compose twice.
4. A hook that raises leaves the empty text untouched and the incident reaches the same diagnostic a
   failing hook reaches today (`agent/turn_finalizer.py:104-111`); the host keeps working.
5. Surface the outcome in ``--format stream-json`` and in the SSE route, so a consumer can tell an
   empty model answer from a composed one.

Until that exists, `hermes-cited` declares the incompatibility: the README and the delivery report say
that a cited turn with an empty model answer is delivered empty, with no render, no seal and no row,
because the plugin is never asked.

## The third contract: compose cited after every host footer

`transform_llm_output` is not the last writer of the message. In the pinned host the finalizer applies the
transform at `agent/turn_finalizer.py:628`, persists the row, and only then appends its own text: the footer
of the file mutations that failed (`agent/turn_finalizer.py:645-647`, through the formatter of
`agent/turn_explainers.py:211`) and the output hooks. A cited render that the plugin composed and persisted
(`stored`) can therefore differ from the message the user finally receives (`final`): `stored != final`. The
addition is text of the final message, not voice and not interim commentary, and a second call of the
transformer is idempotent: it does not compose the render again.

The plugin cannot close that gap from its own hook, because the extra text is written by the host after the
hook returns. A cited turn on a host path that can append a footer is not a path where the render contract
holds, and `hermes-cited` does not publish it as one.

### Proposal

Run the composition of a cited turn after every footer or explanation the host adds and before the terminal
delivery, so the text that is persisted, the text that is delivered and the text the record carries are the
same string. Concretely: apply the output transform after `_append_file_mutation_footer` and the other late
writers, and let the string the transform returns be the text that is finally delivered. The integration test
of the full finalizer should cover that sequence, not only `apply_llm_output_transform`.

## What `hermes-cited` does meanwhile

Until these contracts exist, the plugin enforces what it can and says what it cannot: the three missing
contracts are **synchronous retention of the delivery**, **a final composition step even when the model's
response is empty**, and **a final composition boundary after the host's own footers**, so the final message
cannot differ from the persisted render. Because none of them exists, the seal is **not emitted**: the one
capability point of D11 answers "not accredited" and the answer says so with the fixed note.

- **The seal waits for the host**: `delivery.accredited_delivery()` is the only place that would turn the
  mark back on, and it needs both halves of the contract above. While it answers `False`, every cited answer
  is the plugin's composition plus the fixed note that names the retention.
- **Every surface whose text it cannot retain**: the plugin takes a snapshot of the effective delivery
  configuration at the **start** of the cited turn and withholds the seal when anything else could
  have been seen. In round 6 that covers `api_server` (the SSE route of the desktop app), `desktop`,
  any messaging platform whose streaming is on, interim assistant commentary
  (`display.interim_assistant_messages`), streaming TTS (`tts.auto_tts`), an unknown platform, a
  configuration it cannot read and the regular case in which the host simply does not accredit the
  delivery. The withheld note names the surface and the switch, or the missing accreditation.
- **CLI**: the streaming consumer is documented (`--format stream-json` shows only the terminal
  `result` record), and `display.streaming: false` plus
  `display.interim_assistant_messages: false` remove the draft entirely.
- **Empty responses**: declared as the host incompatibility above, with the integration test that
  proves it (`tests/test_host.py`).
- **Footers after the transform**: the plugin declares that the delivered message can differ from the
  persisted render when the host appends its own text (`agent/turn_finalizer.py:645-647`), and it does not
  publish the render guarantee for those paths until the host hands the terminal text to the composition.
- **Dot mode passes the text through (D12)**: nothing in dot mode is verified, whatever the text says. This
  version of the plugin writes no seal, so the phrase `Verified by Cited` in an answer never comes from the
  plugin, and the row records exactly the text that is delivered. The protection of the reserved mark
  returns with the activation of the seal, as the third requirement above states.
- The composition of cited mode is what the plugin writes: for a cited turn that reaches the hook, it is the
  documentary render, the fixed refusal or the operational refusal; the host may add text afterwards.

## Configuration reference used by the plugin

```yaml
# $HERMES_HOME/config.yaml — the gateway
streaming:
  enabled: false                 # master switch; transport: off also disables
display:
  platforms:
    telegram:
      streaming: false           # narrow only; never enables on its own
```

`display.streaming` is CLI-only (`gateway/display_config.py:126-128`). The gateway resolves
`display.platforms.<platform>.streaming` first (`gateway/display_config.py:98-110`) and then
`StreamingConfig.enabled_for` (`gateway/config.py:509-515`).
