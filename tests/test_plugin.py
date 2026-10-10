"""The plugin registration and the cited-mode turn, end to end inside the process (H2-H6, H9, H10)."""

from __future__ import annotations

import json

from hermes_cited import audit, plugin

GROUNDED = "«Afinación de bicicleta: 380 pesos.» [1]"
REWORDED = "La afinación de bicicleta cuesta 380 pesos [1]."


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
    assert "«" in text
    assert "verbatim" in text


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


def _run_turn(context, answer, mode="cited", session="s1", turn="t1", platform="cli"):
    hook(
        context,
        "pre_llm_call",
        session_id=session,
        turn_id=turn,
        user_message="cuanto cuesta la afinacion",
        platform=platform,
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
        session_id=session,
        turn_id=turn,
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
        session_id=session,
        turn_id=turn,
        model="deepseek-flash",
        platform=platform,
    )


def test_a_copied_cited_answer_is_sealed_and_logged(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited")
    final = _run_turn(context, GROUNDED)
    assert "380 pesos" in final
    assert "Verified by Cited" in final

    path = hermes_home / "cited" / "audit.jsonl"
    count, error = audit.verify_file(path)
    assert error is None
    assert count == 1
    entry = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert entry["mode"] == "cited"
    assert entry["seq"] == 1
    assert entry["session"] == "s1"
    assert entry["turn_id"] == "t1"
    assert entry["verifier"]["applied"] is True
    assert entry["verifier"]["ok"] is True
    assert entry["question"] == "cuanto cuesta la afinacion"
    assert entry["tool_calls"][0]["args"] == {"query": "afinacion"}
    assert len(entry["tool_calls"][0]["excerpt_sha256"][0]) == 64
    assert entry["tool_calls"][0]["excerpt_texts"][0]
    assert cited_env.token not in path.read_text(encoding="utf-8")


def test_a_reworded_datum_is_replaced_by_a_refusal(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited")
    final = _run_turn(context, REWORDED)
    assert "380 pesos" in final
    assert "Verified by Cited" not in final
    path = hermes_home / "cited" / "audit.jsonl"
    entry = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert entry["verifier"]["ok"] is False
    assert any("380 pesos" in item for item in entry["verifier"]["ungrounded"])


def test_a_query_echo_cannot_verify_its_own_datum(monkeypatch, hermes_home, cited_env):
    """B2: a turn with zero passages cannot validate the datum the question carried."""
    context = build(monkeypatch, mode="cited")
    empty = json.dumps(
        {
            "cited_tool": "cited_search",
            "query": "999 pesos",
            "text": 'Cited found 0 passage(s) for "999 pesos".',
            "passages": [],
        }
    )
    hook(
        context,
        "pre_llm_call",
        session_id="s1",
        turn_id="t1",
        user_message="cuanto cuesta el jabon",
        platform="cli",
    )
    hook(
        context,
        "post_tool_call",
        tool_name="cited_search",
        args={"query": "999 pesos"},
        result=empty,
        session_id="s1",
        turn_id="t1",
        status="ok",
    )
    final = hook(
        context, "transform_llm_output", response_text=GROUNDED, session_id="s1", turn_id="t1", platform="cli"
    )
    assert "Verified by Cited" not in final
    assert "no excerpt" in final.lower()


def test_a_refused_cited_ask_becomes_an_explicit_refusal(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited")
    refused = json.dumps(
        {
            "cited_tool": "cited_ask",
            "question": "jabon",
            "status": "refused",
            "answer": "No encuentro eso en los documentos.",
            "text": "No encuentro eso en los documentos.",
            "citations": [],
        }
    )
    hook(context, "pre_llm_call", session_id="s1", turn_id="t1", user_message="jabon", platform="cli")
    hook(
        context,
        "post_tool_call",
        tool_name="cited_ask",
        args={"question": "jabon"},
        result=refused,
        session_id="s1",
        turn_id="t1",
        status="ok",
    )
    final = hook(
        context, "transform_llm_output", response_text="Cuesta 999 pesos.", session_id="s1", turn_id="t1", platform="cli"
    )
    assert "Verified by Cited" not in final
    assert "declined" in final


def test_an_ungrounded_citation_mark_is_refused(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited")
    final = _run_turn(context, "«Afinación de bicicleta: 380 pesos.» [7]")
    assert "Verified by Cited" not in final
    assert "[7]" in final


def test_dot_mode_is_untouched_and_still_logged(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="dot")
    final = _run_turn(context, "La afinacion cuesta 450 pesos inventados.", mode="dot")
    assert final is None
    path = hermes_home / "cited" / "audit.jsonl"
    count, error = audit.verify_file(path)
    assert error is None
    assert count == 1
    entry = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert entry["mode"] == "dot"
    assert entry["verifier"]["applied"] is False
    assert entry["session"] == "s1"


def test_cited_mode_without_a_cited_call_is_refused(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited")
    hook(
        context,
        "pre_llm_call",
        session_id="s1",
        turn_id="t9",
        user_message="cuanto cuesta",
        platform="cli",
    )
    final = hook(
        context, "transform_llm_output", response_text="Cuesta 380 pesos.", session_id="s1", turn_id="t9", platform="cli"
    )
    assert "Verified by Cited" not in final
    assert "Cited" in final


def test_a_failed_append_is_an_operational_refusal_without_a_seal(monkeypatch, hermes_home, cited_env):
    """H10: an answer that cannot be recorded is never delivered as verified."""
    context = build(monkeypatch, mode="cited")

    def fail(*args, **kwargs):
        raise PermissionError("synthetic read-only log")

    monkeypatch.setattr(audit, "append_entry", fail)
    final = _run_turn(context, GROUNDED)
    assert "Verified by Cited" not in final
    assert "could not be written" in final
    assert not (hermes_home / "cited" / "audit.jsonl").exists()


def test_a_broken_tail_is_an_operational_refusal(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited")
    path = hermes_home / "cited" / "audit.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json\n", encoding="utf-8")
    final = _run_turn(context, GROUNDED)
    assert "Verified by Cited" not in final
    assert "could not be written" in final


def test_the_session_and_turn_survive_two_turns(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited")
    _run_turn(context, GROUNDED, session="session-real", turn="t1")
    _run_turn(context, GROUNDED, session="session-real", turn="t2")
    path = hermes_home / "cited" / "audit.jsonl"
    entries = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert [(entry["session"], entry["turn_id"]) for entry in entries] == [
        ("session-real", "t1"),
        ("session-real", "t2"),
    ]


def test_the_token_in_the_question_is_redacted_from_the_log(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited")
    _run_turn(context, GROUNDED, session=cited_env.token, turn=cited_env.token)
    path = hermes_home / "cited" / "audit.jsonl"
    text = path.read_text(encoding="utf-8")
    assert cited_env.token not in text
    assert "<token>" in text


def test_the_mode_command_changes_the_next_turn(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="dot")
    assert context.commands["cited"]("") is not None
    assert "Verified by Cited" in _run_turn(context, GROUNDED)
    context.commands["dot"]("")
    assert _run_turn(context, GROUNDED) is None


def _write_streaming_config(hermes_home, enabled=True):
    (hermes_home / "config.yaml").write_text(
        "streaming:\n  enabled: {0}\n".format("true" if enabled else "false"), encoding="utf-8"
    )


def test_the_seal_is_withheld_on_a_streaming_messaging_surface(monkeypatch, hermes_home, cited_env):
    _write_streaming_config(hermes_home, enabled=True)
    context = build(monkeypatch, mode="cited")
    final = _run_turn(context, GROUNDED, platform="telegram")
    assert "Verified by Cited" not in final
    assert "streaming is on" in final
    path = hermes_home / "cited" / "audit.jsonl"
    entry = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert entry["verifier"]["seal_withheld"] is True
    assert entry["verifier"]["applied"] is True


def test_the_seal_is_kept_when_streaming_is_off(monkeypatch, hermes_home, cited_env):
    _write_streaming_config(hermes_home, enabled=False)
    context = build(monkeypatch, mode="cited")
    final = _run_turn(context, GROUNDED, platform="telegram")
    assert "Verified by Cited" in final
    assert "streaming is on" not in final


def test_a_platform_override_can_turn_streaming_off(monkeypatch, hermes_home, cited_env):
    (hermes_home / "config.yaml").write_text(
        "streaming:\n  enabled: true\ndisplay:\n  platforms:\n    telegram:\n      streaming: false\n",
        encoding="utf-8",
    )
    context = build(monkeypatch, mode="cited")
    final = _run_turn(context, GROUNDED, platform="telegram")
    assert "Verified by Cited" in final


def test_the_cli_keeps_the_seal_by_default(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited")
    final = _run_turn(context, GROUNDED, platform="cli")
    assert "Verified by Cited" in final


def test_the_cli_keeps_the_seal_even_when_its_streaming_is_on(monkeypatch, hermes_home, cited_env):
    """The CLI is documented, not withheld: its consumer shows only the terminal result record."""
    (hermes_home / "config.yaml").write_text("display:\n  streaming: true\n", encoding="utf-8")
    context = build(monkeypatch, mode="cited")
    final = _run_turn(context, GROUNDED, platform="cli")
    assert "Verified by Cited" in final
    assert "seal is withheld" not in final
