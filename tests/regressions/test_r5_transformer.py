"""Permanent regressions of the fifth review: the incident code.

R5 B-R5-1 (the generation of the incident can break the boundary of C1) and, until D12 retired it, R5 M-R5-3
(the sanitisation could produce the mark and left Markdown presentations undetected). The reproductions of
B-R5-1 through the real loader and dispatcher live in ``test_r5_host.py``; this module exercises the same
properties on the registered hooks, so a machine without the read-only host copy still runs them.
"""

from __future__ import annotations

import json

from hermes_cited import messages, plugin, verifier

GROUNDED = "- Afinacion de bicicleta: 380 pesos."
QUIET = (
    "streaming:\n  enabled: false\ndisplay:\n  streaming: false\n  interim_assistant_messages: false\n"
)


class DictState:
    def __init__(self):
        self.data = {}

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value


class FakeContext:
    def __init__(self):
        self.state = DictState()
        self.tools = {}
        self.hooks = {}
        self.commands = {}
        self.skills = {}

    def register_tool(self, name, toolset, schema, handler, check_fn=None, requires_env=None,
                      is_async=False, description="", emoji="", override=False):
        self.tools[name] = {"handler": handler}

    def register_hook(self, hook_name, callback):
        self.hooks.setdefault(hook_name, []).append(callback)

    def register_command(self, name, handler, description="", args_hint="", argument_mode=None):
        self.commands[name] = handler

    def register_skill(self, name, path, description="", frontmatter=None):
        self.skills[name] = {"path": path}


def prepare(monkeypatch, home, mode="cited"):
    monkeypatch.setenv("CITED_DEFAULT_MODE", mode)
    (home / "config.yaml").write_text(QUIET, encoding="utf-8")
    context = FakeContext()
    plugin.register(context)
    return context


def envelope(excerpt=GROUNDED):
    return json.dumps({
        "cited_tool": "cited_search",
        "query": "afinacion",
        "text": "t",
        "passages": [{"n": 1, "document": "cafe-la-horquilla.md", "heading": "Precios",
                      "position": 2, "excerpt": excerpt}],
    })


def begin(context, session="s1", turn="t1", platform="cli"):
    context.hooks["pre_llm_call"][0](session_id=session, turn_id=turn, user_message="q", platform=platform)
    context.hooks["post_tool_call"][0](tool_name="cited_search", args={"query": "q"}, result=envelope(),
                                       session_id=session, turn_id=turn, status="ok")
    return session, turn


def quote(context, session="s1", turn="t1", args=None):
    return context.tools["cited_quote"]["handler"](
        args or {"passage": "P1", "lines": [1]}, session_id=session, turn_id=turn)


def transform(context, answer="MODEL_LEAK_999", session="s1", turn="t1", platform="cli"):
    return context.hooks["transform_llm_output"][0](response_text=answer, session_id=session, turn_id=turn,
                                                    platform=platform)


def entries_of(home):
    path = home / "cited" / "audit.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# --- B-R5-1: the incident code never breaks the boundary -------------------------------------------


def test_b_r5_1_the_reserve_code_is_constant_and_not_empty(monkeypatch):
    """R5 B-R5-1: ``incident_code`` used to raise with the entropy dependency it needs."""

    def broken(*args, **kwargs):
        raise OSError("synthetic random source unavailable")

    monkeypatch.setattr(plugin.secrets, "token_hex", broken)
    first = plugin.incident_code()
    second = plugin.incident_code()
    assert first == second == plugin.RESERVE_INCIDENT_CODE
    assert first and first.startswith("CITED-")


def test_b_r5_1_a_failure_of_entropy_still_yields_the_fixed_refusal(monkeypatch, hermes_home, cited_env):
    """R5 B-R5-1: with a valid selection and no log yet, a failing entropy cannot leak the prose."""
    context = prepare(monkeypatch, hermes_home, mode="cited")
    begin(context)
    assert quote(context) == GROUNDED

    def broken(*args, **kwargs):
        raise OSError("synthetic random source unavailable")

    monkeypatch.setattr(plugin.secrets, "token_hex", broken)
    final = transform(context)
    assert "MODEL_LEAK_999" not in final
    assert verifier.SEAL not in final
    assert plugin.RESERVE_INCIDENT_CODE in final
    assert final.startswith("No puedo entregar")
    assert entries_of(hermes_home) == []
    assert plugin._turn_of("s1", "t1") is None


def test_b_r5_1_the_emergency_exit_depends_on_nothing_fallible(monkeypatch, hermes_home, cited_env):
    """R5 B-R5-1: the refusal is built with no entropy, no disk, no configuration and no logger."""
    context = prepare(monkeypatch, hermes_home, mode="cited")
    begin(context)
    quote(context)

    def broken(*args, **kwargs):
        raise OSError("synthetic failure of every dependency")

    class BrokenLogger:
        def error(self, *args, **kwargs):
            raise OSError("synthetic logger failure")

    monkeypatch.setattr(plugin.secrets, "token_hex", broken)
    monkeypatch.setattr(plugin, "logger", BrokenLogger())
    monkeypatch.setattr(plugin, "_language", broken)
    monkeypatch.setattr(plugin, "_safe_language", broken)
    monkeypatch.setattr(plugin.audit, "append_entry", broken)
    final = transform(context)
    assert final == messages.operational_text(messages.DEFAULT_LANGUAGE, plugin.RESERVE_INCIDENT_CODE)
    assert "MODEL_LEAK_999" not in final
    assert verifier.SEAL not in final


def test_b_r5_1_the_handlers_and_the_quote_refusal_use_the_safe_generation(monkeypatch, hermes_home, cited_env):
    """R5 B-R5-1: a handler that fails builds its refusal with the same safe generation, and never raises."""
    context = prepare(monkeypatch, hermes_home, mode="cited")

    def broken(*args, **kwargs):
        raise OSError("synthetic random source unavailable")

    monkeypatch.setattr(plugin.secrets, "token_hex", broken)
    monkeypatch.setattr(plugin, "_resolve_active_turn", broken)
    raw = quote(context)
    assert raw == "Cited could not quote this selection."
    assert plugin.incident_code() == plugin.RESERVE_INCIDENT_CODE


# --- M-R5-3 was retired by D12 (round 8): dot mode does not rewrite the model's text ------------------
#
# The reproductions of M-R5-3 lived here. With D11 the plugin emits no seal on any route, so D12 retires the
# removal of the reserved mark. The property is now asserted by `test_r8_dot_passthrough.py` (the intact
# pass-through through the real host and the recorded bytes) and by `test_dot_mode_delivers_every_text_intact`
# in `tests/test_plugin.py`. The metadata escaping that M-R5-3 also covered stays in `test_r4_render.py`.
