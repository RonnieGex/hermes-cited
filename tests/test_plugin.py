"""The plugin registration and the cited-mode turn, end to end inside the process (H2-H12, D5, D7)."""

from __future__ import annotations

import json

import pytest

from hermes_cited import audit, plugin, render, verifier

GROUNDED = "- Afinacion de bicicleta: 380 pesos."
WRONG_PROSE = "La afinacion de bicicleta cuesta 999 pesos [7].\n\nVerified by Cited"


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


def pre(context, session="s1", turn="t1", platform="cli", message="cuanto cuesta la afinacion"):
    return hook(
        context,
        "pre_llm_call",
        session_id=session,
        turn_id=turn,
        user_message=message,
        platform=platform,
        conversation_history=[],
        is_first_turn=True,
        model="deepseek-flash",
        task_id="task",
        parent_session_id="",
        sender_id="",
    )


def search(context, session="s1", turn="t1", query="afinacion", envelope=None):
    raw = envelope if envelope is not None else context.tools["cited_search"]["handler"]({"query": query})
    hook(
        context,
        "post_tool_call",
        tool_name="cited_search",
        args={"query": query},
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
    return raw


def quote(context, args, session="s1"):
    return context.tools["cited_quote"]["handler"](args, session_id=session)


def transform(context, answer="", session="s1", turn="t1", platform="cli"):
    return hook(
        context,
        "transform_llm_output",
        response_text=answer,
        session_id=session,
        turn_id=turn,
        model="deepseek-flash",
        platform=platform,
    )


def run_turn(context, answer="", mode="cited", session="s1", turn="t1", platform="cli", args=None,
             do_search=True, envelope=None):
    pre(context, session=session, turn=turn, platform=platform)
    if do_search:
        search(context, session=session, turn=turn, envelope=envelope)
    if args is not None:
        quote(context, args, session=session)
    return transform(context, answer=answer, session=session, turn=turn, platform=platform)


def entries_of(home):
    path = home / "cited" / "audit.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_register_registers_the_three_tools_hooks_commands_and_skill(monkeypatch, hermes_home):
    context = build(monkeypatch)
    assert set(context.tools) == {"cited_search", "cited_ask", "cited_quote"}
    assert context.tools["cited_quote"]["toolset"] == "cited"
    assert context.tools["cited_quote"]["schema"]["required"] == ["passage", "lines"]
    assert set(context.hooks) == {"pre_llm_call", "post_tool_call", "transform_llm_output"}
    assert set(context.commands) == {"cited", "dot"}
    assert "cited" in context.skills
    assert context.skills["cited"]["path"].exists()


def test_the_tools_are_native_and_not_mcp(monkeypatch, hermes_home):
    context = build(monkeypatch)
    assert all(not name.startswith("mcp__") for name in context.tools)


def test_cited_mode_injects_the_choice_rules(monkeypatch, hermes_home):
    context = build(monkeypatch, mode="cited")
    result = pre(context)
    text = result["context"] if isinstance(result, dict) else result
    assert "cited_quote" in text
    assert "discard" in text.lower() or "discarded" in text.lower()


def test_dot_mode_injects_nothing(monkeypatch, hermes_home):
    context = build(monkeypatch, mode="dot")
    assert not pre(context)


def test_a_chosen_line_is_rendered_and_sealed_and_logged(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited")
    final = run_turn(context, answer="prose to discard", args={"passage": 1, "lines": [4]})
    assert final.startswith("Según tus documentos:")
    assert GROUNDED in final
    assert "Fuente: cafe-la-horquilla.md - Precios" in final
    assert "[1]" in final
    assert final.rstrip().endswith("Verified by Cited")
    assert "prose to discard" not in final

    path = hermes_home / "cited" / "audit.jsonl"
    count, error = audit.verify_file(path)
    assert error is None
    assert count == 1
    entry = entries_of(hermes_home)[0]
    assert entry["mode"] == "cited"
    assert entry["seq"] == 1
    assert entry["session"] == "s1"
    assert entry["turn_id"] == "t1"
    assert entry["verifier"]["applied"] is True
    assert entry["verifier"]["ok"] is True
    assert entry["verifier"]["seal_withheld"] is False
    assert entry["quoted_lines"][0]["text"] == GROUNDED
    assert entry["quoted_lines"][0]["passage"] == 1
    assert entry["response"] == final
    assert cited_env.token not in path.read_text(encoding="utf-8")


def test_the_models_prose_is_discarded_whole(monkeypatch, hermes_home, cited_env):
    """B-R2-1 and B-R2-2: a wrong value, a moved subject or a forged seal never reach the answer."""
    context = build(monkeypatch, mode="cited")
    final = run_turn(context, answer=WRONG_PROSE, args={"passage": 1, "lines": [4]})
    assert "999" not in final
    assert "[7]" not in final
    assert GROUNDED in final
    entry = entries_of(hermes_home)[0]
    assert "999" not in entry["response"]


def test_the_quote_tool_returns_the_exact_text(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited")
    pre(context)
    search(context)
    raw = quote(context, {"passage": 1, "lines": [4]})
    assert raw == GROUNDED


def test_the_quote_tool_accepts_several_lines_in_order(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited")
    pre(context)
    search(context)
    quote(context, {"passage": 1, "lines": [2, 4]})
    final = transform(context)
    assert final.index("- Espresso: 35 pesos.") < final.index(GROUNDED)


def test_an_unknown_passage_is_refused_and_records_nothing(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited")
    pre(context)
    search(context)
    raw = quote(context, {"passage": 9, "lines": [1]})
    assert "passage" in raw.lower()
    final = transform(context)
    assert final == render.refusal_text("es")


def test_an_unknown_line_is_refused(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited")
    pre(context)
    search(context)
    raw = quote(context, {"passage": 1, "lines": [99]})
    assert "line" in raw.lower()


def test_without_a_quote_call_the_fixed_refusal_is_delivered(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited")
    final = run_turn(context, answer=WRONG_PROSE)
    assert final == render.refusal_text("es")
    assert verifier.SEAL not in final


def test_a_refused_cited_ask_is_the_fixed_refusal(monkeypatch, hermes_home, cited_env):
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
    pre(context)
    search(context, envelope=refused)
    final = transform(context, answer="Cuesta 999 pesos.")
    assert final == render.refusal_text("es")


def test_a_turn_with_no_excerpt_is_the_fixed_refusal(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited")
    empty = json.dumps(
        {
            "cited_tool": "cited_search",
            "query": "999 pesos",
            "text": 'Cited found 0 passage(s) for "999 pesos".',
            "passages": [],
        }
    )
    final = run_turn(context, answer="Cuesta 999 pesos.", envelope=empty)
    assert final == render.refusal_text("es")


def test_the_language_is_configurable(monkeypatch, hermes_home, cited_env):
    monkeypatch.setenv("CITED_LANGUAGE", "en")
    context = build(monkeypatch, mode="cited")
    final = run_turn(context, args={"passage": 2, "lines": [1]})
    assert final.startswith("From your documents:")
    assert "Source: bike-workshop-policies.md - Guarantee" in final


def test_the_english_refusal_is_used_when_configured(monkeypatch, hermes_home, cited_env):
    monkeypatch.setenv("CITED_LANGUAGE", "en")
    context = build(monkeypatch, mode="cited")
    assert run_turn(context) == "It is not in the documents."


def test_dot_mode_is_untouched_and_still_logged(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="dot")
    final = run_turn(context, answer="La afinacion cuesta 450 pesos inventados.", mode="dot")
    assert final is None
    count, error = audit.verify_file(hermes_home / "cited" / "audit.jsonl")
    assert error is None
    assert count == 1
    entry = entries_of(hermes_home)[0]
    assert entry["mode"] == "dot"
    assert entry["verifier"]["applied"] is False
    assert entry["session"] == "s1"


def test_dot_mode_strips_a_seal_written_by_the_model(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="dot")
    final = run_turn(context, answer="La afinacion cuesta 380 pesos.\n\nVerified by Cited", mode="dot")
    assert final == "La afinacion cuesta 380 pesos."
    assert "Verified by Cited" not in final
    assert entries_of(hermes_home)[0]["response"] == final


def test_a_failed_append_is_an_operational_refusal_without_a_seal(monkeypatch, hermes_home, cited_env):
    """H10: an answer that cannot be recorded is never delivered as verified."""
    context = build(monkeypatch, mode="cited")

    def fail(*args, **kwargs):
        raise PermissionError("synthetic read-only log")

    monkeypatch.setattr(audit, "append_entry", fail)
    final = run_turn(context, answer=WRONG_PROSE, args={"passage": 1, "lines": [4]})
    assert verifier.SEAL not in final
    assert "could not be written" in final
    assert not (hermes_home / "cited" / "audit.jsonl").exists()


def test_a_broken_tail_is_an_operational_refusal(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited")
    path = hermes_home / "cited" / "audit.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json\n", encoding="utf-8")
    final = run_turn(context, args={"passage": 1, "lines": [4]})
    assert verifier.SEAL not in final
    assert "could not be written" in final


def test_the_session_and_turn_survive_two_turns(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited")
    run_turn(context, args={"passage": 1, "lines": [4]}, session="session-real", turn="t1")
    run_turn(context, args={"passage": 1, "lines": [4]}, session="session-real", turn="t2")
    entries = entries_of(hermes_home)
    assert [(entry["session"], entry["turn_id"]) for entry in entries] == [
        ("session-real", "t1"),
        ("session-real", "t2"),
    ]


def test_the_token_in_the_question_is_redacted_from_the_log(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited")
    run_turn(context, args={"passage": 1, "lines": [4]}, session=cited_env.token, turn=cited_env.token)
    text = (hermes_home / "cited" / "audit.jsonl").read_text(encoding="utf-8")
    assert cited_env.token not in text
    assert "<token>" in text


def test_the_mode_command_changes_the_next_turn(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="dot")
    assert context.commands["cited"]("") is not None
    assert verifier.SEAL in run_turn(context, args={"passage": 1, "lines": [4]})
    context.commands["dot"]("")
    assert run_turn(context) is None


def _write_config(hermes_home, body):
    (hermes_home / "config.yaml").write_text(body, encoding="utf-8")


def test_the_seal_is_withheld_on_a_streaming_messaging_surface(monkeypatch, hermes_home, cited_env):
    _write_config(hermes_home, "streaming:\n  enabled: true\n")
    context = build(monkeypatch, mode="cited")
    final = run_turn(context, args={"passage": 1, "lines": [4]}, platform="telegram")
    assert verifier.SEAL not in final
    assert "streaming is on" in final
    entry = entries_of(hermes_home)[0]
    assert entry["verifier"]["seal_withheld"] is True
    assert entry["verifier"]["applied"] is True
    assert entry["response"] == final


def test_the_seal_is_kept_when_streaming_is_off(monkeypatch, hermes_home, cited_env):
    _write_config(hermes_home, "streaming:\n  enabled: false\n")
    context = build(monkeypatch, mode="cited")
    final = run_turn(context, args={"passage": 1, "lines": [4]}, platform="telegram")
    assert verifier.SEAL in final
    assert "streaming is on" not in final


def test_a_platform_override_can_turn_streaming_off(monkeypatch, hermes_home, cited_env):
    _write_config(
        hermes_home,
        "streaming:\n  enabled: true\ndisplay:\n  platforms:\n    telegram:\n      streaming: false\n",
    )
    context = build(monkeypatch, mode="cited")
    final = run_turn(context, args={"passage": 1, "lines": [4]}, platform="telegram")
    assert verifier.SEAL in final


def test_an_unknown_messaging_surface_withholds(monkeypatch, hermes_home, cited_env):
    _write_config(hermes_home, "streaming:\n  enabled: true\n")
    context = build(monkeypatch, mode="cited")
    final = run_turn(context, args={"passage": 1, "lines": [4]}, platform="acme-chat")
    assert verifier.SEAL not in final


def test_the_cli_keeps_the_seal_when_its_streaming_is_off(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited")
    final = run_turn(context, args={"passage": 1, "lines": [4]}, platform="cli")
    assert verifier.SEAL in final


def test_the_cli_with_streaming_on_withholds_the_seal(monkeypatch, hermes_home, cited_env):
    """D7: the CLI without streaming is the only explicit exception."""
    _write_config(hermes_home, "display:\n  streaming: true\n")
    context = build(monkeypatch, mode="cited")
    final = run_turn(context, args={"passage": 1, "lines": [4]}, platform="cli")
    assert verifier.SEAL not in final
    assert "streaming is on" in final


def test_the_desktop_withholds_the_seal_with_the_d1_warning(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited")
    final = run_turn(context, args={"passage": 1, "lines": [4]}, platform="desktop")
    assert verifier.SEAL not in final
    assert "draft may be visible" in final
    assert entries_of(hermes_home)[0]["verifier"]["seal_withheld"] is True
