# The facts of round 3, with their file and line

Date: 2026-10-10. Host: the installed Hermes Agent v0.21.6+387, commit `dce1e9b37581dd62e480a9064dc04a709c2940d3`,
read in `C:\Users\Franc\AppData\Local\hermes\hermes-agent`. Nothing here was written under the real home
and no gateway, bot or `hermes update` was run.

## D7 — the delivery resolver

- `gateway/config.py:486` `@dataclass StreamingConfig` with `enabled: bool = False` and
  `transport: str = "auto"`.
- `gateway/config.py:504` `globally_enabled`: `bool(self.enabled) and self.transport != "off"`.
- `gateway/config.py:509` `enabled_for(platform_override)`: `globally_enabled and (override is None or
  bool(override))`; a per-platform value can only narrow.
- `gateway/config.py:521` `from_dict`: `mode` is a transport alias that also implies `enabled`; an
  explicit `enabled` wins; a bare `transport` does not imply enabled.
- `gateway/config.py:93` `_normalize_transport_token`: YAML 1.1 parses bare `on`/`off` as booleans, so a
  boolean maps to `"auto"`/`"off"`; anything else lower-cases with `"auto"` as the default.
- `gateway/config.py:36` `_coerce_bool`: bool-ish strings (`true`/`yes`/`on`, `false`/`no`/`off`).
- `gateway/config.py:217` `class Platform(Enum)`: the release admits `wecom`, `wecom_callback`,
  `feishu`, `dingtalk`, `qqbot`, `weixin`, `whatsapp_cloud`, `bluebubbles`, `yuanbao`, `relay`,
  `api_server`, `webhook`, `msgraph_webhook` and `local`, besides the ones round 1 listed.
- `gateway/platforms/api_server_openai_routes.py:241` `self.transformed_final`: the SSE route replaces
  the deltas with a non-append transform, which is why `api_server` keeps its documented exception.

The compatibility copy of the plugin is pinned to those lines and is used only when the import of
`gateway.config` fails; the gate asserts that inside the Hermes venv the plugin uses the real class.

## D5 — the tool dispatch and the output hook

- `tools/registry.py:904` `_kwargs_accepted_by`: a native tool handler receives only the keyword
  arguments its signature declares.
- `model_tools.py:826` `dispatch_kwargs = {"task_id": ..., "session_id": ...}`: a handler sees the
  `session_id`, so `cited_quote` can find the turn of its session.
- `model_tools.py:695` the `post_tool_call` hook also receives `turn_id`, which is how the turn learns
  what `cited_search` returned.
- `agent/turn_finalizer.py:507` `apply_llm_output_transform`: `transform_llm_output` receives
  `response_text`, `session_id`, `model`, `platform` and `turn_id`; the first non-empty string wins and
  replaces the final text before it is persisted.

## D6 — the persistence path

- `hermes_cli/plugins.py:1972` the plugin contract of the hooks; the plugin holds its own exclusive lock
  over `<log>.lock` for the append.
- The custody of the checkpoint is the plugin's own: the key at `%APPDATA%\Katalis\hermes-cited\audit.key`
  by default, the high-water mark next to it, and `CITED_AUDIT_KEY_PATH` inside `HERMES_HOME` rejected.
