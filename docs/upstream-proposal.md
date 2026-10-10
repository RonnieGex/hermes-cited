# Proposal for Hermes Agent: a per-turn delivery policy

Status: design note for the Hermes Agent maintainers. **No pull request and no issue was opened by
this repository.** Franc (the owner of `RonnieGex/hermes-cited`) decides whether this is proposed
upstream.

Reader: someone who knows Hermes Agent v0.21.6+387 (commit `dce1e9b`) and its plugin API. Every line
number below was read in that checkout.

## The problem

A plugin can replace the final answer (`transform_llm_output`), but it cannot stop the answer from
being *delivered* while it is still being written. A verifier therefore runs too late: the user has
already seen the draft. In a "cited" mode that promises that no unverified value reaches the user,
that gap is the difference between a guarantee and a wish.

Measured in `dce1e9b`, with a real agent object and a recording receiver:

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

### Why a hook and not a plugin

The plugin cannot reach any of the points above: `ctx.register_hook` accepts observer names only, the
stream hooks are asynchronous and lossy, and the finalizer's return contract has no hold. A plugin
that claimed "the user never sees the draft" without this change would be making a promise the host
does not keep.

## What `hermes-cited` does meanwhile

Until this policy exists, the plugin enforces what it can and says what it cannot:

- **Messaging** (Telegram, Slack, Discord and the rest): the plugin reads the effective
  configuration (`streaming.enabled` plus `display.platforms.<platform>.streaming`) and, when
  streaming is on, withholds the seal and tells the user why.
- **CLI**: the streaming consumer is documented (`--format stream-json` shows only the terminal
  `result` record), and `display.streaming: false` removes the draft entirely.
- **Desktop**: the app wires its own SSE stream; the README says plainly that a draft may be visible
  while the answer is written.

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
