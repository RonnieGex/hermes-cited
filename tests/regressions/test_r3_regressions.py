"""Permanent regressions of the third Codex review: B-R3-1..3, M-R3-1..7 and m-R3-1..2.

Every test names its review and its finding id in the docstring, and the tables of the review are
``parametrize`` cases whose ids name the case. The tests stay at the plugin level: where the finding is
about the real host (M-R3-4's streaming class, M-R3-5's empty response), the docstring points to the
integration evidence of ``tests/test_host.py`` instead of importing the host here. Round 4 (D9) retired the
local custody, so the transaction fixtures of B-R3-2 and B-R3-3 assert the vigente behaviour and say so.
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest

from hermes_cited import audit, delivery, messages, plugin, render, tools, verifier

REPO = Path(__file__).resolve().parents[2]
QUIET = "streaming:\n  enabled: false\ndisplay:\n  streaming: false\n  interim_assistant_messages: false\n"
STREAM = "streaming:\n  enabled: true\n"
GROUNDED = "- Afinacion de bicicleta: 380 pesos."


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


def context(monkeypatch, hermes_home, mode="cited", config=QUIET):
    monkeypatch.setenv("CITED_DEFAULT_MODE", mode)
    if config is not None:
        (hermes_home / "config.yaml").write_text(config, encoding="utf-8")
    ctx = FakeContext()
    plugin.register(ctx)
    return ctx


def hook(ctx, name, **payload):
    results = [callback(**payload) for callback in ctx.hooks.get(name, [])]
    return results[0] if len(results) == 1 else results


def envelope(excerpt, document="d.md", heading="H", number=1):
    return json.dumps(
        {
            "cited_tool": "cited_search",
            "query": "precio",
            "text": "transport",
            "passages": [
                {"n": number, "document": document, "heading": heading, "position": 0, "excerpt": excerpt}
            ],
        }
    )


def refusal_envelope(citations=None, answer="No."):
    return json.dumps(
        {
            "cited_tool": "cited_ask",
            "question": "jabon",
            "status": "refused",
            "answer": answer,
            "text": answer,
            "citations": list(citations or []),
        }
    )


def begin(ctx, session="s1", turn="t1", platform="cli", question="precio"):
    hook(ctx, "pre_llm_call", session_id=session, turn_id=turn, user_message=question, platform=platform)


def post(ctx, raw, session="s1", turn="t1", args=None):
    parsed = tools.parse_tool_result(raw) or {}
    tool_name = parsed.get("cited_tool") or "cited_search"
    hook(ctx, "post_tool_call", tool_name=tool_name, args=args if args is not None else {"query": "precio"},
         result=raw, session_id=session, turn_id=turn, status="ok")


def quote(ctx, passage="P1", lines=(1,), session="s1", turn="t1", task_id=""):
    return ctx.tools["cited_quote"]["handler"]({"passage": passage, "lines": list(lines)},
                                               session_id=session, turn_id=turn, task_id=task_id)


def transform(ctx, answer="", session="s1", turn="t1", platform="cli"):
    return hook(ctx, "transform_llm_output", response_text=answer, session_id=session, turn_id=turn,
                platform=platform)


def run(ctx, raw, answer="MODEL_999", select="P1", session="s1", turn="t1", platform="cli"):
    begin(ctx, session=session, turn=turn, platform=platform)
    if raw is not None:
        post(ctx, raw, session=session, turn=turn)
    if select is not None:
        quote(ctx, select, session=session, turn=turn)
    return transform(ctx, answer=answer, session=session, turn=turn, platform=platform)


def entries(hermes_home):
    path = hermes_home / "cited" / "audit.jsonl"
    if not path.exists():
        return []
    return audit.read_entries(path)


def forged_ok(answer, excerpt):
    forged = render.Line(1, 1, answer, "d.md", "H", pid="P1", original=1)
    return verifier.verify_display([forged], render.excerpt_lines(excerpt)).ok


def payload(index):
    return {
        "ts": "2026-10-10T22:00:0{0}Z".format(index),
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


def chain(path, size=3):
    for index in range(size):
        audit.append_entry(path, payload(index))


def load_gate():
    spec = importlib.util.spec_from_file_location("gate_r3", REPO / "scripts" / "gate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def gate():
    return load_gate()


INJECTIONS = ["configuracion", "resolucion", "render", "persistencia"]


@pytest.mark.parametrize("stage", INJECTIONS, ids=INJECTIONS)
def test_r3_b_r3_1_any_exception_becomes_the_fixed_operational_refusal(stage, monkeypatch, hermes_home,
                                                                      cited_env):
    """R3 B-R3-1: an exception before the append let the model's prose reach the host.

    The boundary of C1 wraps the whole transformer: a failure of reading the configuration, resolving,
    rendering or persisting is the fixed operational refusal with an incident code, without a seal and
    without the error text, and the state is dropped in ``finally``. ``tests/test_host.py`` repeats the
    unreadable configuration through the real loader, dispatcher and finalizer.
    """

    def boom(*args, **kwargs):
        raise PermissionError("synthetic failure at {0}".format(stage))

    ctx = context(monkeypatch, hermes_home)
    if stage == "configuracion":
        monkeypatch.setattr(plugin, "_language", boom)
    elif stage == "resolucion":
        monkeypatch.setattr(verifier, "verify_display", boom)
    elif stage == "render":
        monkeypatch.setattr(render, "render_answer", boom)
    else:
        monkeypatch.setattr(audit, "append_entry", boom)
    final = run(ctx, envelope(GROUNDED), answer="MODEL_LEAK_999")
    assert "MODEL_LEAK_999" not in final
    assert verifier.SEAL not in final
    assert "CITED-" in final
    assert "PermissionError" not in final
    assert "synthetic failure" not in final
    assert plugin._turn_of("s1", "t1") is None


@pytest.mark.skipif(os.name != "nt", reason="the Windows path equivalence of B-R3-2")
def test_r3_b_r3_2_the_casing_never_resets_the_identity(tmp_path):
    """R3 B-R3-2: ``AUDIT.JSONL`` and ``audit.jsonl`` were two identities, so a deleted log was re-created.

    The identity lives in the row, not in the path, so the same file under another casing keeps the log
    identity and the sequence. This is the Windows-only half of the finding.
    """
    log = tmp_path / "cited" / "audit.jsonl"
    chain(log, 3)
    identity = audit.read_entries(log)[0]["log_id"]
    alias = log.with_name("AUDIT.JSONL")
    assert log.samefile(alias)
    entry = audit.append_entry(alias, payload(3))
    assert entry["seq"] == 4
    assert entry["log_id"] == identity
    assert audit.verify_file(log) == (4, None)


def test_r3_b_r3_2_a_vanished_log_starts_a_new_chain_without_a_registry(tmp_path):
    """R3 B-R3-2: the custody registry remembered the identity, and a casing change reset it.

    Round 4 retired the registry (D9), so a log that disappears and comes back empty is a new local chain
    and the record says exactly that; no custody file exists to be reset.
    """
    log = tmp_path / "cited" / "audit.jsonl"
    chain(log, 3)
    old_identity = audit.read_entries(log)[0]["log_id"]
    log.unlink()
    log.with_name("AUDIT.JSONL").write_text("", encoding="utf-8")
    entry = audit.append_entry(log, payload(4))
    assert entry["seq"] == 1
    assert entry["log_id"] != old_identity
    assert audit.verify_file(log) == (1, None)


def test_r3_b_r3_2_there_is_no_identity_registry_to_reset(tmp_path):
    """R3 B-R3-2: the file next to the log is the lock, never a registry or a custody file."""
    log = tmp_path / "audit.jsonl"
    chain(log, 3)
    assert sorted(item.name for item in tmp_path.iterdir() if item.name.startswith("audit")) == [
        "audit.jsonl",
        "audit.jsonl.lock",
    ]


def test_r3_b_r3_3_a_failure_of_the_publication_never_touches_the_published_chain(tmp_path, monkeypatch):
    """R3 B-R3-3: a write that failed after ``write``/``flush`` left a sealed row that was not delivered.

    Round 5 (M-R4-1) prepares the row outside the published file and replaces it as the last step, so a
    failure of any earlier stage leaves the published chain byte-identical and the next append is accepted.
    """
    path = tmp_path / "audit.jsonl"
    chain(path, 1)
    before = path.read_bytes()

    def partial(temp, text):
        with open(temp, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload(2))[:20])
            handle.flush()
            os.fsync(handle.fileno())
        raise OSError("synthetic failure after the partial write")

    monkeypatch.setattr(audit, "_write_temp_file", partial)
    with pytest.raises(OSError):
        audit.append_entry(path, payload(2))
    assert path.read_bytes() == before
    assert audit.verify_file(path) == (1, None)
    monkeypatch.undo()
    audit.append_entry(path, payload(3))
    assert audit.verify_file(path) == (2, None)


def test_r3_b_r3_3_a_failed_append_is_the_operational_refusal(monkeypatch, hermes_home, cited_env):
    """R3 B-R3-3: the row of a response that was not delivered was later authenticated as delivered."""
    ctx = context(monkeypatch, hermes_home)

    def fail(*args, **kwargs):
        raise OSError("synthetic log unavailable")

    monkeypatch.setattr(audit, "append_entry", fail)
    final = run(ctx, envelope(GROUNDED), answer="MODEL_999")
    assert verifier.SEAL not in final
    assert "CITED-" in final
    assert "OSError" not in final
    assert "synthetic log unavailable" not in final


def test_r3_b_r3_3_the_transaction_is_replaced_by_the_consistency_record(monkeypatch, hermes_home, cited_env):
    """R3 B-R3-3 / D9: the custody transaction is gone; what remains is the log and its lock."""
    ctx = context(monkeypatch, hermes_home)
    final = run(ctx, envelope(GROUNDED), answer="MODEL_999")
    assert verifier.SEAL not in final
    assert GROUNDED in final
    storage = hermes_home / "cited"
    assert sorted(item.name for item in storage.iterdir()) == ["audit.jsonl", "audit.jsonl.lock"]
    assert list(hermes_home.rglob("*.checkpoint")) == []
    assert list(hermes_home.rglob("*.key")) == []


REFUSAL_ORDERS = ["seleccion-antes-de-la-negativa", "seleccion-despues-de-la-negativa", "negativa-sin-citas"]


@pytest.mark.parametrize("order", REFUSAL_ORDERS, ids=REFUSAL_ORDERS)
def test_r3_m_r3_1_a_refusal_blocks_every_selection_of_the_turn(order, monkeypatch, hermes_home, cited_env):
    """R3 M-R3-1: ``status: refused`` was recorded but never consulted, so a selection was still sealed.

    A refusal of the turn blocks every selection, before or after it, and with or without citations.
    """
    ctx = context(monkeypatch, hermes_home)
    begin(ctx)
    post(ctx, envelope(GROUNDED))
    if order == "seleccion-antes-de-la-negativa":
        assert GROUNDED in quote(ctx)
        post(ctx, refusal_envelope([{"n": 1, "document": "d.md", "heading": "H", "position": 1,
                                     "excerpt": GROUNDED}]))
    elif order == "seleccion-despues-de-la-negativa":
        post(ctx, refusal_envelope([{"n": 1, "document": "d.md", "heading": "H", "position": 1,
                                     "excerpt": GROUNDED}]))
        assert GROUNDED in quote(ctx)
    else:
        post(ctx, refusal_envelope([]))
        assert GROUNDED in quote(ctx)
    final = transform(ctx, answer="Cuesta 999 pesos.")
    assert final == render.refusal_text("es")
    assert verifier.SEAL not in final
    assert entries(hermes_home)[0]["refusals"]


def test_r3_m_r3_2_two_searches_of_a_turn_do_not_share_a_number(monkeypatch, hermes_home, cited_env):
    """R3 M-R3-2: the first passage 1 of two searches was the only one selectable.

    Every passage carries a per-turn ``pid``, and the secondary passage is selectable by it.
    """
    ctx = context(monkeypatch, hermes_home)
    begin(ctx)
    post(ctx, envelope("Old: 380 pesos.", document="old.md"))
    post(ctx, envelope("New: 999 pesos.", document="new.md"))
    assert quote(ctx, "P1") == "Old: 380 pesos."
    assert quote(ctx, "P2") == "New: 999 pesos."
    final = transform(ctx, answer="MODEL_999")
    assert "Old: 380 pesos. [1]" in final
    assert "New: 999 pesos. [2]" in final


def test_r3_m_r3_2_a_second_passage_line_is_selectable(monkeypatch, hermes_home, cited_env):
    """R3 M-R3-2: a line that did not exist in the first passage was refused even if the second had it."""
    ctx = context(monkeypatch, hermes_home)
    begin(ctx)
    post(ctx, envelope("Old: 380 pesos.", document="old.md"))
    post(ctx, envelope("New: 999 pesos.", document="new.md"))
    assert quote(ctx, "P2", (1,)) == "New: 999 pesos."


def test_r3_m_r3_2_an_ambiguous_number_is_rejected(monkeypatch, hermes_home, cited_env):
    """R3 M-R3-2: the plain number 1 named two passages, so it is rejected instead of guessed."""
    ctx = context(monkeypatch, hermes_home)
    begin(ctx)
    post(ctx, envelope("Old: 380 pesos.", document="old.md"))
    post(ctx, envelope("New: 999 pesos.", document="new.md"))
    raw = quote(ctx, 1)
    assert "pid" in raw.lower()
    assert transform(ctx, answer="MODEL_999") == render.refusal_text("es")


def test_r3_m_r3_2_two_open_turns_are_never_guessed(monkeypatch, hermes_home, cited_env):
    """R3 M-R3-2: an interleaved selection of two open turns picked the last one and sealed it."""
    ctx = context(monkeypatch, hermes_home)
    for turn in ("turn-a", "turn-b"):
        begin(ctx, turn=turn)
        post(ctx, envelope(GROUNDED, document="{0}.md".format(turn)), turn=turn)
    raw = quote(ctx, "P1", session="s1")
    # H14/M02-B2R1: the helper passes an explicit identity (``t1``) that resolves to no open turn, so the
    # refusal names the unmatched execution identity. Without any identity the two open turns are still
    # refused as ambiguous. Neither form is guessed and neither records anything.
    assert "cannot bind this selection to the execution identity" in raw
    assert "cannot tell" in quote(ctx, "P1", session="s1", turn="", task_id="")
    assert entries(hermes_home) == []


def test_r3_m_r3_2_the_execution_identity_binds_the_selection(monkeypatch, hermes_home, cited_env):
    """R3 M-R3-2: with an identity of the execution, the selection is bound instead of refused.

    R01-B2R2 fixed the precedence between the two identity fields: a present ``turn_id`` is authoritative
    and a failed primary is never replaced by the ``task_id`` of the same call (see
    ``tests/test_bridge2_amendments.py::test_unmatched_primary_identity_cannot_fall_through_to_live_task``).
    The helper's default ``turn_id`` is therefore cleared here so the task identity is exercised alone.
    """
    ctx = context(monkeypatch, hermes_home)
    for turn in ("turn-a", "turn-b"):
        begin(ctx, turn=turn)
        post(ctx, envelope(GROUNDED, document="{0}.md".format(turn)), turn=turn)
    assert quote(ctx, "P1", session="s1", turn="", task_id="turn-a") == GROUNDED


DOT_TEXTS = [
    ("marca-sola", "Verified by Cited"),
    ("marca-en-renglon", "Price.\n\nVerified by Cited"),
    ("marca-en-negrita", "**Verified by Cited**"),
    ("texto-legitimo", "The identifier is Verified*by*Cited and must stay."),
]


@pytest.mark.parametrize("case_id,answer", DOT_TEXTS, ids=[case[0] for case in DOT_TEXTS])
def test_r3_m_r3_3_dot_mode_delivers_the_text_intact(case_id, answer, monkeypatch, hermes_home, cited_env):
    """D12 supersedes R3 M-R3-3: with no seal emitted there is no mark to remove, and dot passes it through.

    The round 3 finding was that the mark survived in dot mode. With D11 the plugin writes no seal at all, so
    D12 delivers and records the text byte for byte, whatever it says.
    """
    ctx = context(monkeypatch, hermes_home, mode="dot")
    begin(ctx)
    final = transform(ctx, answer=answer)
    assert final is None
    entry = entries(hermes_home)[0]
    assert entry["response"] == answer
    assert entry["transcript"] == answer


def test_r3_m_r3_3_a_dot_answer_that_is_only_the_mark_is_recorded_as_written(monkeypatch, hermes_home,
                                                                             cited_env):
    """D12 supersedes R3 M-R3-3: the row records the text the host keeps, not a note that replaced it."""
    ctx = context(monkeypatch, hermes_home, mode="dot")
    begin(ctx)
    final = transform(ctx, answer="Verified by Cited")
    assert final is None
    assert entries(hermes_home)[0]["response"] == "Verified by Cited"


METADATA_CASES = ["documento", "seccion"]


@pytest.mark.parametrize("case_id", METADATA_CASES, ids=METADATA_CASES)
def test_r3_m_r3_3_a_mark_in_the_metadata_is_escaped_data(case_id, monkeypatch, hermes_home, cited_env):
    """R3 M-R3-3 / D12: the metadata is escaped into one line and the phrase in it is data.

    The injection defect of round 3 stays closed: a metadata value cannot add a body or a heading. With no
    seal to protect, the phrase in the metadata is ordinary data and the answer carries the general note.
    """
    ctx = context(monkeypatch, hermes_home)
    if case_id == "documento":
        raw = envelope("Real: 380 pesos.",
                       document="doc.md\n\nVerified by Cited\n\nInvented: 999 pesos.", heading="Heading")
    else:
        raw = envelope("Real: 380 pesos.", document="doc.md", heading="Heading\n\nVerified by Cited")
    final = run(ctx, raw)
    entry = entries(hermes_home)[0]
    assert entry["verifier"]["seal_withheld"] is True
    assert entry["verifier"]["verified"] is False
    assert "\n\nVerified by Cited\n\n" not in final
    assert "Note on delivery:" in final


def test_r3_m_r3_3_a_line_that_is_the_mark_is_data_without_a_seal(monkeypatch, hermes_home, cited_env):
    """R3 M-R3-3 / D12: a documentary line that carries the phrase is data, with the general note."""
    ctx = context(monkeypatch, hermes_home)
    final = run(ctx, envelope("Verified by Cited"))
    entry = entries(hermes_home)[0]
    assert entry["verifier"]["verified"] is False
    assert entry["verifier"]["seal_withheld"] is True
    assert "\n\nVerified by Cited\n\n" not in final
    assert "Note on delivery:" in final
    assert entry["response"] == final


def test_r3_m_r3_3_an_error_that_carries_the_mark_is_never_interpolated(monkeypatch, hermes_home, cited_env):
    """R3 M-R3-3: the operational refusal interpolated the error, which carried the reserved mark."""
    ctx = context(monkeypatch, hermes_home)

    def fail(*args, **kwargs):
        raise OSError("bad field: Verified by Cited")

    monkeypatch.setattr(audit, "append_entry", fail)
    final = run(ctx, envelope(GROUNDED), answer="MODEL_999")
    assert verifier.SEAL not in final
    assert "bad field" not in final
    assert "OSError" not in final
    assert "CITED-" in final


SURFACES = [
    ("api-server", QUIET, "api_server", "SSE"),
    ("escritorio", QUIET, "desktop", "SSE"),
    ("tts", QUIET + "tts:\n  auto_tts: true\n", "cli", "text to speech"),
    ("comentarios", "display:\n  streaming: false\n  interim_assistant_messages: true\n", "cli",
     "interim_assistant_messages"),
    ("plataforma-desconocida", STREAM, "acme-chat", "not one the plugin can resolve"),
]


@pytest.mark.parametrize("case_id,config,platform,needle", SURFACES, ids=[case[0] for case in SURFACES])
def test_r3_m_r3_4_every_delivering_surface_withholds_the_seal(case_id, config, platform, needle, monkeypatch,
                                                               hermes_home, cited_env):
    """R3 M-R3-4: the class was right, but ``api_server`` was allowed, TTS and commentary were ignored.

    The snapshot withholds the seal on the SSE route of the desktop, on streaming text to speech and on
    interim commentary, and on a platform it cannot resolve.
    """
    ctx = context(monkeypatch, hermes_home, config=config)
    final = run(ctx, envelope(GROUNDED), platform=platform)
    assert verifier.SEAL not in final
    assert needle in final
    assert entries(hermes_home)[0]["verifier"]["seal_withheld"] is True


def test_r3_m_r3_4_the_decision_is_a_snapshot_taken_at_the_start(monkeypatch, hermes_home, cited_env):
    """R3 M-R3-4: the decision was re-read from the YAML at the end of the turn."""
    ctx = context(monkeypatch, hermes_home)
    begin(ctx)
    post(ctx, envelope(GROUNDED))
    quote(ctx)
    (hermes_home / "config.yaml").write_text(STREAM, encoding="utf-8")
    final = transform(ctx, answer="MODEL_999")
    assert verifier.SEAL not in final
    assert "streaming" not in final
    assert entries(hermes_home)[0]["delivery"]["streaming"] is False
    assert delivery.snapshot("cli", home=hermes_home).surface_clear is False


def test_r3_m_r3_5_the_closure_composes_an_empty_response(monkeypatch, hermes_home, cited_env):
    """R3 M-R3-5: the real finalizer returns before the hook when the model response is empty.

    This asserts the contract of the closure, which composes the render out of the selection even for an
    empty model text. The host incompatibility itself is proven by the integration test of the real
    finalizer in ``tests/test_host.py`` (``test_the_host_never_calls_the_hook_for_an_empty_response``).
    """
    ctx = context(monkeypatch, hermes_home)
    final = run(ctx, envelope(GROUNDED), answer="")
    assert final != ""
    assert GROUNDED in final
    assert entries(hermes_home)[0]["response"] == final


GATE_NEGATIVES = [
    ("signo-negativo", "amount_with_citation", ("-380 pesos [99].", "380"), False),
    ("duracion-negativa", "amount_with_unit", ("-90 days", "90", "day"), False),
    ("unidad-de-otra-clase", "amount_with_citation", ("380 kg, pesos [99]", "380"), False),
    ("cita-ligada", "amount_with_citation", ("380 pesos [1].", "380"), True),
]


@pytest.mark.parametrize("case_id,function,arguments,expected", GATE_NEGATIVES,
                         ids=[case[0] for case in GATE_NEGATIVES])
def test_r3_m_r3_6_the_gate_no_longer_accepts_the_review_counterexamples(gate, case_id, function, arguments,
                                                                        expected):
    """R3 M-R3-6: the sign was ignored, a nearby unit of another class passed and any mark was a citation."""
    assert getattr(gate, function)(*arguments) is expected


def test_r3_m_r3_6_the_citation_must_be_the_mark_of_the_selection(gate):
    """R3 M-R3-6: any mark passed ``amount_with_citation``; the bound statement needs the resolved one."""
    assert gate.amount_statement("380 pesos [99].", "380", unit="currency", mark=1) is False
    assert gate.amount_statement("380 pesos [1].", "380", unit="currency", mark=1) is True


def test_r3_m_r3_6_every_block_is_bound_to_its_own_turn(gate):
    """R3 M-R3-6, M-R4-7 and M-R5-4: the block resolves against its own evidence row and its whole render."""
    line = {
        "pid": "P1",
        "uid": "t1:0:P1",
        "call": 0,
        "original": 1,
        "number": 1,
        "text": "- Afinacion de bicicleta: 380 pesos.",
        "document": "cafe-la-horquilla.md",
        "heading": "Precios",
        "position": 2,
    }
    entry = {
        "turn_id": "t1",
        "mode": "cited",
        "response": "Según tus documentos:\n\n- Afinacion de bicicleta: 380 pesos. [1]\n"
                    "Fuente: cafe-la-horquilla.md - Precios\n\nNote on delivery: withheld",
        "evidence": [
            {
                "call": 0,
                "pid": "P1",
                "uid": "t1:0:P1",
                "number": 1,
                "document": "cafe-la-horquilla.md",
                "heading": "Precios",
                "position": 2,
                "lines": [{"line": 1, "text": "- Afinacion de bicicleta: 380 pesos."}],
            }
        ],
        "quoted_lines": [dict(line)],
        "tool_calls": [{"excerpt_texts": ["Precios\n- Afinacion de bicicleta: 380 pesos."]}],
    }
    assert gate.blocks_are_bound(entry, entry["quoted_lines"][0]) is True
    assert gate.blocks_are_bound(dict(entry, turn_id="t2"), entry["quoted_lines"][0]) is False
    assert gate.blocks_are_bound(entry, dict(entry["quoted_lines"][0], pid="")) is False
    assert gate.blocks_are_bound(entry, dict(entry["quoted_lines"][0], document="otro.md")) is False
    wrong_call = dict(entry["quoted_lines"][0], call=9, uid="t1:9:P1")
    assert gate.blocks_are_bound(entry, wrong_call) is False
    assert gate.blocks_are_bound(entry, dict(entry["quoted_lines"][0], number=999)) is False
    assert gate.blocks_are_bound(entry, dict(entry["quoted_lines"][0], original=999)) is False


def test_r3_m_r3_6_the_terminal_record_names_its_scope(gate):
    """R3 M-R3-6: ``delivered_of`` selected the terminal event of a list, not the real deliveries."""
    assert "terminal" in (gate.terminal_record_of.__doc__ or "").lower()
    events = [
        {"type": "text", "text": "unverified 999"},
        {"type": "result", "text": "380 pesos [1]\n\nVerified by Cited"},
    ]
    assert "999" not in gate.terminal_record_of(events)


def test_r3_m_r3_6_the_selftest_carries_the_new_negatives():
    """R3 M-R3-6: the self-test returned true over the new false positives.

    The full run lives in ``tests/test_gate.py``; this guards that the review's counterexamples remain the
    gate's own cases.
    """
    source = (REPO / "scripts" / "gate.py").read_text(encoding="utf-8")
    assert "gate_selftest" in source
    assert "-380 pesos [99]." in source
    assert "-90 days" in source
    assert "380 kg, pesos [99]" in source


def test_r3_m_r3_7_the_active_changes_stay_within_the_limit():
    """R3 M-R3-7: three open changes exceeded the maximum of two and nothing was archived."""
    changes = REPO / "openspec" / "changes"
    active = sorted(item.name for item in changes.iterdir() if item.is_dir() and item.name != "archive")
    assert len(active) <= 2
    assert (changes / "archive").is_dir()


BAD_INDEXES = [0, -1, True, False, 1.5, 999999, "²", "９", "9" * 5000, "P" * 40, "", None, {}, [], "P1 P2"]


@pytest.mark.parametrize("bad", BAD_INDEXES, ids=[repr(value)[:20] for value in BAD_INDEXES])
def test_r3_m_r3_1_cited_quote_never_raises_on_a_bad_passage(bad, monkeypatch, hermes_home, cited_env):
    """R3 m-R3-1: ``str.isdigit()`` accepted ``²`` and a five-thousand-digit string escaped the handler."""
    ctx = context(monkeypatch, hermes_home)
    begin(ctx)
    post(ctx, envelope(GROUNDED))
    raw = quote(ctx, bad)
    assert isinstance(raw, str)


@pytest.mark.parametrize("bad", BAD_INDEXES, ids=[repr(value)[:20] for value in BAD_INDEXES])
def test_r3_m_r3_1_cited_quote_never_raises_on_a_bad_line(bad, monkeypatch, hermes_home, cited_env):
    """R3 m-R3-1: the same acceptance reached every element of ``lines``."""
    ctx = context(monkeypatch, hermes_home)
    begin(ctx)
    post(ctx, envelope(GROUNDED))
    raw = quote(ctx, "P1", (bad,))
    assert isinstance(raw, str)


def test_r3_m_r3_2_the_command_message_describes_the_render_contract():
    """m-R3-2: ``/cited`` still promised a number verifier and a refusal that names the data."""
    message = messages.mode_text("es", "cited")
    assert "renglones" in message
    assert "sello" in message
    assert "no verificados" not in message.lower()


def test_r3_m_r3_2_the_quote_tool_is_a_local_selection():
    """m-R3-2: the three tools were presented as if all of them called the network."""
    assert "plugin writes the answer" in tools.QUOTE_DESCRIPTION
    assert "POST" not in tools.QUOTE_DESCRIPTION
    assert tools.TOOL_NAMES == ("cited_search", "cited_ask", "cited_quote")


R3_MATRIX = [
    ("moneda", "Cuesta €380.", "Cuesta $380."),
    ("signo", "Saldo: -380 pesos.", "Saldo: 380 pesos."),
    ("decimal", "Dosis 1.200 mg.", "Dosis 1200 mg."),
    ("superindice", "Cuesta ⁹⁹⁹ pesos.", "Cuesta 380 pesos."),
    ("fullwidth", "Cuesta ３８０ pesos.", "Cuesta 380 pesos."),
    ("miles", "Cuesta 1\u202f200 pesos.", "Cuesta 1200 pesos."),
    ("plural", "Garantía: 1 día.", "Garantía: 1 días."),
    ("fecha", "Fecha 10/09/2026.", "Fecha 09/10/2026."),
    ("codigo", "Código xyz-123.", "Código abc-123."),
    ("numeral-escrito", "Cuesta novecientos pesos.", "Cuesta trescientos pesos."),
    ("unidad", "Dosis 5 mcg.", "Dosis 5 mg."),
    ("sujeto", "Espresso: 380 pesos.", "Espresso: 35 pesos. Afinación: 380 pesos."),
    ("cita", "Cuesta 380 pesos [1].", "Cuesta 380 pesos."),
    ("mayusculas", "CUESTA 380 PESOS.", "Cuesta 380 pesos."),
    ("prosa-libre-una", "Incluye una reparación.", "Incluye dos reparaciones."),
    ("prosa-libre-cero", "Stock: cero.", "Stock: cinco."),
    ("prosa-libre-medio", "Dosis: medio comprimido.", "Dosis: dos comprimidos."),
    ("prosa-libre-unidad", "La dosis se expresa en mcg.", "La dosis se expresa en mg."),
    ("prosa-libre-codigo", "Código: XYZ.", "Código: ABC."),
    ("prosa-libre-fecha", "Entrega: mañana.", "Entrega: hoy."),
    ("prosa-libre-porcentaje", "Descuento: cien\u200bto por ciento.", "Sin descuento."),
    ("prosa-libre-fraccion", "Descuento: ⅓.", "Sin descuento."),
    ("prosa-libre-infinito", "Límite: ∞.", "Límite: 5."),
    ("menos-inicial", "«-380 pesos.»", "380 pesos."),
    ("exponente", "«Dosis: 10³ mg.»", "Dosis: 103 mg."),
    ("subindice", "«Código: H₂O.»", "Código: H2O."),
    ("subcadena", "«380 pesos.»", "1380 pesos."),
    ("sujeto-separado", "Espresso:\n«380 pesos.»", "Espresso: 35 pesos. Afinación: 380 pesos."),
    ("dato-fuera-de-comillas", "«Afinación»: 380 pesos.", "Afinación: 380 pesos."),
    ("comilla-parcial", "Cuesta «380» pesos.", "Cuesta 380 pesos."),
    ("dato-entre-corchetes", "Cantidad: [1].", "Cantidad: 5."),
]

MATRIX_PARAMS = []
for _case_id, _answer, _excerpt in R3_MATRIX:
    MATRIX_PARAMS.append(pytest.param(_answer, _excerpt, id=_case_id))
    MATRIX_PARAMS.append(pytest.param("«{0}»".format(_answer), _excerpt, id="{0}-entre-comillas".format(_case_id)))


@pytest.mark.parametrize("answer,excerpt", MATRIX_PARAMS)
def test_r3_the_whole_data_matrix_of_r1_and_r2(answer, excerpt, monkeypatch, hermes_home, cited_env):
    """R3, matriz de datos de R1/R2: 31 cases run bare and wrapped in ``«...»``.

    Every falsified block is rejected, no selection is the fixed refusal, and the chosen line is copied out
    of the excerpt with its document.
    """
    assert forged_ok(answer, excerpt) is False
    ctx = context(monkeypatch, hermes_home)
    raw = envelope(excerpt)
    assert run(ctx, raw, answer=answer, select=None) == render.refusal_text("es")
    final = run(ctx, raw, answer=answer, session="s2", turn="t2")
    assert render.excerpt_lines(excerpt)[0] in final
    assert answer not in final
