# H0 (round 2) — the delivery paths of a turn, read in the Hermes source

Read-only inspection of the installed checkout `C:\Users\Franc\AppData\Local\hermes\hermes-agent`
(commit `dce1e9b37581dd62e480a9064dc04a709c2940d3`, v0.21.6+387) on 2026-10-10. Nothing under the checkout
was written. Paths are relative to the checkout root.

This report answers the round 1 fact sheet where `transform_llm_output` is not enough: which channels can
deliver a draft before the verdict, and how each one is configured.

## 1. The stream hooks are observers and arrive late

| Fact | File:line |
|---|---|
| A registered hook callback gets its own bounded queue and worker; the queue drops the oldest pending event when full (`_QUEUE_SIZE = 1024`) | `agent/plugin_stream_hooks.py:1-7`, `:22`, `:42-57` |
| `enqueue_plugin_stream_hook` fans out; the aggregated return is discarded on the stream path | `agent/plugin_stream_hooks.py:133-145` |
| The callback's return value is ignored (`context.copy().run(dispatcher.callback, **payload)`) | `agent/plugin_stream_hooks.py:60-83` |
| The delta is delivered to the user first and the hook is enqueued after | `agent/stream_delivery.py:331-334` |
| `on_stream_start/delta/end` are in `VALID_HOOKS` | `hermes_cli/plugins.py:115`, registered by `hermes_cli/plugins.py:933-935` |

**Consequence:** a plugin cannot retain or transform a delta from these hooks. They are post-delivery
observers, and they can even lose events.

## 2. The single chokepoints of delivery

| Channel | File:line |
|---|---|
| Text: the one fan-out to display, gateway, SSE and streaming TTS, `agent/stream_delivery.py:35` (`results = [self._call_quietly(cb, text) for cb in (self.stream_delta_callback, self._stream_callback)]`, `:33-36`) | `agent/stream_delivery.py:33-36` |
| Text delivery call | `agent/stream_delivery.py:331` |
| Reasoning callback | `agent/stream_delivery.py:348` |
| Interim comments (`_deliver_interim`) | `agent/stream_delivery.py:182`, `:188-216` |
| `_has_stream_consumers()` | `agent/stream_delivery.py:368-377` |
| Gateway: `agent.stream_delta_callback = stream_delta_cb` | `gateway/run_turn_runner.py:1268` |
| Gateway deltas tee to messaging and streaming TTS | `gateway/run_turn_runner.py:966-978` |
| CLI: `stream_delta_callback=self._stream_delta if self.streaming_enabled else None` | `hermes_cli/cli_agent_setup_mixin.py:697-698` |
| CLI streaming TTS queue fed by every delta | `hermes_cli/cli_chat_turn_mixin.py:311-316`, `:372` |
| SSE: `stream_delta_callback=_on_delta, reasoning_callback=_on_reasoning, status_callback=_on_status` | `gateway/platforms/api_server_openai_routes.py:622-624` |
| SSE commentary | `gateway/platforms/api_server_openai_routes.py:1155-1163` |

## 3. The final transform runs after the stream

| Fact | File:line |
|---|---|
| "first non-empty string wins" | `agent/turn_finalizer.py:515-517` |
| Idempotent per `turn_id` | `agent/turn_finalizer.py:497-500` |
| Called before persistence, after the stream | `agent/turn_finalizer.py:480-494`, `:628`, `:632` |
| The persisted row is rewritten | `agent/turn_finalizer.py:263-276` |
| The gateway reconciles by editing the already-visible message | `gateway/run_turn.py:4089-4118` |
| `hermes -z` already nulls the delta callback and returns `final_response` | `hermes_cli/oneshot.py:585-603`, `:613` |
| `--quiet` nulls text, reasoning and tool-gen, then `--format stream-json` reattaches only the text emitter | `hermes_cli/cli_single_query.py:474-486`, `:550-552`; `hermes_cli/stream_json.py:46-51` |

## 4. The effective streaming configuration

| Fact | File:line |
|---|---|
| `streaming.enabled` is the master switch; `transport: off` also disables | `gateway/config.py:504-507`, `:520-533` |
| `enabled_for(override)`: an override only narrows; `None` follows the global | `gateway/config.py:509-515` |
| The gateway builds its streaming from the top-level `streaming` key | `gateway/config.py:813` |
| Per-platform resolution order: `display.platforms.<plat>.<key>` then `display.<key>` | `gateway/display_config.py:98-110` |
| `display.streaming` is CLI-only and is ignored by the gateway | `gateway/display_config.py:126-128` |
| The decision to emit messaging deltas | `gateway/run_turn_runner.py:925-931` |
| Documented defaults: telegram `true`, discord `false`, slack `false`, wecom `true` | `hermes_cli/config_defaults.py:955-965` |
| The gateway loader does **not** merge `DEFAULT_CONFIG` | `gateway/run.py:2866-2878` |
| CLI config default is `streaming: true` (`_cli_config_defaults`) | `hermes_cli/cli_config_load.py:210` |
| CLI reads it as `self.streaming_enabled = display.get("streaming", False)` | `hermes_cli/cli_init_mixin.py:64` |

**Measured:** with `streaming.enabled: true` and this installation's `config.yaml` (which has no
`display.platforms`), `enabled_for(None)` is true for **every** messaging platform, including Discord and
Slack whose documented defaults are false, because the gateway never materialises `DEFAULT_CONFIG`. The only
hard per-platform guarantee is an explicit `display.platforms.<platform>.streaming: false`. The real
`config.yaml` has `display.streaming: true`, so the interactive CLI streams by default even though the round
1 design note assumed `false`.

**Consequence for the plugin (D1/H9):** the plugin reads the same keys, withholds the seal on a messaging
surface whose effective streaming is on, keeps the seal on the CLI, and documents the CLI and desktop
limitations instead of promising something the host does not keep.

## 5. The SSE route is outside the gateway switch

| Fact | File:line |
|---|---|
| The API server runs its own agent lifecycle and does not go through `TurnRunner` | `gateway/platforms/api_server.py:4256-4260` |
| Its callbacks are wired unconditionally when `stream: true` | `gateway/platforms/api_server_openai_routes.py:622-624`, `:656`, `:1128` |
| `/v1/runs` wires its own text callback | `gateway/platforms/api_server_runs.py:962` |
| No file under `gateway/platforms/*.py` consults `streaming.enabled` or `enabled_for` | grep with no matches |

## 6. Why `python -m hermes_cited.verify_log` needs the installed directory

| Fact | File:line |
|---|---|
| A directory plugin is imported as `hermes_plugins.<slug>` (`-` becomes `_`) | `hermes_cli/plugins_loader.py:36`, `:679-688` |
| The plugin directory becomes the package search location; it never enters `sys.path` as a top-level package | `hermes_cli/plugins_loader.py:698-733` |
| `hermes_plugins` is a synthetic empty namespace | `hermes_cli/plugins_loader.py:707-711` |

**Consequence (M7):** the documented command must run with the current directory set to
`$HERMES_HOME/plugins/hermes-cited`, where `python -m` puts the plugin root on `sys.path` and the
`hermes_cited/` subpackage resolves.

## 7. Identity of a turn

| Fact | File:line |
|---|---|
| `turn_id = ... f"{agent.session_id or 'session'}:{effective_task_id}:{uuid4}"` | `agent/turn_context.py:586-590` |
| `pre_llm_call` payload | `agent/turn_context.py:804-816` |
| `post_tool_call` payload | `model_tools.py:645-655`, `:693-698` |

## 8. Points a delivery-policy hook would have to touch

The full list, with the change at each point, is in `docs/upstream-proposal.md`. It covers text, reasoning,
interim comments, streaming TTS, the SSE route and the post-persist reconciliation, and it is a proposal:
no pull request and no issue was opened in the upstream repository.
