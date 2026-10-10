"""The plugin registration and the cited-mode turn, end to end inside the process (H2-H15, D5, D9-D14)."""

from __future__ import annotations

import json

import pytest

from hermes_cited import audit, delivery, messages, plugin, render, verifier

GROUNDED = "- Afinacion de bicicleta: 380 pesos."
WRONG_PROSE = "La afinacion de bicicleta cuesta 999 pesos [7].\n\nVerified by Cited"
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


def write_config(hermes_home, body):
    (hermes_home / "config.yaml").write_text(body, encoding="utf-8")


def build(monkeypatch, mode="dot", hermes_home=None, quiet=True):
    monkeypatch.setenv("CITED_DEFAULT_MODE", mode)
    if hermes_home is not None and quiet:
        write_config(hermes_home, QUIET)
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


def ask(context, session="s1", turn="t1", envelope=None):
    hook(
        context,
        "post_tool_call",
        tool_name="cited_ask",
        args={"question": "jabon"},
        result=envelope,
        session_id=session,
        turn_id=turn,
        tool_call_id="call-2",
        status="ok",
        error_type=None,
        error_message=None,
        duration_ms=5,
        middleware_trace=[],
    )


def quote(context, args, session="s1", turn_id="", task_id=""):
    return context.tools["cited_quote"]["handler"](args, session_id=session, turn_id=turn_id, task_id=task_id)


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
        quote(context, args, session=session, turn_id=turn)
    return transform(context, answer=answer, session=session, turn=turn, platform=platform)


def entries_of(home):
    path = home / "cited" / "audit.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_register_registers_the_three_tools_hooks_commands_and_skill(monkeypatch, hermes_home):
    context = build(monkeypatch, hermes_home=hermes_home)
    assert set(context.tools) == {"cited_search", "cited_ask", "cited_quote"}
    assert context.tools["cited_quote"]["toolset"] == "cited"
    assert context.tools["cited_quote"]["schema"]["required"] == ["passage", "lines"]
    assert set(context.hooks) == {"pre_llm_call", "post_tool_call", "transform_llm_output"}
    assert set(context.commands) == {"cited", "dot"}
    assert "cited" in context.skills
    assert context.skills["cited"]["path"].exists()


def test_the_tools_are_native_and_not_mcp(monkeypatch, hermes_home):
    context = build(monkeypatch, hermes_home=hermes_home)
    assert all(not name.startswith("mcp__") for name in context.tools)


def test_cited_mode_injects_the_choice_rules(monkeypatch, hermes_home):
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home)
    result = pre(context)
    text = result["context"] if isinstance(result, dict) else result
    assert "cited_quote" in text
    assert "discard" in text.lower() or "discarded" in text.lower()
    assert "P1" in text


def test_dot_mode_injects_nothing(monkeypatch, hermes_home):
    context = build(monkeypatch, mode="dot", hermes_home=hermes_home)
    assert not pre(context)


def test_a_chosen_line_is_rendered_and_sealed_and_logged(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home)
    final = run_turn(context, answer="prose to discard", args={"passage": "P1", "lines": [4]})
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
    assert entry["verifier"]["verified"] is True
    assert entry["verifier"]["seal_withheld"] is False
    assert entry["quoted_lines"][0]["text"] == GROUNDED
    assert entry["quoted_lines"][0]["pid"] == "P1"
    assert entry["quoted_lines"][0]["original"] == 1
    assert entry["response"] == final
    assert entry["transcript"] == final[: -len("\n\nVerified by Cited")]
    assert entry["delivery"]["seal"] is True
    assert cited_env.token not in path.read_text(encoding="utf-8")


def test_a_numeric_passage_is_still_accepted_when_it_is_unambiguous(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home)
    final = run_turn(context, args={"passage": 1, "lines": [4]})
    assert GROUNDED in final
    assert final.rstrip().endswith("Verified by Cited")


def test_the_models_prose_is_discarded_whole(monkeypatch, hermes_home, cited_env):
    """B-R2-1 and B-R2-2: a wrong value, a moved subject or a forged seal never reach the answer."""
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home)
    final = run_turn(context, answer=WRONG_PROSE, args={"passage": "P1", "lines": [4]})
    assert "999" not in final
    assert "[7]" not in final
    assert GROUNDED in final
    entry = entries_of(hermes_home)[0]
    assert "999" not in entry["response"]


def test_the_quote_tool_returns_the_exact_text(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home)
    pre(context)
    search(context)
    assert quote(context, {"passage": "P1", "lines": [4]}) == GROUNDED


def test_the_quote_tool_accepts_several_lines_in_order(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home)
    pre(context)
    search(context)
    quote(context, {"passage": "P1", "lines": [2, 4]})
    final = transform(context)
    assert final.index("- Espresso: 35 pesos.") < final.index(GROUNDED)


def test_an_unknown_passage_is_refused_and_records_nothing(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home)
    pre(context)
    search(context)
    raw = quote(context, {"passage": "P9", "lines": [1]})
    assert "passage" in raw.lower()
    final = transform(context)
    assert final == render.refusal_text("es")


def test_an_unknown_line_is_refused(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home)
    pre(context)
    search(context)
    raw = quote(context, {"passage": "P1", "lines": [99]})
    assert "line" in raw.lower()


@pytest.mark.parametrize(
    "bad",
    [0, -1, True, False, 1.5, 999999, "²", "９", "9" * 5000, "P" * 40, "", None, {}, [], "P1 P2"],
)
def test_cited_quote_never_raises_on_a_bad_passage(monkeypatch, hermes_home, cited_env, bad):
    """m-R3-1: only positive integers of the schema, and the handler never raises into Hermes."""
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home)
    pre(context)
    search(context)
    raw = quote(context, {"passage": bad, "lines": [1]})
    assert isinstance(raw, str)
    assert "could not quote" in raw.lower() or "citation" in raw.lower() or "pid" in raw.lower()


@pytest.mark.parametrize("bad", [0, -1, True, 1.5, 999999, "²", "9" * 5000, None, {}])
def test_cited_quote_never_raises_on_a_bad_line(monkeypatch, hermes_home, cited_env, bad):
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home)
    pre(context)
    search(context)
    raw = quote(context, {"passage": "P1", "lines": [bad]})
    assert isinstance(raw, str)
    assert "line" in raw.lower() or "could not quote" in raw.lower()


def test_without_a_quote_call_the_fixed_refusal_is_delivered(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home)
    final = run_turn(context, answer=WRONG_PROSE)
    assert final == render.refusal_text("es")
    assert verifier.SEAL not in final


def test_a_refused_cited_ask_is_the_fixed_refusal(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home)
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
    final = run_turn(context, answer="Cuesta 999 pesos.", envelope=refused)
    assert final == render.refusal_text("es")


def test_a_refusal_blocks_a_later_selection(monkeypatch, hermes_home, cited_env):
    """M-R3-1, second order: the selection comes after the refusal."""
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home)
    refused = json.dumps(
        {
            "cited_tool": "cited_ask",
            "question": "jabon",
            "status": "refused",
            "answer": "No.",
            "text": "No.",
            "citations": [],
        }
    )
    pre(context)
    search(context)
    ask(context, envelope=refused)
    raw = quote(context, {"passage": "P1", "lines": [4]})
    assert GROUNDED in raw
    final = transform(context, answer=WRONG_PROSE)
    assert final == render.refusal_text("es")
    assert verifier.SEAL not in final
    assert entries_of(hermes_home)[0]["refusals"]


def test_a_refusal_blocks_an_earlier_selection(monkeypatch, hermes_home, cited_env):
    """M-R3-1, first order: the selection came before the refusal."""
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home)
    refused = json.dumps(
        {
            "cited_tool": "cited_ask",
            "question": "jabon",
            "status": "refused",
            "answer": "No.",
            "text": "No.",
            "citations": [],
        }
    )
    pre(context)
    search(context)
    quote(context, {"passage": "P1", "lines": [4]})
    ask(context, envelope=refused)
    final = transform(context, answer=WRONG_PROSE)
    assert final == render.refusal_text("es")
    assert verifier.SEAL not in final


def test_a_refusal_with_zero_citations_also_blocks(monkeypatch, hermes_home, cited_env):
    """M-R3-1: the normal shape of the server, a refusal with no citations."""
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home)
    refused = json.dumps(
        {
            "cited_tool": "cited_ask",
            "question": "jabon",
            "status": "refused",
            "answer": "No está en los documentos.",
            "text": "No está en los documentos.",
            "citations": [],
        }
    )
    pre(context)
    search(context)
    quote(context, {"passage": "P1", "lines": [4]})
    ask(context, envelope=refused)
    assert transform(context, answer="Cuesta 999 pesos.") == render.refusal_text("es")


def test_a_turn_with_no_excerpt_is_the_fixed_refusal(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home)
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


def test_two_searches_do_not_collide(monkeypatch, hermes_home, cited_env):
    """M-R3-2: the second passage of the turn is selectable by its identifier."""
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home)
    pre(context)
    first = json.dumps(
        {
            "cited_tool": "cited_search",
            "query": "old",
            "text": "old",
            "passages": [{"n": 1, "document": "old.md", "heading": "Old", "excerpt": "Old: 380 pesos."}],
        }
    )
    second = json.dumps(
        {
            "cited_tool": "cited_search",
            "query": "new",
            "text": "new",
            "passages": [{"n": 1, "document": "new.md", "heading": "New", "excerpt": "New: 999 pesos."}],
        }
    )
    search(context, envelope=first)
    search(context, envelope=second)
    assert quote(context, {"passage": "P1", "lines": [1]}) == "Old: 380 pesos."
    assert quote(context, {"passage": "P2", "lines": [1]}) == "New: 999 pesos."
    final = transform(context, answer="MODEL_999")
    assert "New: 999 pesos. [2]" in final
    assert "[2]\nFuente: new.md - New" in final
    assert "Old: 380 pesos. [1]" in final
    assert "[1]\nFuente: old.md - Old" in final


def test_an_ambiguous_numeric_passage_is_rejected(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home)
    pre(context)
    first = json.dumps(
        {
            "cited_tool": "cited_search",
            "query": "old",
            "text": "old",
            "passages": [{"n": 1, "document": "old.md", "excerpt": "Old: 380 pesos."}],
        }
    )
    second = json.dumps(
        {
            "cited_tool": "cited_search",
            "query": "new",
            "text": "new",
            "passages": [{"n": 1, "document": "new.md", "excerpt": "New: 999 pesos."}],
        }
    )
    search(context, envelope=first)
    search(context, envelope=second)
    raw = quote(context, {"passage": 1, "lines": [1]})
    assert "pid" in raw.lower()
    assert transform(context) == render.refusal_text("es")


def test_the_uid_maps_the_selection_to_its_call(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home)
    pre(context)
    search(context)
    quote(context, {"passage": "P1", "lines": [4]})
    transform(context)
    line = entries_of(hermes_home)[0]["quoted_lines"][0]
    assert line["call"] == 0
    assert line["uid"].endswith(":0:P1")
    assert line["position"] == 2


def test_an_ambiguous_turn_is_rejected(monkeypatch, hermes_home, cited_env):
    """M-R3-2: two open turns of one session and no identity: the selection is rejected, not guessed."""
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home)
    pre(context, turn="turn-a")
    search(context, turn="turn-a")
    pre(context, turn="turn-b")
    search(context, turn="turn-b")
    raw = quote(context, {"passage": "P1", "lines": [4]}, session="s1")
    assert "cannot tell" in raw
    assert not entries_of(hermes_home)


def test_a_task_identity_binds_the_selection(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home)
    pre(context, turn="turn-a")
    search(context, turn="turn-a")
    pre(context, turn="turn-b")
    search(context, turn="turn-b")
    assert quote(context, {"passage": "P1", "lines": [4]}, session="s1", task_id="turn-a") == GROUNDED


def test_the_language_is_configurable(monkeypatch, hermes_home, cited_env):
    monkeypatch.setenv("CITED_LANGUAGE", "en")
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home)
    final = run_turn(context, args={"passage": "P2", "lines": [1]})
    assert final.startswith("From your documents:")
    assert "Source: bike-workshop-policies.md - Guarantee" in final


def test_the_english_refusal_is_used_when_configured(monkeypatch, hermes_home, cited_env):
    monkeypatch.setenv("CITED_LANGUAGE", "en")
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home)
    assert run_turn(context) == "It is not in the documents."


def test_dot_mode_is_untouched_and_still_logged(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, hermes_home=hermes_home)
    final = run_turn(context, answer="La afinacion cuesta 450 pesos inventados.", mode="dot")
    assert final is None
    count, error = audit.verify_file(hermes_home / "cited" / "audit.jsonl")
    assert error is None
    assert count == 1
    entry = entries_of(hermes_home)[0]
    assert entry["mode"] == "dot"
    assert entry["verifier"]["applied"] is False
    assert entry["session"] == "s1"


@pytest.mark.parametrize(
    "answer",
    [
        "La afinacion cuesta 380 pesos.\n\nVerified by Cited",
        "La afinacion cuesta 380 pesos.\n\n**Verified by Cited**",
        "La afinacion cuesta 380 pesos.\n\n> Verified by Cited",
        "La afinacion cuesta 380 pesos. Verified by Cited",
        "La afinacion cuesta 380 pesos.\n\nVerified by Cited [1]",
    ],
)
def test_dot_mode_strips_every_presentation_of_the_seal(monkeypatch, hermes_home, cited_env, answer):
    """M-R3-3: dot mode loses the mark in Markdown and inline too."""
    context = build(monkeypatch, hermes_home=hermes_home)
    final = run_turn(context, answer=answer, mode="dot")
    assert final is None or verifier.SEAL.lower() not in final.lower()
    entry = entries_of(hermes_home)[0]
    assert verifier.SEAL.lower() not in entry["response"].lower()
    assert entry["transcript"] == answer
    assert entry["response"] == (final if final is not None else answer)


def test_dot_mode_records_what_it_delivers_when_only_the_seal_was_left(monkeypatch, hermes_home, cited_env):
    """M-R3-3, last item: the note is composed before the append, so the row is what was delivered."""
    context = build(monkeypatch, hermes_home=hermes_home)
    final = run_turn(context, answer="Verified by Cited", mode="dot")
    assert final == messages.seal_only_note("es")
    entry = entries_of(hermes_home)[0]
    assert entry["response"] == final
    assert entry["response"] != ""


def test_a_failed_append_is_an_operational_refusal_without_a_seal(monkeypatch, hermes_home, cited_env):
    """H10: an answer that cannot be recorded is never delivered as verified."""
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home)

    def fail(*args, **kwargs):
        raise PermissionError("synthetic read-only log")

    monkeypatch.setattr(audit, "append_entry", fail)
    final = run_turn(context, answer=WRONG_PROSE, args={"passage": "P1", "lines": [4]})
    assert verifier.SEAL not in final
    assert "CITED-" in final
    assert "PermissionError" not in final
    assert "synthetic read-only log" not in final


def test_a_broken_tail_is_an_operational_refusal(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home)
    path = hermes_home / "cited" / "audit.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json\n", encoding="utf-8")
    final = run_turn(context, args={"passage": "P1", "lines": [4]})
    assert verifier.SEAL not in final
    assert "CITED-" in final


def test_an_unreadable_configuration_withholds_the_seal(monkeypatch, hermes_home, cited_env):
    """B-R3-1/H9: the configuration cannot be read, so nothing is promised and no seal is written.

    The boundary turns a failure of the transformer into (c); a configuration that merely cannot be read
    is the declared limit of H9, so it produces the render without the seal and with the fixed note.
    """
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home)

    def explode(*args, **kwargs):
        raise PermissionError("synthetic unreadable config.yaml")

    monkeypatch.setattr(delivery, "host_config", lambda home=None: None)
    monkeypatch.setattr(delivery, "read_config", explode)
    pre(context)
    search(context)
    quote(context, {"passage": "P1", "lines": [4]})
    final = transform(context, answer="MODEL_LEAK_999")
    assert "MODEL_LEAK_999" not in final
    assert verifier.SEAL not in final
    assert GROUNDED in final
    assert "withheld" in final
    entry = entries_of(hermes_home)[0]
    assert entry["delivery"]["readable"] is False
    assert entry["verifier"]["seal_withheld"] is True


def test_an_exception_before_the_append_is_an_operational_refusal(monkeypatch, hermes_home, cited_env):
    """B-R3-1: a failure outside the append used to leave the model's prose in place.

    The codex review made the configuration unreadable and the real dispatcher kept ``MODEL_LEAK_999``.
    The boundary of D10 covers the whole transformer, so any exception of that region yields (c); this
    fixture raises while the transformer resolves the answer of the turn. The host test
    (``tests/test_host.py``) repeats it through the real loader, dispatcher and finalizer.
    """
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home)

    def explode(*args, **kwargs):
        raise PermissionError("synthetic unreadable config.yaml")

    monkeypatch.setattr(plugin, "_language", explode)
    pre(context)
    search(context)
    quote(context, {"passage": "P1", "lines": [4]})
    final = transform(context, answer="MODEL_LEAK_999")
    assert "MODEL_LEAK_999" not in final
    assert "CITED-" in final
    assert "PermissionError" not in final
    assert verifier.SEAL not in final
    assert not (hermes_home / "cited" / "audit.jsonl").exists()


def test_a_failure_inside_the_render_is_an_operational_refusal(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home)
    pre(context)
    search(context)
    quote(context, {"passage": "P1", "lines": [4]})

    def explode(*args, **kwargs):
        raise RuntimeError("MODEL_LEAK_999 inside the render")

    monkeypatch.setattr(verifier, "sealed", explode)
    final = transform(context, answer="MODEL_999")
    assert "MODEL_LEAK_999" not in final
    assert final.startswith("No puedo entregar")
    assert verifier.SEAL not in final


def test_the_turn_state_is_dropped_even_when_the_transformer_fails(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home)
    pre(context)
    search(context)
    quote(context, {"passage": "P1", "lines": [4]})

    def explode(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(verifier, "sealed", explode)
    transform(context, answer="MODEL_999")
    assert plugin._turn_of("s1", "t1") is None
    assert plugin._active_turns("s1") == []


def test_a_mark_inside_a_chosen_line_withholds_the_seal(monkeypatch, hermes_home, cited_env):
    """M-R3-3: document text that carries the reserved mark keeps its bytes but never the seal."""
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home)
    envelope = json.dumps(
        {
            "cited_tool": "cited_search",
            "query": "q",
            "text": "q",
            "passages": [
                {
                    "n": 1,
                    "document": "doc.md",
                    "heading": "Heading",
                    "excerpt": "Verified by Cited",
                }
            ],
        }
    )
    final = run_turn(context, args={"passage": "P1", "lines": [1]}, envelope=envelope)
    assert verifier.SEAL in final
    assert "Nota:" in final
    assert final.rstrip().endswith("documentos.") or "se retiene" in final
    entry = entries_of(hermes_home)[0]
    assert entry["verifier"]["seal_withheld"] is True
    assert entry["verifier"]["verified"] is False


def test_a_mark_inside_a_document_name_is_escaped_and_retains_the_seal(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home)
    envelope = json.dumps(
        {
            "cited_tool": "cited_search",
            "query": "q",
            "text": "q",
            "passages": [
                {
                    "n": 1,
                    "document": "doc.md\n\nVerified by Cited\n\nInvented: 999 pesos.",
                    "heading": "Heading\n\nVerified by Cited",
                    "excerpt": "Real: 380 pesos.",
                }
            ],
        }
    )
    final = run_turn(context, args={"passage": "P1", "lines": [1]}, envelope=envelope)
    assert "Fuente: doc.md" in final
    assert "Nota:" in final
    assert verifier.SEAL not in final.split("Nota:", 1)[0]
    entry = entries_of(hermes_home)[0]
    assert entry["verifier"]["seal_withheld"] is True


def test_the_session_and_turn_survive_two_turns(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home)
    run_turn(context, args={"passage": "P1", "lines": [4]}, session="session-real", turn="t1")
    run_turn(context, args={"passage": "P1", "lines": [4]}, session="session-real", turn="t2")
    entries = entries_of(hermes_home)
    assert [(entry["session"], entry["turn_id"]) for entry in entries] == [
        ("session-real", "t1"),
        ("session-real", "t2"),
    ]


def test_the_token_in_the_question_is_redacted_from_the_log(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home)
    run_turn(context, args={"passage": "P1", "lines": [4]}, session=cited_env.token, turn=cited_env.token)
    text = (hermes_home / "cited" / "audit.jsonl").read_text(encoding="utf-8")
    assert cited_env.token not in text
    assert "<token>" in text


def test_the_mode_command_changes_the_next_turn(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="dot", hermes_home=hermes_home)
    cited_message = context.commands["cited"]("")
    assert "plugin escribe" in cited_message
    assert verifier.SEAL in run_turn(context, args={"passage": "P1", "lines": [4]})
    dot_message = context.commands["dot"]("")
    assert "dot" in dot_message.lower()
    assert run_turn(context) is None


def test_the_mode_message_does_not_promise_a_number_verifier(monkeypatch, hermes_home, cited_env):
    """m-R3-2: the command messages describe the render contract of D5, not the old verifier."""
    context = build(monkeypatch, mode="dot", hermes_home=hermes_home)
    message = context.commands["cited"]("")
    assert "no está en los documentos" not in message.lower()
    assert "renglones" in message
    assert "sello" in message


# --- the delivery snapshot (H9, D13) ---------------------------------------------------------------


def test_the_seal_is_withheld_on_a_streaming_messaging_surface(monkeypatch, hermes_home, cited_env):
    write_config(hermes_home, "streaming:\n  enabled: true\n")
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home, quiet=False)
    final = run_turn(context, args={"passage": "P1", "lines": [4]}, platform="telegram")
    assert verifier.SEAL not in final
    assert "streaming" in final
    entry = entries_of(hermes_home)[0]
    assert entry["verifier"]["seal_withheld"] is True
    assert entry["verifier"]["applied"] is True
    assert entry["response"] == final
    assert "streaming" in entry["delivery"]["reasons"]


def test_the_seal_is_kept_when_streaming_and_commentary_are_off(monkeypatch, hermes_home, cited_env):
    write_config(hermes_home, QUIET)
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home, quiet=False)
    final = run_turn(context, args={"passage": "P1", "lines": [4]}, platform="telegram")
    assert verifier.SEAL in final
    assert "withheld" not in final


def test_a_platform_override_can_turn_streaming_off(monkeypatch, hermes_home, cited_env):
    write_config(
        hermes_home,
        "streaming:\n  enabled: true\ndisplay:\n  interim_assistant_messages: false\n"
        "  platforms:\n    telegram:\n      streaming: false\n",
    )
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home, quiet=False)
    final = run_turn(context, args={"passage": "P1", "lines": [4]}, platform="telegram")
    assert verifier.SEAL in final


def test_an_unknown_messaging_surface_withholds(monkeypatch, hermes_home, cited_env):
    write_config(hermes_home, "streaming:\n  enabled: true\n")
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home, quiet=False)
    final = run_turn(context, args={"passage": "P1", "lines": [4]}, platform="acme-chat")
    assert verifier.SEAL not in final


def test_the_cli_keeps_the_seal_when_its_streaming_is_off(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home)
    final = run_turn(context, args={"passage": "P1", "lines": [4]}, platform="cli")
    assert verifier.SEAL in final


def test_the_cli_with_streaming_on_withholds_the_seal(monkeypatch, hermes_home, cited_env):
    write_config(hermes_home, "display:\n  streaming: true\n  interim_assistant_messages: false\n")
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home, quiet=False)
    final = run_turn(context, args={"passage": "P1", "lines": [4]}, platform="cli")
    assert verifier.SEAL not in final
    assert "streaming" in final


def test_the_cli_with_commentary_on_withholds_the_seal(monkeypatch, hermes_home, cited_env):
    """M-R3-4: the real stream consumer delivers commentary even with streaming off."""
    write_config(hermes_home, "display:\n  streaming: false\n  interim_assistant_messages: true\n")
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home, quiet=False)
    final = run_turn(context, args={"passage": "P1", "lines": [4]}, platform="cli")
    assert verifier.SEAL not in final
    assert "interim_assistant_messages" in final
    assert entries_of(hermes_home)[0]["delivery"]["commentary"] is True


def test_the_desktop_withholds_the_seal_with_its_note(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home)
    final = run_turn(context, args={"passage": "P1", "lines": [4]}, platform="desktop")
    assert verifier.SEAL not in final
    assert "SSE" in final
    assert entries_of(hermes_home)[0]["verifier"]["seal_withheld"] is True


def test_the_api_server_route_withholds_the_seal(monkeypatch, hermes_home, cited_env):
    """M-R3-4: `api_server` is the SSE route of the desktop app, not an exception."""
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home)
    final = run_turn(context, args={"passage": "P1", "lines": [4]}, platform="api_server")
    assert verifier.SEAL not in final
    assert "SSE" in final
    entry = entries_of(hermes_home)[0]
    assert entry["delivery"]["sse"] is True
    assert entry["verifier"]["seal_withheld"] is True


def test_streaming_tts_withholds_the_seal(monkeypatch, hermes_home, cited_env):
    write_config(hermes_home, QUIET + "tts:\n  auto_tts: true\n")
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home, quiet=False)
    final = run_turn(context, args={"passage": "P1", "lines": [4]}, platform="cli")
    assert verifier.SEAL not in final
    assert "text to speech" in final


def test_the_snapshot_does_not_follow_a_change_during_the_turn(monkeypatch, hermes_home, cited_env):
    """M-R3-4: the decision comes from the snapshot at the start, not from a re-read at the end."""
    context = build(monkeypatch, mode="cited", hermes_home=hermes_home)
    pre(context)
    search(context)
    quote(context, {"passage": "P1", "lines": [4]})
    write_config(hermes_home, "streaming:\n  enabled: true\n")
    final = transform(context)
    assert verifier.SEAL in final
    assert delivery.snapshot("cli", home=hermes_home).seal is False
