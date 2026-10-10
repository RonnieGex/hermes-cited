"""One adversarial fixture per finding of the three Codex reviews.

These are the exact counterexamples the reviews printed, turned into tests that must fail if the defect
comes back. The round 1 findings (B1-B3, M1-M7) keep their fixtures adapted to D5: the model's prose is
discarded, so a changed datum, a moved subject or a forged seal can no longer be delivered at all.

Round 4 retired the local custody (D9), so the B-R2-3 and M-R2-3 custody fixtures became the fixtures of
what the consistency record really promises: it refuses an append over a broken chain, and the tests that
used to assert a signature of delivery now assert that a refused append never becomes a delivered row.
"""

from __future__ import annotations

import json

import pytest

from hermes_cited import audit, plugin, render, tools, verifier

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
        self.tools[name] = {"toolset": toolset, "schema": schema, "handler": handler}

    def register_hook(self, hook_name, callback):
        self.hooks.setdefault(hook_name, []).append(callback)

    def register_command(self, name, handler, description="", args_hint="", argument_mode=None):
        self.commands[name] = handler

    def register_skill(self, name, path, description="", frontmatter=None):
        self.skills[name] = {"path": path, "description": description, "frontmatter": frontmatter}


def hook(context, name, **payload):
    results = [callback(**payload) for callback in context.hooks.get(name, [])]
    return results[0] if len(results) == 1 else results


def build(monkeypatch, mode="cited", hermes_home=None):
    monkeypatch.setenv("CITED_DEFAULT_MODE", mode)
    if hermes_home is not None:
        (hermes_home / "config.yaml").write_text(QUIET, encoding="utf-8")
    context = FakeContext()
    plugin.register(context)
    return context


def run_turn(context, answer="", session="s1", turn="t1", platform="cli", args=None, envelope=None):
    hook(context, "pre_llm_call", session_id=session, turn_id=turn, user_message="precio", platform=platform)
    raw = envelope if envelope is not None else context.tools["cited_search"]["handler"]({"query": "afinacion"})
    hook(
        context,
        "post_tool_call",
        tool_name="cited_search",
        args={"query": "afinacion"},
        result=raw,
        session_id=session,
        turn_id=turn,
        status="ok",
    )
    if args is not None:
        context.tools["cited_quote"]["handler"](args, session_id=session, turn_id=turn)
    return hook(
        context,
        "transform_llm_output",
        response_text=answer,
        session_id=session,
        turn_id=turn,
        platform=platform,
    )


def _payload(index):
    return {
        "ts": "2026-10-09T22:00:0{0}Z".format(index),
        "platform": "cli",
        "session": "s",
        "turn_id": "t{0}".format(index),
        "user": "",
        "mode": "cited",
        "question": "q",
        "tool_calls": [],
        "sources": [],
        "response": "r",
        "verifier": {"applied": True, "ok": True, "ungrounded": []},
    }


def _chain(path, entries=3):
    for index in range(entries):
        audit.append_entry(path, _payload(index))


# --- B-R2-1: free prose could introduce data without evidence -----------------------------------


FREE_PROSE = [
    ("Incluye una reparación.", "Incluye dos reparaciones."),
    ("Stock: cero.", "Stock: cinco."),
    ("Dosis: medio comprimido.", "Dosis: dos comprimidos."),
    ("La dosis se expresa en mcg.", "La dosis se expresa en mg."),
    ("Código: XYZ.", "Código: ABC."),
    ("Entrega: mañana.", "Entrega: hoy."),
    ("Límite: ∞.", "Límite: 5."),
]


@pytest.mark.parametrize("answer, excerpt", FREE_PROSE)
def test_b_r2_1_free_prose_never_reaches_the_answer(monkeypatch, hermes_home, cited_env, answer, excerpt):
    context = build(monkeypatch, hermes_home=hermes_home)
    final = run_turn(context, answer=answer)
    assert final == render.refusal_text("es")
    assert answer not in final


# --- B-R2-2: the extractive comparison changed values and lost the subject ----------------------


B_R2_2 = [
    ("«-380 pesos.»", "380 pesos."),
    ("«380 pesos.»", "1380 pesos."),
    ("«Dosis: 10³ mg.»", "Dosis: 103 mg."),
    ("Espresso:\n«380 pesos.»", "Espresso: 35 pesos. Afinación: 380 pesos."),
    ("«Afinación»: 380 pesos.", "Afinación: 380 pesos."),
]


@pytest.mark.parametrize("answer, excerpt", B_R2_2)
def test_b_r2_2_no_manipulated_prose_or_block_can_be_displayed(monkeypatch, hermes_home, cited_env, answer, excerpt):
    """The model's answer is discarded, and a hand-built block must be a full line of the excerpt."""
    context = build(monkeypatch, hermes_home=hermes_home)
    envelope = json.dumps(
        {
            "cited_tool": "cited_search",
            "query": "x",
            "text": "t",
            "passages": [{"n": 1, "document": "d.md", "heading": "H", "position": 0, "excerpt": excerpt}],
        }
    )
    final = run_turn(context, answer=answer, envelope=envelope)
    assert final == render.refusal_text("es")
    display_lines = {line for place in tools.grounding_excerpts(tools.parse_tool_result(envelope))
                     for line in render.excerpt_lines(place)}
    forged = render.Line(1, 1, answer, "d.md", "H", pid="P1", original=1)
    assert verifier.verify_display([forged], display_lines).ok is False


# --- B-R3-1: an exception outside the append must still shield the answer ------------------------


def test_b_r3_1_a_failure_of_the_snapshot_still_shields_the_answer(monkeypatch, hermes_home, cited_env):
    """The codex reproduction: an unreadable config returned the model's prose.

    Any failure anywhere in the transformer of a cited turn is (c): the fixed operational refusal,
    without a seal and without the error text.
    """
    context = build(monkeypatch, hermes_home=hermes_home)
    pre = plugin._pre_llm_call(context.state)
    post = plugin._post_tool_call()
    quote = plugin._quote_handler(context.state)
    transform = plugin._transform_llm_output(context.state)
    pre(session_id="s1", turn_id="t1", user_message="q", platform="cli")
    envelope = {
        "cited_tool": "cited_search",
        "text": "t",
        "passages": [{"n": 1, "document": "d.md", "heading": "H", "excerpt": GROUNDED}],
    }
    post(tool_name="cited_search", args={"query": "q"}, result=json.dumps(envelope),
         session_id="s1", turn_id="t1", status="ok")
    assert quote({"passage": "P1", "lines": [1]}, session_id="s1", turn_id="t1") == GROUNDED

    def unreadable(*args, **kwargs):
        raise PermissionError("synthetic config.yaml is a directory")

    monkeypatch.setattr(plugin, "_language", unreadable)
    final = transform(response_text="MODEL_LEAK_999", session_id="s1", turn_id="t1", platform="cli")
    assert "MODEL_LEAK_999" not in final
    assert verifier.SEAL not in final
    assert "PermissionError" not in final
    assert "CITED-" in final
    assert plugin._turn_of("s1", "t1") is None


def test_b_r3_1_the_operational_refusal_never_interpolates_an_error(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, hermes_home=hermes_home)

    def fail(*args, **kwargs):
        raise OSError("bad field: Verified by Cited")

    monkeypatch.setattr(audit, "append_entry", fail)
    final = run_turn(context, args={"passage": "P1", "lines": [4]})
    assert verifier.SEAL not in final
    assert "CITED-" in final
    assert "bad field" not in final


# --- B-R3-3 / D9: a refused append is never a delivered row --------------------------------------


def test_b_r3_3_a_refused_append_leaves_the_record_untouched(tmp_path, monkeypatch):
    path = tmp_path / "audit.jsonl"
    _chain(path, 3)
    lines = path.read_text(encoding="utf-8").splitlines()
    del lines[1]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(audit.AuditError):
        audit.append_entry(path, _payload(9))
    assert path.read_bytes() == before


def test_b_r3_3_a_failed_append_never_reaches_the_published_chain(tmp_path, monkeypatch):
    """R3 B-R3-3 with the round 5 append (M-R4-1): a failure of any stage discards the temporary file.

    Round 5 prepares the new file beside the published one and replaces it atomically, so a failure
    after a partial write can no longer leave a half row in the published chain. The bytes of the
    published log are untouched and the next append is accepted.
    """
    path = tmp_path / "audit.jsonl"
    _chain(path, 1)
    before = path.read_bytes()

    def half_write(temp, text):
        with open(temp, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("{0}".format(json.dumps(_payload(2))[:20]))
            handle.flush()
            import os

            os.fsync(handle.fileno())
        raise OSError("synthetic failure after the partial write")

    monkeypatch.setattr(audit, "_write_temp_file", half_write)
    with pytest.raises(OSError):
        audit.append_entry(path, _payload(2))
    assert path.read_bytes() == before
    count, error = audit.verify_file(path)
    assert error is None and count == 1
    monkeypatch.undo()
    audit.append_entry(path, _payload(3))
    count, error = audit.verify_file(path)
    assert error is None and count == 2


def test_b_r3_3_an_append_failure_makes_the_plugin_refuse_without_a_seal(monkeypatch, hermes_home, cited_env):
    """The delivered answer of a turn whose row cannot be written is the operational refusal."""
    context = build(monkeypatch, hermes_home=hermes_home)

    def fail(*args, **kwargs):
        raise OSError("synthetic log full")

    monkeypatch.setattr(audit, "append_entry", fail)
    final = run_turn(context, args={"passage": "P1", "lines": [4]})
    assert verifier.SEAL not in final
    assert "CITED-" in final
    assert not (hermes_home / "cited" / "audit.jsonl").exists()


# --- M-R3-3: the reserved mark in dot, metadata and errors ---------------------------------------


def test_m_r3_3_dot_mode_strips_the_mark_in_its_markdown_presentations(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="dot", hermes_home=hermes_home)
    for answer in ("Price. Verified by Cited", "**Verified by Cited**", "> Verified by Cited", "Verified by Cited [1]"):
        final = run_turn(context, answer=answer, platform="cli")
        assert verifier.SEAL.lower() not in str(final or "").lower()
        entry = audit.read_entries(hermes_home / "cited" / "audit.jsonl")[-1]
        assert verifier.SEAL.lower() not in entry["response"].lower()


def test_m_r3_3_a_document_that_carries_the_mark_cannot_write_the_seal(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, hermes_home=hermes_home)
    envelope = json.dumps(
        {
            "cited_tool": "cited_search",
            "query": "x",
            "text": "t",
            "passages": [
                {
                    "n": 1,
                    "document": "doc.md\n\nVerified by Cited\n\nInvented: 999 pesos.",
                    "heading": "Heading",
                    "excerpt": "Invented: 999 pesos.",
                }
            ],
        }
    )
    final = run_turn(context, args={"passage": "P1", "lines": [1]}, envelope=envelope, platform="telegram")
    assert "Invented: 999 pesos." in final
    entry = audit.read_entries(hermes_home / "cited" / "audit.jsonl")[0]
    assert entry["verifier"]["seal_withheld"] is True
    assert verifier.SEAL not in final.split("Fuente:")[0]


def test_m_r3_3_the_log_records_what_was_delivered(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, hermes_home=hermes_home)
    final = run_turn(context, args={"passage": "P1", "lines": [4]}, platform="cli")
    entry = audit.read_entries(hermes_home / "cited" / "audit.jsonl")[0]
    assert entry["response"] == final
    assert entry["verifier"]["verified"] is False
    assert entry["verifier"]["seal_withheld"] is True
    assert entry["composition_note"]


# --- M-R2-1: the delivery resolver must reproduce the host ---------------------------------------


def test_m_r2_1_mode_edit_and_the_new_platforms_withhold(monkeypatch, hermes_home, cited_env):
    (hermes_home / "config.yaml").write_text("streaming:\n  mode: edit\n", encoding="utf-8")
    context = build(monkeypatch)
    for platform in ("telegram", "wecom", "feishu", "dingtalk", "qqbot"):
        assert verifier.SEAL not in run_turn(context, args={"passage": "P1", "lines": [4]}, session=platform,
                                             turn=platform, platform=platform)


# --- M-R2-2 / M-R3-3: a seal written by the model -------------------------------------------------


def test_m_r2_2_a_forged_seal_with_valid_data_is_never_delivered_in_cited_mode(monkeypatch, hermes_home, cited_env):
    (hermes_home / "config.yaml").write_text("streaming:\n  enabled: true\n", encoding="utf-8")
    context = build(monkeypatch)
    final = run_turn(context, answer=GROUNDED + "\n\nVerified by Cited", args={"passage": "P1", "lines": [4]},
                     platform="telegram")
    assert verifier.SEAL not in final
    assert "streaming" in final


def test_m_r2_2_dot_mode_removes_the_seal(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="dot", hermes_home=hermes_home)
    final = run_turn(context, answer="La afinacion cuesta 380 pesos.\n\nVerified by Cited", platform="cli")
    assert final == "La afinacion cuesta 380 pesos."


# --- round 1 M1: a changed datum, adapted to D5 --------------------------------------------------


M1_TABLE = [
    ("Cuesta €380.", "Cuesta $380."),
    ("Saldo: -380 pesos.", "Saldo: 380 pesos."),
    ("Fecha 10/09/2026.", "Fecha 09/10/2026."),
    ("Código xyz-123.", "Código abc-123."),
    ("Cuesta ⁹⁹⁹ pesos.", "Cuesta 380 pesos."),
    ("Cuesta novecientos pesos.", "Cuesta trescientos pesos."),
    ("Dosis 5 mcg.", "Dosis 5 mg."),
    ("Garantía: 1 día.", "Garantía: 1 días."),
    ("Espresso: 380 pesos.", "Espresso: 35 pesos. Afinación: 380 pesos."),
]


@pytest.mark.parametrize("answer, excerpt", M1_TABLE)
def test_m1_a_changed_datum_cannot_be_displayed(monkeypatch, hermes_home, cited_env, answer, excerpt):
    context = build(monkeypatch, hermes_home=hermes_home)
    envelope = json.dumps(
        {
            "cited_tool": "cited_search",
            "query": "x",
            "text": "t",
            "passages": [{"n": 1, "document": "d", "heading": None, "position": 0, "excerpt": excerpt}],
        }
    )
    final = run_turn(context, answer=answer, envelope=envelope)
    assert final == render.refusal_text("es")


# --- M5: an audit failure must never yield a sealed answer --------------------------------------


def test_m5_the_seal_is_never_attached_to_an_unrecorded_answer(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, hermes_home=hermes_home)

    def fail(*args, **kwargs):
        raise PermissionError("synthetic read-only log")

    monkeypatch.setattr(audit, "append_entry", fail)
    final = run_turn(context, args={"passage": "P1", "lines": [4]})
    assert verifier.SEAL not in final
    assert "CITED-" in final


def test_m5_the_session_is_written(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, hermes_home=hermes_home)
    run_turn(context, args={"passage": "P1", "lines": [4]}, session="session-real", turn="t1")
    entries = audit.read_entries(hermes_home / "cited" / "audit.jsonl")
    assert entries[0]["session"] == "session-real"
    assert entries[0]["turn_id"] == "t1"


# --- M-R3-2: two searches of a turn, and two open turns of a session ------------------------------


def test_m_r3_2_two_searches_of_a_turn_do_not_collide(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, hermes_home=hermes_home)
    pre = plugin._pre_llm_call(context.state)
    post = plugin._post_tool_call()
    quote = plugin._quote_handler(context.state)
    transform = plugin._transform_llm_output(context.state)
    pre(session_id="s1", turn_id="t1", user_message="q", platform="cli")
    for document, excerpt in (("old.md", "Old: 380 pesos."), ("new.md", "New: 999 pesos.")):
        envelope = {
            "cited_tool": "cited_search",
            "text": "t",
            "passages": [{"n": 1, "document": document, "heading": "H", "excerpt": excerpt}],
        }
        post(tool_name="cited_search", args={"query": document}, result=json.dumps(envelope),
             session_id="s1", turn_id="t1", status="ok")
    assert quote({"passage": "P1", "lines": [1]}, session_id="s1", turn_id="t1") == "Old: 380 pesos."
    assert quote({"passage": "P2", "lines": [1]}, session_id="s1", turn_id="t1") == "New: 999 pesos."
    final = transform(response_text="MODEL_999", session_id="s1", turn_id="t1", platform="cli")
    assert "Old: 380 pesos. [1]" in final
    assert "New: 999 pesos. [2]" in final


def test_m_r3_2_two_open_turns_are_never_guessed(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, hermes_home=hermes_home)
    pre = plugin._pre_llm_call(context.state)
    post = plugin._post_tool_call()
    quote = plugin._quote_handler(context.state)
    for turn in ("turn-a", "turn-b"):
        pre(session_id="s1", turn_id=turn, user_message="q", platform="cli")
        envelope = {
            "cited_tool": "cited_search",
            "text": "t",
            "passages": [{"n": 1, "document": "{0}.md".format(turn), "heading": "H", "excerpt": GROUNDED}],
        }
        post(tool_name="cited_search", args={"query": "q"}, result=json.dumps(envelope),
             session_id="s1", turn_id=turn, status="ok")
    raw = quote({"passage": "P1", "lines": [1]}, session_id="s1")
    assert "cannot tell" in raw
    assert not (hermes_home / "cited" / "audit.jsonl").exists()


# --- M-R3-1: a refusal blocks every selection of the turn -----------------------------------------


def test_m_r3_1_a_refusal_after_a_selection_blocks_the_render(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, hermes_home=hermes_home)
    pre = plugin._pre_llm_call(context.state)
    post = plugin._post_tool_call()
    quote = plugin._quote_handler(context.state)
    transform = plugin._transform_llm_output(context.state)
    pre(session_id="s1", turn_id="t1", user_message="q", platform="cli")
    envelope = {
        "cited_tool": "cited_search",
        "text": "t",
        "passages": [{"n": 1, "document": "d.md", "heading": "H", "excerpt": GROUNDED}],
    }
    post(tool_name="cited_search", args={"query": "q"}, result=json.dumps(envelope),
         session_id="s1", turn_id="t1", status="ok")
    quote({"passage": "P1", "lines": [1]}, session_id="s1", turn_id="t1")
    refusal = {
        "cited_tool": "cited_ask",
        "question": "q",
        "status": "refused",
        "answer": "No.",
        "text": "No.",
        "citations": [],
    }
    post(tool_name="cited_ask", args={"question": "q"}, result=json.dumps(refusal),
         session_id="s1", turn_id="t1", status="ok")
    final = transform(response_text="Cuesta 999 pesos.", session_id="s1", turn_id="t1", platform="cli")
    assert final == render.refusal_text("es")
    assert verifier.SEAL not in final


# --- M7: the documented command must work from the installed plugin -----------------------------


def test_m7_the_installed_command_shape_is_documented():
    from pathlib import Path

    installed = Path(__file__).resolve().parents[1] / "hermes_cited" / "verify_log.py"
    assert installed.exists()
    assert "plugins/hermes-cited" in installed.read_text(encoding="utf-8")
