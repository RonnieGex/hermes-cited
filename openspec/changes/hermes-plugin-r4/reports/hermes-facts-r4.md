# The facts of round 4, with their file and line

Date: 2026-10-10. Host: Hermes Agent v0.21.6+387, commit `dce1e9b37581dd62e480a9064dc04a709c2940d3`, read in the
read-only public copy of the review (`host-fast/hermes-agent-dce1e9b…`). The installed tree under
`C:\Users\Franc\AppData\Local\hermes\hermes-agent` was only read, with the same commit; nothing was written
under the real home, no gateway, bot or `hermes update` was run, and every execution used a temporary
`HERMES_HOME`.

The round 3 report (`openspec/changes/hermes-plugin-r3/reports/hermes-facts-r3.md`) still describes the
`StreamingConfig` resolver and the tool dispatch, and those facts did not change. This report records the
facts round 4 depends on and corrects the one the third review found wrong.

## M-R3-4 — the surfaces the host does not retain

- `gateway/platforms/api_server.py:2394` builds the API agent with `platform="api_server"`, and
  `gateway/platforms/api_server_openai_routes.py:241` (`self.transformed_final`) replaces the streamed
  deltas with a non-append transform. There is no configuration switch that reaches that route.
  **Correction of round 3:** `api_server` is *not* an exception; it is the SSE route of the desktop app and
  it withholds the seal (D13). The cycle `_stream_and_finalize` keeps the initial baseline and re-emits the
  transformed final answer, which is why the review's second conclusion — a replacement at the very end does
  not erase what was already seen — stands.
- `gateway/run_turn_runner.py:917-994` (`_setup_stream_consumer`) builds the delta sinks: the gateway stream
  consumer when `scfg.enabled_for(platform_override)` (`:931`) **or** `ctx.interim_assistant_messages_enabled`
  (`:932`), plus the streaming TTS consumer from `ctx.streaming_tts_consumer_holder[0]` (`:924`). The deltas
  are delivered before the transform runs.
- `gateway/run_turn_runner.py:980-992` (`interim_assistant_cb`): commentary reaches `stts.on_delta` and
  `stream_consumer.on_commentary`, so commentary is a delivery of its own, independent of text streaming.
- `gateway/run_turn.py:3014-3016` resolves `interim_assistant_messages` and turns it into
  `interim_assistant_messages_enabled = not is_webhook and mode != "off"`.
- `gateway/display_config.py:11-35` (`_GLOBAL_DEFAULTS`) and `:39-70` (`_TIER_*`, `_PLATFORM_DEFAULTS`): the
  resolution order is `display.platforms.<p>.<key>` → `display.<key>` → platform default → global default.
  `interim_assistant_messages` defaults to `True` globally and in the HIGH/MEDIUM tiers, and to `False` in
  the LOW/MINIMAL tiers (`signal`, `whatsapp_cloud`, `photon`, `bluebubbles`, `weixin`, `wecom`,
  `wecom_callback`, `dingtalk`, `qqbot`). The plugin pins that table in `delivery.INTERIM_DEFAULTS`.
- `gateway/run_turn.py:3227-3258` (`_run_agent_start_streaming_tts`): streaming TTS needs a voice input, an
  auto-TTS chat and a streaming provider; the gate is `_load_tts_config()` and
  `hermes_cli/config_defaults.py:1231` (`auto_tts: False`). The plugin reads `tts.auto_tts` and withholds
  when it is on.
- `hermes_cli/config_defaults.py:919` and `gateway/display_config.py:24`: `interim_assistant_messages: True`
  is the default, so "no commentary" has to be proven, not assumed. That is why `delivery.snapshot` grants
  the seal only when the snapshot affirmatively shows that nothing else can have been seen.

## M-R3-5 — the empty response never reaches the hook

- `agent/turn_finalizer.py:501-502`:

  ```python
      if not final_response:
          return final_response, False, None
  ```

  The early return is inside `apply_llm_output_transform` (`:480`), so with an empty ``final_response`` the
  hook is not invoked at all and `transformed` stays `False`.
- The two call sites that reach it are `agent/turn_finalizer.py:628` (`_persist_step`, the recovery path,
  guarded by `if final_response and not interrupted`) and `:655` (`_apply_output_hooks`, also guarded by
  `if final_response and not interrupted`). Both guards mean a cited turn with an empty answer is delivered
  empty and the plugin cannot compose it.
- `agent/turn_finalizer.py:104-111` (`_invoke_hook_safely`) logs a failing hook and returns `[]`, and
  `hermes_cli/lifecycle.py:26-29` composes the first-party observers with the plugin hooks. That is the
  dispatcher the review used to show that an exception before the append leaves the model's prose in place
  (B-R3-1); with the boundary of D10 the hook always returns one of the three answers.

## A note on the reported line numbers

The line numbers above are of `dce1e9b`. `docs/upstream-proposal.md` cites `agent/turn_finalizer.py:628` and
`:515-517` for the round 3 behaviour and `:501` for the empty response; they are the same functions, read in
the same checkout.
