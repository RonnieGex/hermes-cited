# H0 — Hermes Agent facts re-read in the source (fact sheet)

Read-only source inspection of the installed checkout `C:\Users\Franc\AppData\Local\hermes\hermes-agent`.

| Item | Value | Where verified |
|---|---|---|
| Commit | `dce1e9b37581dd62e480a9064dc04a709c2940d3` | `install-stamp.json` `commit` |
| Version | `v0.21.6+387.gdce1e9b` (base `0.21.6`, distance 387, branch `main`, `dirty: false`) | `install-stamp.json` `displayVersion` |
| Python | 3.11.15 (its own `venv\Scripts\python.exe`) | `venv\Scripts\python.exe --version` |
| Date of inspection | 2026-10-09 | — |

Every line number below was re-opened in **this** checkout. Paths are relative to the checkout root. This report
replaces the one written against `c9a99993` (`v0.21.6+333`): facts whose line numbers moved are marked
**(CHANGED)**; facts from the old report that could not be re-confirmed are listed in the last section.

Nothing under `%LOCALAPPDATA%\hermes` was written. No `git` command was run. The real `HERMES_HOME` was never
pointed at, and no Hermes process was executed against it.

---

## 1. Plugin discovery and registration

### 1.1 Directory plugins under `$HERMES_HOME/plugins/<name>/`

| Fact | File:line |
|---|---|
| A directory plugin is `plugin.yaml` (or `plugin.yml`, or portable `plugin.json`) + an `__init__.py` exposing `register(ctx)` | `hermes_cli/plugins.py:1-9` (module docstring: "A directory plugin needs a `plugin.yaml` manifest and an `__init__.py` exposing `register(ctx)`"); `plugins/plugin_loader.py:91-104` (`iter_plugin_dirs` requires `__init__.py`); `hermes_cli/plugins_loader.py:698-733` (`_load_directory_module`, raises `FileNotFoundError` when `__init__.py` is missing, `:704-706`) |
| The user plugin root is `$HERMES_HOME/plugins` | `hermes_cli/plugins_discovery.py:209-211` (`user_dir = get_hermes_home() / "plugins"`); helper `plugins/plugin_loader.py:81-88` (`user_plugins_dir`) |
| Scan shape: flat `<root>/<name>/plugin.yaml` (key `name`) or category `<root>/<cat>/<name>/plugin.yaml` (key `cat/name`); manifest-less directories recurse exactly one level | `hermes_cli/plugins_discovery.py:134-186` (`scan_directory`), depth cap `:181-185` |
| Discovery order: bundled (excluded categories listed) → user → project (opt-in `HERMES_ENABLE_PROJECT_PLUGINS=1`) → entry points | `hermes_cli/plugins_discovery.py:189-218`; `hermes_cli/plugins.py:1397-1408` |
| Bundled top-level categories excluded from the general scanner: `memory`, `context_engine`, `model-providers`, `cron_providers`, `computer_use` | `hermes_cli/plugins_discovery.py:207-208` |
| Later source wins on key collision (project > user > bundled); a flat impostor claiming a *bundled* key from a differently named directory is skipped | `hermes_cli/plugins_discovery.py:221-244` (`resolve_manifest_winners`) |
| `register(ctx)` is called once per plugin; a plugin with no `register` is recorded with `error = "no register() function"` | `hermes_cli/plugins_loader.py:484-516` (`_import_and_register`: `:509-514`), invoked at `:515` inside the per-plugin deadline `run_with_load_deadline` (`:104-148`, `:519`) |
| `manifest.name` defaults to the directory name when `plugin.yaml` omits it | `hermes_cli/plugins_manifest.py:538` |
| `requires_hermes` is load-blocking (skip before import) | `hermes_cli/plugins_loader.py:470-477`; `hermes_cli/plugins_manifest.py:478-486` |

### 1.2 pip entry-point plugins (`hermes_agent.plugins`)

| Fact | File:line |
|---|---|
| Entry-point group constant | `hermes_cli/plugins_discovery.py:29` (`ENTRY_POINTS_GROUP = "hermes_agent.plugins"`); same value in `hermes_cli/plugin_host_child.py:38` (`_ENTRY_POINTS_GROUP`) |
| Metadata-only manifests are built without importing plugin code | `hermes_cli/plugins_discovery.py:72-100` (`discover_entrypoint_manifests`), group select at `:79-81` |
| Companion capability group `hermes_agent.plugin_capabilities` supplies declared capabilities import-free | `hermes_cli/plugins_discovery.py:30`, `:81`, `:87-88` |
| The module/`register` is loaded through the entry point (`module` → module, `module:function` → the attribute) | `hermes_cli/plugins_loader.py:735-741` (`_load_entrypoint_module`); callable-target handling `:503-507` |
| A directory plugin under the same key wins over an entry point of the same name | `hermes_cli/plugins.py:1405-1408` |

### 1.3 Opt-in rule (`plugins.enabled`, `plugins.disabled`)

| Fact | File:line |
|---|---|
| `plugins.disabled` is a deny-list that wins over `plugins.enabled` | `hermes_cli/plugins_discovery.py:112-119` (`_get_disabled_plugins`); gate `:276-277` |
| `plugins.enabled` is the allow-list. Missing/malformed key = `None` = "nothing enabled yet" (first `migrate_config` grandfathers installed user plugins); an empty list = explicitly empty | `hermes_cli/plugins_discovery.py:122-131`; gate `:297-301` |
| The match is on either the path-derived `key` or the manifest `name` | `hermes_cli/plugins_discovery.py:263-264`, `:297` |
| Bundled `backend` plugins auto-load; bundled `platform` plugins are deferred and register lazily; `exclusive`/`model-provider` kinds go to their own discovery; non-bundled sources must be in `plugins.enabled` | `hermes_cli/plugins_discovery.py:278-296`, `:302-310` |
| Discovery applies the gate then loads in `requires_plugins` order | `hermes_cli/plugins.py:1409-1426` (`_discover_and_load_inner`), `_gate_manifest` `:1431-1449` |

### 1.4 `PluginContext` registrars (exact signatures)

| Registrar | Signature | File:line |
|---|---|---|
| `ctx.register_tool` | `(name: str, toolset: str, schema: dict, handler: Callable, check_fn: Callable \| None = None, requires_env: list \| None = None, is_async: bool = False, description: str = "", emoji: str = "", override: bool = False) -> Optional[PluginRegistration]` | `hermes_cli/plugins.py:455-498` (signature `:456-460`) |
| `ctx.register_hook` | `(hook_name: str, callback: Callable) -> PluginRegistration`; an unknown name warns but is still stored | `hermes_cli/plugins.py:933-935` (`_track_callback` `:944-955`) |
| `ctx.register_command` | `(name: str, handler: Callable, description: str = "", args_hint: str = "", argument_mode: str \| None = None) -> Optional[PluginRegistration]`; handler `fn(raw_args: str) -> str \| None`, sync or async | `hermes_cli/plugins.py:646-672` |
| `ctx.register_cli_command` | `(name: str, help: str, setup_fn: Callable, handler_fn: Callable \| None = None, description: str = "") -> PluginRegistration` | `hermes_cli/plugins.py:632-644` |
| `ctx.register_skill` | `(name: str, path: Path, description: str = "", frontmatter: Optional[Mapping[str, Any]] = None) -> PluginRegistration`; resolvable as `<namespace>:<name>`; raises `ValueError`/`FileNotFoundError` | `hermes_cli/plugins_content.py:22-52`; bound into the class body at `hermes_cli/plugins.py:1013` |
| `ctx.get_config` | `(key: str, default: Any = None) -> Any`; reads `plugins.entries.<plugin_id>.settings.<key>` with a legacy `…config` fallback | `hermes_cli/plugins.py:266-276` (`set_config` `:278-280`) |
| `ctx.call_mcp` | `(server: str, tool: str, arguments: Optional[dict] = None, timeout: float = 30) -> dict[str, Any]`; default-deny unless `server` is in `plugins.entries.<plugin_id>.mcp_allowlist`, raises `PermissionError` otherwise; timeout clamps 1-600 s; results over 65536 chars truncated | `hermes_cli/plugins.py:509-538` (`_MCP_RESULT_CHAR_CAP` `:540`) |

Tool handler contract: handlers are `handler(args, **kwargs)`; kwargs are signature-filtered (a narrow
`handler(args)` is safe); every exception is converted to a tool error `{"error": …}` instead of propagating
(`tools/registry.py:893-921`, filtering `:901-904`, error path `:911-921`).

A tool name that would shadow an existing global/built-in tool is **refused**, not raised:
`ctx.register_tool` warns and returns `None` when `registry.get_entry(name)` exists and `override` is false
(`hermes_cli/plugins.py:476-482`); the registry itself also rejects the shadow (`tools/registry.py:695-707`,
`:722-730`). `override=True` additionally needs operator opt-in
`plugins.entries.<plugin_id>.allow_tool_override: true` (`hermes_cli/plugins.py:470-475`).

`ctx.register_cli_command` is **in-process only**: under `plugins.isolation: host` it is skipped with a warning
(`hermes_cli/plugin_isolation.py:44-48`).

### 1.5 Fields a `plugin.yaml` can carry

Recognized keys (unknown keys warn for `manifest_version >= 2`, debug for v1, and never block a load):
`hermes_cli/plugins_manifest.py:32-39` (`_KNOWN_MANIFEST_FIELDS`), warning `:173-179`.
Parsed into `PluginManifest` (dataclass at `hermes_cli/plugins_manifest.py:341-395`) by
`parse_manifest_file` (`:525-557`) and `_parse_manifest_v2_fields` (`:129-184`):

- `name` (defaults to the dir name, `:538`), `version`, `description`, `author` (str or `{name,email,url}`,
  `_display_author` `:82-86`)
- `requires_env` (list of strings or mappings), `optional_env` (consumed raw, `hermes_cli/config.py:4146`)
- `provides_tools`, `provides_hooks` (alias `hooks` accepted, `:549-551`)
- `kind` — one of `standalone | backend | exclusive | platform | model-provider` (`:27`), resolved in `_manifest_kind` (`:503-522`)
- `requires_hermes`, `capabilities`, `emits`, `listens`, `provides_locales` (+ per-id `{endonym, rtl}`)
- v2 (all optional/additive; `SUPPORTED_MANIFEST_VERSION = 2`, `:42`): `manifest_version`, `api_version`,
  `requires_plugins` (`[{id, version_range}]`, advisory + load ordering), `python_dependencies` (validated and
  surfaced only, never auto-installed), `config_schema`, `license`, `homepage`, `tags`
- also accepted/known but **not** dataclass fields (read raw elsewhere): `label`, `platforms`,
  `external_dependencies`, `pip_dependencies`, `provides_browser_providers`, `provides_web_providers`,
  `hermes`, `depends`, `python_runtime` (e.g. `pip_dependencies`/`external_dependencies` at
  `hermes_cli/web_server_memory.py:56-68`, `python_runtime` at `hermes_cli/plugin_validate.py:576`)

**(CHANGED)** `skill_namespace` is **not** a `plugin.yaml` field. It is only ever set on the internal manifest
of a portable Agent Plugins package (`hermes_cli/plugins_manifest.py:499`,
`portable_plugin_manifest`), and defaults to `""` for directory/entry-point plugins. The old report listed it
among manifest fields. `source`, `path`, `key`, `portable` are likewise internal, not YAML keys.

---

## 2. Hooks

### 2.1 `VALID_HOOKS`

The allow-list is `hermes_cli/plugins.py:109-204` (`VALID_HOOKS: set[str] = {` at `:109`, closing `}` at
`:204`). Registering a name outside it warns but is still stored
(`hermes_cli/plugins.py:944-952`). Shell hooks share the same allow-list; `SHELL_UNSUPPORTED_HOOKS` is
`hermes_cli/plugins.py:206-208`.

The four hooks this report cares about (literal lines inside the set):

| Hook | Line in `VALID_HOOKS` |
|---|---|
| `post_tool_call` | `hermes_cli/plugins.py:110` |
| `transform_llm_output` | `hermes_cli/plugins.py:112` (contract comment `:111`) |
| `pre_llm_call` | `hermes_cli/plugins.py:112` |
| `post_llm_call` | `hermes_cli/plugins.py:112` |

### 2.2 Dispatch mechanics

| Fact | File:line |
|---|---|
| `invoke_hook(hook_name, **kwargs)` calls every callback in registration order and returns the non-`None` results | `hermes_cli/plugins_dispatch.py:211-245` |
| A callback with `**kwargs` (or un-introspectable) gets the whole payload; a narrow signature gets only declared keyword names | `hermes_cli/plugins_dispatch.py:184-198` |
| `async def` callbacks are resolved loop-safely instead of returning a coroutine | `hermes_cli/plugins_dispatch.py:200-209` |
| Module entry point used by the agent: `hermes_cli.lifecycle.invoke_hook` = first-party observers, then plugin hooks | `hermes_cli/lifecycle.py:20-29` |
| Timeout-bounded hooks: `post_tool_call`, `transform_llm_output`, `pre_llm_call`, `post_llm_call`, plus others | `hermes_cli/plugins_dispatch.py:42-48` |
| Bound = `plugins.hook_callback_timeout`, default 30 s, clamp 600 s; worker abandoned, never joined | `hermes_cli/plugins.py:1125-1150`; constants `hermes_cli/plugins_dispatch.py:155-156`; default `hermes_cli/config_defaults.py:1717-1719` |
| Only `pre_tool_call` fails **closed** on timeout/raise (emits a block directive); the other bounded hooks fail open (skip) | `hermes_cli/plugins_dispatch.py:50-51`, `:228-244` |

### 2.3 Can a hook replace (or block) the final assistant response? **Replace: yes. Block: no.**

- Function: `agent/turn_finalizer.py:480-519` — `apply_llm_output_transform(agent, final_response, *,
  turn_id, platform=None, logger=None)`.
- Return-value contract: **first hook result that is a non-empty `str` wins**; any other value (`None`, empty
  string, dict, non-str) leaves the text unchanged. Fired as a loop that `break`s on the first hit
  (`agent/turn_finalizer.py:506-517`, contract comment `:506`).
- Payload keys: `response_text`, `session_id`, `model`, `platform`, `turn_id`
  (`agent/turn_finalizer.py:507-514`).
- Ordering vs persistence: the transform runs **before** the final assistant row is first written. Called
  from `agent/turn_final_response.py:348-358` ahead of `append_message` and `_flush_messages_to_session_db`
  (`:360-364`), and from `agent/turn_finalizer.py:627-628` ahead of `_close_transcript_tail` /
  `_persist_session` (`:629-632`). Docstring states it explicitly (`agent/turn_finalizer.py:486-494`): the text
  the user sees is the text stored in SQLite/JSON and replayed.
- Idempotent per turn: yes. The outcome is cached on the agent as `agent._llm_output_transform =
  (turn_id, transformed, pre_transform)`; a later call in the same turn returns the recorded outcome without
  re-firing (`agent/turn_finalizer.py:497-500`, `:518`). A different `turn_id` fires again.
- **Blocking: no such channel.** There is no veto/block contract for the final response — only string
  replacement. (Only `pre_tool_call` has a block directive, `hermes_cli/plugins_dispatch.py:50-51`, `:234-235`.)
- Streaming surfaces: deltas may already have been sent; the differing suffix/replacement is delivered after
  the stream (`cli._post_stream_transform_output`, exercised by
  `tests/hermes_cli/test_transformed_stream_output.py:6-32`). On `--format stream-json` the terminal `result`
  record carries the post-transform `final_response` (`hermes_cli/stream_json.py:82-96`).

### 2.4 Payload keys per hook and the exact call site

| Hook | Payload keys | Call site (file:line) |
|---|---|---|
| `pre_llm_call` | `session_id`, `task_id`, `turn_id`, `user_message`, `conversation_history`, `is_first_turn`, `model`, `platform`, `parent_session_id`, `sender_id` | `agent/turn_context.py:793-847`, payload at `:804-816`; caller `:1172-1176` — **(CHANGED)** old report cited `:787-841` / payload `:798-810` |
| `post_tool_call` | `tool_name`, `args`, `result`, `task_id`, `session_id`, `tool_call_id`, `turn_id`, `api_request_id` (None → `""`), `duration_ms`, `status`, `error_type`, `error_message`, `middleware_trace` | `model_tools.py:676-700`, emit at `:693-698`; the `_CallIds` fields at `:644-655` |
| `transform_llm_output` | `response_text`, `session_id`, `model`, `platform`, `turn_id` | `agent/turn_finalizer.py:507-514` |
| `post_llm_call` | `session_id`, `task_id`, `turn_id`, `user_message`, `assistant_response`, `conversation_history`, `model`, `platform` | `agent/turn_finalizer.py:466-476` (inside `_apply_output_hooks` `:450-477`; called from `finalize_turn` `:655-658`) |

Additional notes on `post_tool_call`: it is gated on `has_hook("post_tool_call")` and derives
`status`/`error_type`/`error_message` from the result only past that gate (`model_tools.py:683-692`). It is
fired **after** the tool ran — it observes the result, it does not change it (use `transform_tool_result` for
that).

Additional notes on `post_llm_call`: it receives the **already-transformed** text as `assistant_response`
(`_apply_output_hooks` calls `apply_llm_output_transform` at `:461-463` first), runs once per turn, and is
skipped for detached forks / when `agent._persist_disabled` is set (`:465`). It fires after the durable flush
(`_persist_step` runs at `:634`, `_apply_output_hooks` at `:655`).

### 2.5 `pre_llm_call` return values → injected context

`agent/turn_context.py:827-844`:

- a `dict` with a truthy `"context"` contributes `str(result["context"])` (`:829-830`);
- a plain non-empty `str` contributes itself (`:831-832`);
- anything else is skipped (`:833-834`);
- accepted pieces are joined with `"\n\n"` (`:844`) and an oversized piece is spilled to disk first
  (`:835-842`, `tools/hook_output_spill`).

The joined text is injected into the **user message**, never the system prompt
(`agent/turn_context.py:797-799` docstring, `:1180-1182` `_merge_gateway_notes`, `:1200-1203`
`_stamp_api_content_sidecar`; composition `:108-130`).

### 2.6 Process model

- Default `plugins.isolation: in_process` imports every plugin into the Hermes process
  (`hermes_cli/plugin_isolation.py:28-31`, `:89-99`).
- With `plugins.isolation: host`, every **non-bundled** Python plugin loads in one plugin-host process
  **per profile home** and talks to Hermes only through `ctx`; bundled plugins stay in-process
  (`hermes_cli/plugins_loader.py:567-578` — `_runs_in_plugin_host`, `_plugin_host` docstring "one process per
  profile home"; `hermes_cli/plugin_isolation.py:1-12`).
- Therefore: hook callbacks run in-process by default; under host isolation they run in that profile's host
  process. Either way **all callbacks of one plugin share one process/interpreter** — they are stored in one
  manager-owned `_hooks` mapping and dispatched from it (`hermes_cli/plugins.py:1180`,
  `hermes_cli/plugins_dispatch.py:229-238`), so a per-turn buffer held in plugin-module state is consistent
  across a plugin's own hooks.

---

## 3. Slash commands in CLI and gateway

| Surface | Dispatch site | What the handler can see |
|---|---|---|
| CLI (interactive REPL) | Unregistered slash input falls through `_process_unregistered_slash` (`cli.py:1215-1233`) → `_run_plugin_slash_command` (`cli.py:1276-1287`). Lookup name is `base_cmd.lstrip("/")` (`:1279`) and the handler is called as `plugin_handler(user_args)` (`:1283`), then async results are resolved by `resolve_plugin_command_result` (`:1283`). Registered names are checked first at `cli.py:773-774`. | **Only `raw_args`.** No `_session_env_scope` / `_set_session_env` is bound on this path (their only definitions are `gateway/run.py:4204` and `:4235-4243`; the scope's own docstring says it exists for "a plugin command handler invoked outside the normal agent-turn path"). The handler reads the process environment (so `$HERMES_HOME/.env` values via `os.environ`), but `get_session_env("HERMES_SESSION_KEY")` does not resolve to a CLI conversation key. The CLI's `pre_command` hook is fired only for **built-in** commands (`cli.py:1189-1195`, guarded by `_cmd_def is not None`), so a plugin command never triggers it. |
| Gateway | `_hm_dispatch_quick_and_plugin_commands` (`gateway/run_inbound.py:1047-1105`); plugin branch at `:1081-1102`. The lookup normalizes `_` → `-` (`:1084`). | A session context is built (`build_session_context(source, self.config)`, `:1092`), `session_key` is set from the source (`:1093`), and the handler runs inside `with self._session_env_scope(_plugin_context):` (`:1095`). Async handlers are awaited on the loop; sync handlers run on the gateway pool with copied contextvars (`:1096-1101`). So `gateway.session_context.get_session_env(...)` resolves the full session variable set — `HERMES_SESSION_PLATFORM/SOURCE/CHAT_ID/CHAT_TYPE/CHAT_NAME/THREAD_ID/USER_ID/USER_NAME/SCOPE_ID/KEY/ID/PROFILE/…` (`gateway/session_context.py:34-48`, reader `:173-179`). |

- Resolver: `get_plugin_command_handler(name)` returns `entry["handler"]` or `None`
  (`hermes_cli/plugins.py:2183-2186`); the registry is `PluginManager._plugin_commands`
  (`hermes_cli/plugins.py:1187`), exposed by `get_plugin_commands()` (`:2226-2228`).
- Async results: `resolve_plugin_command_result` awaits them with a 30 s bound
  (`hermes_cli/plugins.py:2189-2199`).
- **Collision with a built-in is refused at registration time**: `ctx.register_command` lowercases/strips the
  name, calls `hermes_cli.commands.resolve_command(clean)`, and if a built-in matches it logs a warning and
  returns `None` without registering (`hermes_cli/plugins.py:654-663`). It refuses silently (no exception).
- `ctx.register_cli_command` is the other surface: it registers a real `hermes <name> …` argparse subcommand;
  `setup_fn` receives the subparser and `handler_fn` becomes `set_defaults(func=…)`
  (`hermes_cli/plugins.py:632-644`). Under `plugins.isolation: host` this registrar is skipped
  (`hermes_cli/plugin_isolation.py:46-48`).
- `argument_mode` is normalized to one of `options | text | mixed`, defaulting to `text` when `args_hint` is
  given, else `None` (`hermes_cli/plugins.py:664-670`).

---

## 4. Installing a plugin from a local path

Accepted identifier forms — resolved by `hermes_cli/plugins_cmd.py:294-330` (`_resolve_git_url`), scheme list
at `:291`:

| Input | Result |
|---|---|
| `https://`, `http://`, `git@`, `ssh://`, `file://` | used verbatim as the clone URL (with the GitHub-browser-URL special case below) |
| `https://github.com/owner/repo/tree/<ref>/<subdir>` | normalized to `https://github.com/owner/repo.git` + `#subdir` (`:300-309`); other browser segments (`blob`, `commit`, `issues`, `pull`, `releases`, `wiki`, …) collapse to the repo (`:288-290`, `:304-309`) |
| any scheme with `#subdir` fragment or `.git/<subdir>` boundary | explicit subdirectory (`:311-318`) |
| `owner/repo` or `owner/repo#subdir` or `owner/repo/<subdir...>` | `https://github.com/owner/repo.git` + optional subdir (`:321-326`); anything else raises `ValueError` (`:327-330`) |

- `http://` and `file://` are accepted but warn at install time
  (`hermes_cli/plugins_cmd.py:296-297`; `hermes_cli/plugins_cmd_install.py:574-577`, and again in the
  dashboard path `:759-761`).
- Subdirectory containment: `..`, absolute paths and symlinks may not escape the clone root; missing/not-a-dir
  raise `PluginOperationError` (`hermes_cli/plugins_cmd.py:333-347`).
- Clone/place: `_install_plugin_core` (`hermes_cli/plugins_cmd_install.py:331-491`) resolves the URL (`:362`),
  clones into a temp dir under `plugins/` (`:377-379`), reads the manifest (`:385` via
  `_read_manifest_for_install` `:234-257`; `plugin.yaml`/`plugin.yml` first, else portable `plugin.json`),
  derives the plugin name (manifest `name` → subdir leaf → repo name, `:386-387`), sanitizes it (`:398`),
  scans the tree (`:417-419`) and publishes atomically (`:470-485`).
- The clone itself: `_clone_plugin_repo` (`hermes_cli/plugins_cmd_git.py:218-257`): `git clone --depth 1`
  (plus `--filter=blob:none --no-checkout` for subdir installs), credentials scrubbed from the recorded
  origin, returns the HEAD SHA. **The source must be a Git repository.**
- CLI: `hermes plugins install <identifier>` (`hermes_cli/subcommands/plugins.py:18-48`), handler
  `cmd_install` (`hermes_cli/plugins_cmd_install.py:532-683`).
- What enables it after install: `_enable_placed` (`hermes_cli/plugins_cmd_install.py:805-817`) →
  `_set_plugin_enabled(name, enable=True)` (`hermes_cli/plugins_cmd.py:619-632`), which admits the change and
  writes the canonical key into `plugins.enabled` (purging it from `plugins.disabled`). Only then does
  `gate_manifest`'s opt-in check pass (`hermes_cli/plugins_discovery.py:297-301`). `--enable` / `--no-enable`
  and `--yes-deps` make this non-interactive (`hermes_cli/subcommands/plugins.py:33-48`,
  `hermes_cli/plugins_cmd_install.py:614-673`).

**Exact one-liner for a local path** (the source directory must be a Git repo containing `plugin.yaml` or
`plugin.json`):

```powershell
hermes plugins install "file:///C:/absolute/path/to/plugin" --enable --yes-deps
```

A plain non-git local directory is **not** accepted by this command — it would be interpreted as `owner/repo`
shorthand. (Portable/`plugin.json` packages install disabled unless `--enable` is given;
`hermes_cli/subcommands/plugins.py:14-15`.)

---

## 5. `requires_toolsets` with plugin tools: **yes**

| Fact | File:line |
|---|---|
| `requires_toolsets` is read from the skill frontmatter under `metadata.hermes` | `agent/skill_utils.py:707-722` (`_hermes_metadata` `:707-711`; `_CONDITION_KEYS` `:716`; `extract_skill_conditions` `:719-722`) |
| The gate: a skill is hidden when any required toolset is absent from `available_toolsets` | `agent/prompt_builder.py:1296-1314`, check at `:1312` (`any(ts not in ats for ts in conditions.get("requires_toolsets", []))`); no filtering info ⇒ shown (`:1305-1306`) |
| On-disk skills are gated with the same function | `agent/prompt_builder.py:1539` |
| Plugin skills registered with `ctx.register_skill` go through the same gate | `agent/prompt_builder.py:1317-1346` (`_plugin_skill_prompt_rows`), call at `:1339-1340` |
| Where `available_toolsets` comes from | `agent/system_prompt.py:301-314`, computed at `:307`: `{model_tools.get_toolset_for_tool(name) for name in agent.valid_tool_names}` minus `{None, ""}` |
| `agent.valid_tool_names` is the names of the tool definitions the agent has | `agent/agent_init.py:1124` |
| Plugin tools are ordinary entries in the **same** global registry, registered with their own `toolset` | `hermes_cli/plugins.py:476-487` (`registry.register(..., toolset=toolset, ...)`) |
| `get_toolset_for_tool` reads that entry's toolset | `model_tools.py:976-977` → `tools/registry.py:945-946` |
| Plugin toolsets are reported for the `hermes tools` TUI | `hermes_cli/plugins.py:2237-2264` (`get_plugin_toolsets`), consumed at `hermes_cli/tools_config.py:147-149` |

**Consequence:** a plugin that registers `ctx.register_tool(..., toolset="cited", ...)` makes `"cited"` appear
in `available_toolsets` (as soon as that tool is among the agent's tools), so a skill whose frontmatter says
`metadata.hermes.requires_toolsets: [cited]` is offered.

**Important nuance (design-relevant):** for a **plugin-registered** skill the offer-time gate reads the
`frontmatter` **dict passed to `ctx.register_skill`**, not the SKILL.md file on disk:
`hermes_cli/plugins_content.py:24-25`, `:47-50` stores `dict(frontmatter or {})`;
`PluginManager.list_plugin_skill_metadata` returns that stored dict (`hermes_cli/plugins.py:1555-1562`); and
`_plugin_skill_prompt_rows` passes `meta.get("frontmatter")` into the gate (`agent/prompt_builder.py:1335`,
`:1339-1340`). A plugin that omits `frontmatter=` gets an empty condition dict and its skill is always shown.

---

## 6. Secrets and environment

| Fact | File:line |
|---|---|
| `$HERMES_HOME/.env` is loaded into `os.environ` at CLI startup | `hermes_cli/main.py:705-713` (`load_hermes_dotenv(project_env=PROJECT_ROOT/".env")`, default home = process home); also directly in `cli.py:333-340` |
| Loader implementation (user `.env` with `override=True`, then optional `.op.env`, then project `.env` as dev fallback) | `hermes_cli/env_loader.py:454-528` (user `.env` existence/sanitize `:500-501`, load `:505-508`, `.op.env` `:513-515`, project `:517-519`) |
| Gateway loads it too | `gateway/run.py:1575` |
| After plugin discovery, plugin-declared secret sources are re-applied and the installed scope refreshed | `hermes_cli/plugins.py:1376-1395` (`load_hermes_dotenv(hermes_home=home)` at `:1383`) |
| Blessed accessor: `agent.secret_scope.get_secret(name, default=None)` — honours the active profile scope; with a scope installed a miss returns `default` under multiplexing, else falls through to `os.environ`; with no scope and multiplexing inactive it reads `os.environ`; with no scope and multiplexing **active** it raises `UnscopedSecretError` (fail closed) | `agent/secret_scope.py:219-247`; `UnscopedSecretError` class `:115-130`; `get_secret_str` `:250-254` |
| Plugins can also register a secret source (run by `load_hermes_dotenv`) | row `hermes_cli/plugins.py:1047-1053` (`register_secret_source`), generated by `_make_scoped_provider_registrar` `:1072-1084` |

**Fallback for a plugin imported outside Hermes:** `get_secret` itself degrades to `os.environ` when no secret
scope is active and multiplexing is off (`agent/secret_scope.py:237`, `:247`). For a module that must also
import in a plain unit test (where `agent` is not importable), guard the import:

```python
try:
    from agent.secret_scope import get_secret
except Exception:  # imported outside Hermes
    def get_secret(name, default=None):
        return os.environ.get(name, default)
```

`CITED_MCP_TOKEN` therefore reaches a plugin through `get_secret("CITED_MCP_TOKEN")` or `os.environ`.

---

## 7. CLI non-interactive invocation

All flags below were confirmed from the argparse source; they were **not** re-verified by executing Hermes.

| Flag | Definition | File:line |
|---|---|---|
| `hermes -z "<question>"` | top-level `-z`, `--oneshot`, `metavar="PROMPT"`, value-taking: "One-shot mode: send a single prompt and print ONLY the final response text to stdout. No banner, no spinner, no tool previews, no session_id line." | `hermes_cli/_parser.py:148-153`; dispatch `hermes_cli/main.py:3227-3244` (`:3242-3244`), implementation `_run_oneshot_from_args` `:3082-3101` |
| `--usage-file PATH` | one-shot only, writes a JSON usage report | `hermes_cli/_parser.py:154-158` |
| `-m`, `--model` | top-level and chat-level (chat uses `default=SUPPRESS` so it does not clobber the top-level value) | top level `hermes_cli/_parser.py:161-163`; chat `:248-249` |
| `--provider` | top-level and chat-level; no `choices=`, user-defined providers allowed | top level `hermes_cli/_parser.py:164-167`; chat `:259-260` |
| `hermes chat -q "<question>"` | `-q`, `--query`, in a mutually exclusive group with `--query-file` | `hermes_cli/_parser.py:230-239` |
| `hermes chat --oneshot -q …` | chat-level `--oneshot` is `action="store_true"`, `dest="oneshot_exit"`: "With -q/--query-file: answer the query and exit … Implied on non-TTY stdio and by -Q/--quiet." | `hermes_cli/_parser.py:240-246` |
| `--format stream-json` | `add("--format", choices=["text", "stream-json"], default="text", dest="output_format")`: "'stream-json' emits newline-delimited JSON events (JSONL), implies --quiet, and cannot be combined with --tui." | `hermes_cli/_parser.py:264-266`; enforced at `hermes_cli/stream_json.py:18-30` (requires `-q/--query`, forbids `--tui`, sets `args.quiet = True`) |
| `--source tool` | `add("--source", default=None)`: "Session source tag for filtering (default: cli). Use 'tool' for third-party integrations that should not appear in user session lists." | `hermes_cli/_parser.py:309-310` |
| `-Q`, `--quiet` | suppress banner/spinner/tool previews; only final response + session info | `hermes_cli/_parser.py:262-263` |

`--format stream-json` event contract: one JSON object per stdout line
(`hermes_cli/stream_json.py:1-6`), `system/init` first (`:44`), `text` deltas (`:53-57`), `tool_use` /
`tool_result` from tool progress (`:59-80`, output capped at 5000 chars `:15`, `:79`), and one terminal
`result` record with `session_id`, `exit_code`, `text`, token stats and `duration_ms` (`:82-96`).
Diagnostics and `session_id` go to stderr (`:95`).

So both mission invocations are exactly right:

- one JSON event per line: `hermes chat --oneshot -q "<question>" --format stream-json --source tool`
- answer only: `hermes -z "<question>"`
- provider/model override: `hermes chat -q "<question>" --provider deepseek -m deepseek-flash`
  (or top-level: `hermes -z "<question>" --provider deepseek -m deepseek-flash`).

---

## Facts from the old report that CHANGED

| Old claim | Re-checked fact |
|---|---|
| `pre_llm_call` injection at `agent/turn_context.py:787-841`, payload `:798-810` | **(CHANGED)** `_collect_pre_llm_call_context` is `agent/turn_context.py:793-847`; payload `:804-816`; injection rule `:827-844` |
| Plugin opt-in at `plugins_discovery.py:113`, `:123-128`, `:262`, `:300` | **(CHANGED line numbers)** `_get_disabled_plugins` `:112-119`, `_get_enabled_plugins` `:122-131`, opt-in placeholder `:297-301` |
| Manifest fields include `skill_namespace` | **(CHANGED)** `skill_namespace` is internal (portable packages only, `plugins_manifest.py:499`), not a `plugin.yaml` key |
| `ctx.register_command` "refuses" a built-in collision | Refined: it warns and returns `None` without raising (`plugins.py:658-663`) |
| `agent.secret_scope.get_secret` at `agent/secret_scope.py:219-254` | **(CHANGED end line)** function body is `:219-247`; `get_secret_str` `:250-254` |
| "Verified by running them in a temporary `HERMES_HOME`; the transcripts are in `reports/`" | **Could not confirm.** `reports/` contains only this file — no transcripts. Behaviour is confirmed from the argparse source only; no Hermes run was performed in this inspection |

Everything else in the old report held: `VALID_HOOKS` `plugins.py:109-204`, the four hook literals,
`apply_llm_output_transform` `turn_finalizer.py:480-519`, `post_tool_call` payload `model_tools.py:676-700`,
CLI `cli.py:1276-1287`, gateway `run_inbound.py:1081-1102`, `_resolve_git_url` `plugins_cmd.py:288-330`,
`_install_plugin_core` `plugins_cmd_install.py:331-493`, `_enable_placed` `plugins_cmd_install.py:805-817`,
`_skill_should_show` `prompt_builder.py:1296-1314`, `get_plugin_toolsets` `plugins.py:2237-2264`,
`main.py:713`, and `tools/registry.py:893-921`.

---

## Consequences for the plugin design

**(a) Can `transform_llm_output` replace the final answer? — YES.** First non-empty string wins
(`agent/turn_finalizer.py:506-517`), it runs before the assistant row is persisted (`:486-494`,
`agent/turn_final_response.py:348-364`, `agent/turn_finalizer.py:627-632`), and the cached outcome makes it
once-per-`turn_id` (`:497-500`). It **cannot block** the response; there is no veto channel.

**(b) Which hook injects cited-mode rules? — `pre_llm_call`.** Return `{"context": "<rules text>"}` (or a plain
string); the joined pieces are appended to the **user message** of the current turn, never to the system prompt
(`agent/turn_context.py:827-844`, `:1180-1182`). `ctx.register_system_prompt_section` is the alternative when
the text should be frozen into each new session prompt instead of refreshed per turn
(`hermes_cli/plugins.py:957-982`).

**(c) Which hook observes Cited results? — `post_tool_call`.** It receives `tool_name`, `args`, `result`,
`tool_call_id`, `turn_id`, `status`, `error_type`, `error_message`, `duration_ms`, `middleware_trace`
(`model_tools.py:693-698`), which is enough to know exactly which passages a tool returned in the current turn
for verification/audit. It observes only; to rewrite the tool result use `transform_tool_result`.

**(d) How a plugin skill keys on the plugin's own toolset.** Register the tool with
`ctx.register_tool(name, toolset="cited", schema=…, handler=…)` (`hermes_cli/plugins.py:456-460`) and register
the skill with the frontmatter **explicitly** passed:
`ctx.register_skill("cited-mode", SKILL_PATH, frontmatter={"metadata": {"hermes": {"requires_toolsets":
["cited"]}}})` (`hermes_cli/plugins_content.py:22-52`). The offer-time gate reads the stored frontmatter dict
(`hermes_cli/plugins.py:1555-1562`, `agent/prompt_builder.py:1335-1340`) and hides the skill whenever `"cited"`
is absent from `available_toolsets`, which is derived from `agent.valid_tool_names` via
`get_toolset_for_tool` (`agent/system_prompt.py:307`). A plugin skill without explicit `frontmatter=` is never
gated.
