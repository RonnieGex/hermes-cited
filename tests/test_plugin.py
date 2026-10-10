"""The plugin registration and the cited-mode turn, end to end inside the process (H2-H6)."""

from __future__ import annotations

import json

from hermes_cited import audit, plugin


class DictState:
    def __init__(self):
        self.data = {}

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value


class FakeContext:
    """The slice of PluginContext this plugin uses, with the real registration signatures."""

    def __init__(self):
        self.state = DictState()
        self.tools = {}
        self.hooks = {}
        self.commands = {}
        self.skills = {}

    def register_tool(self, name, toolset, schema, handler, check_fn=None, requires_env=None,
                      is_async=False, description="", emoji="", override=False):
        self.tools[name] = {
            "toolset": toolset,
            "schema": schema,
            "handler": handler,
            "description": description,
            "emoji": emoji,
        }

    def register_hook(self, hook_name, callback):
        self.hooks.setdefault(hook_name, []).append(callback)

    def register_command(self, name, handler, description="", args_hint="", argument_mode=None):
        self.commands[name] = handler

    def register_skill(self, name, path, description="", frontmatter=None):
        self.skills[name] = {"path": path, "description": description, "frontmatter": frontmatter}


def build(monkeypatch, mode="dot"):
    monkeypatch.setenv("CITED_DEFAULT_MODE", mode)
    context = FakeContext()
    plugin.register(context)
    return context


def hook(context, name, **payload):
    results = [callback(**payload) for callback in context.hooks.get(name, [])]
    return results[0] if len(results) == 1 else results


def test_register_registers_the_two_tools_hooks_commands_and_skill(monkeypatch, hermes_home):
    context = build(monkeypatch)
    assert set(context.tools) == {"cited_search", "cited_ask"}
    assert context.tools["cited_search"]["toolset"] == "cited"
    assert context.tools["cited_search"]["schema"]["required"] == ["query"]
    assert context.tools["cited_ask"]["schema"]["required"] == ["question"]
    assert set(context.hooks) == {"pre_llm_call", "post_tool_call", "transform_llm_output"}
    assert set(context.commands) == {"cited", "dot"}
    assert "cited" in context.skills
    assert context.skills["cited"]["path"].exists()


def test_the_tools_are_native_and_not_mcp(monkeypatch, hermes_home):
    context = build(monkeypatch)
    assert all(not name.startswith("mcp__") for name in context.tools)


def test_cited_mode_injects_the_strict_rules(monkeypatch, hermes_home):
    context = build(monkeypatch, mode="cited")
    result = hook(
        context,
        "pre_llm_call",
        session_id="s1",
        turn_id="t1",
        user_message="cuanto cuesta",
        platform="cli",
        conversation_history=[],
        is_first_turn=True,
        model="deepseek-flash",
        task_id="task",
        parent_session_id="",
        sender_id="",
    )
    text = result["context"] if isinstance(result, dict) else result
    assert "Cited" in text
    assert "cited_search" in text or "cited_ask" in text


def test_dot_mode_injects_nothing(monkeypatch, hermes_home):
    context = build(monkeypatch, mode="dot")
    result = hook(
        context,
        "pre_llm_call",
        session_id="s1",
        turn_id="t1",
        user_message="hola",
        platform="cli",
        conversation_history=[],
        is_first_turn=True,
        model="deepseek-flash",
        task_id="task",
        parent_session_id="",
        sender_id="",
    )
    assert not result


def _run_turn(context, cited_env, answer, mode="cited"):
    hook(
        context,
        "pre_llm_call",
        session_id="s1",
        turn_id="t1",
        user_message="cuanto cuesta la afinacion",
        platform="cli",
        conversation_history=[],
        is_first_turn=True,
        model="deepseek-flash",
        task_id="task",
        parent_session_id="",
        sender_id="",
    )
    raw = context.tools["cited_search"]["handler"]({"query": "afinacion"})
    hook(
        context,
        "post_tool_call",
        tool_name="cited_search",
        args={"query": "afinacion"},
        result=raw,
        session_id="s1",
        turn_id="t1",
        tool_call_id="call-1",
        status="ok",
        error_type=None,
        error_message=None,
        duration_ms=5,
        middleware_trace=[],
    )
    return hook(
        context,
        "transform_llm_output",
        response_text=answer,
        session_id="s1",
        turn_id="t1",
        model="deepseek-flash",
        platform="cli",
    )


def test_a_grounded_cited_answer_is_sealed_and_logged(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited")
    final = _run_turn(context, cited_env, "La afinacion cuesta 380 pesos [1].")
    assert "380 pesos" in final
    assert "Verified by Cited" in final

    path = hermes_home / "cited" / "audit.jsonl"
    count, error = audit.verify_file(path)
    assert error is None
    assert count == 1
    entry = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert entry["mode"] == "cited"
    assert entry["verifier"]["applied"] is True
    assert entry["verifier"]["ok"] is True
    assert entry["question"] == "cuanto cuesta la afinacion"
    assert entry["tool_calls"][0]["args"] == {"query": "afinacion"}
    assert len(entry["tool_calls"][0]["excerpt_sha256"][0]) == 64
    assert cited_env.token not in path.read_text(encoding="utf-8")


def test_an_invented_number_is_replaced_by_a_refusal(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited")
    final = _run_turn(context, cited_env, "La afinacion cuesta 450 pesos [1].")
    assert "450" in final
    assert "Verified by Cited" not in final
    path = hermes_home / "cited" / "audit.jsonl"
    entry = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert entry["verifier"]["ok"] is False
    assert "450" in entry["verifier"]["ungrounded"]


def test_dot_mode_is_untouched_and_still_logged(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="dot")
    final = _run_turn(context, cited_env, "La afinacion cuesta 450 pesos inventados.")
    assert final is None
    path = hermes_home / "cited" / "audit.jsonl"
    count, error = audit.verify_file(path)
    assert error is None
    assert count == 1
    entry = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert entry["mode"] == "dot"
    assert entry["verifier"]["applied"] is False


def test_cited_mode_without_a_cited_call_is_refused(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited")
    hook(
        context,
        "pre_llm_call",
        session_id="s1",
        turn_id="t9",
        user_message="cuanto cuesta",
        platform="cli",
        conversation_history=[],
        is_first_turn=True,
        model="deepseek-flash",
        task_id="task",
        parent_session_id="",
        sender_id="",
    )
    final = hook(
        context,
        "transform_llm_output",
        response_text="Cuesta 380 pesos.",
        session_id="s1",
        turn_id="t9",
        model="deepseek-flash",
        platform="cli",
    )
    assert "Verified by Cited" not in final
    assert "Cited" in final


def test_the_mode_command_changes_the_next_turn(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="dot")
    assert context.commands["cited"]("") is not None
    assert "Verified by Cited" in _run_turn(context, cited_env, "Cuesta 380 pesos [1].")
    context.commands["dot"]("")
    assert _run_turn(context, cited_env, "Cuesta 380 pesos [1].") is None
