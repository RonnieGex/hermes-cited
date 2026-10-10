"""Permanent regressions of the second Codex review: B-R2-1..3, M-R2-1..5 and m-R2-1.

Every test names its review and its finding id in the docstring. Round 4 (D9) retired the local custody, so
where R2 asked for a key, a checkpoint or a high-water mark the test asserts what the product does today and
says so: the hash-chained consistency record, the fixed operational refusal without a seal when the append
fails, and the declared limit that a rewritten chain stays internally consistent. Every run uses the
temporary ``HERMES_HOME`` of the fixtures.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from hermes_cited import audit, delivery, plugin, render, tools, verifier

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


def envelope(excerpt, document="d.md", heading="H", text="transport"):
    return json.dumps(
        {
            "cited_tool": "cited_search",
            "query": "precio",
            "text": text,
            "passages": [
                {"n": 1, "document": document, "heading": heading, "position": 0, "excerpt": excerpt}
            ],
        }
    )


def run(ctx, raw, answer="", select=None, session="s1", turn="t1", platform="cli", question="precio",
        args=None):
    parsed = tools.parse_tool_result(raw) or {}
    tool_name = parsed.get("cited_tool") or "cited_search"
    hook(ctx, "pre_llm_call", session_id=session, turn_id=turn, user_message=question, platform=platform)
    hook(ctx, "post_tool_call", tool_name=tool_name,
         args=args if args is not None else {"query": question}, result=raw,
         session_id=session, turn_id=turn, status="ok")
    if select is not None:
        ctx.tools["cited_quote"]["handler"]({"passage": select, "lines": [1]}, session_id=session,
                                            turn_id=turn)
    return hook(ctx, "transform_llm_output", response_text=answer, session_id=session, turn_id=turn,
                platform=platform)


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


def chain(path, entries=3):
    for index in range(entries):
        audit.append_entry(path, payload(index))


def attempt(path):
    try:
        audit.append_entry(path, payload(9))
        return "appended"
    except audit.AuditError:
        return "refused"


def load_gate():
    spec = importlib.util.spec_from_file_location("gate_r2", REPO / "scripts" / "gate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def gate():
    return load_gate()


B_R2_1 = [
    ("reparacion", "Incluye una reparación.", "Incluye dos reparaciones."),
    ("cero", "Stock: cero.", "Stock: cinco."),
    ("medio", "Dosis: medio comprimido.", "Dosis: dos comprimidos."),
    ("unidad-sin-cantidad", "La dosis se expresa en mcg.", "La dosis se expresa en mg."),
    ("codigo-sin-digitos", "Código: XYZ.", "Código: ABC."),
    ("fecha-relativa", "Entrega: mañana.", "Entrega: hoy."),
    ("infinito", "Límite: ∞.", "Límite: 5."),
    ("fraccion", "Descuento: ⅓.", "Sin descuento."),
    ("porcentaje-con-zwsp", "Descuento: cien\u200bto por ciento.", "Sin descuento."),
]


@pytest.mark.parametrize("case_id,answer,excerpt", B_R2_1, ids=[case[0] for case in B_R2_1])
def test_b_r2_1_free_prose_can_never_introduce_a_datum(case_id, answer, excerpt, monkeypatch, hermes_home,
                                                       cited_env):
    """R2 B-R2-1: free prose introduced data that no passage held.

    D5 discards the model's text whole, so none of these sentences is delivered: without a selection the
    fixed refusal is; a forged block is not a full line of the excerpt.
    """
    assert forged_ok(answer, excerpt) is False
    ctx = context(monkeypatch, hermes_home)
    final = run(ctx, envelope(excerpt), answer=answer)
    assert final == render.refusal_text("es")
    assert answer not in final


B_R2_2 = [
    ("menos-inicial", "«-380 pesos.»", "380 pesos."),
    ("subcadena", "«380 pesos.»", "1380 pesos."),
    ("exponente", "«Dosis: 10³ mg.»", "Dosis: 103 mg."),
    ("sujeto-separado", "Espresso:\n«380 pesos.»", "Espresso: 35 pesos. Afinación: 380 pesos."),
    ("dato-fuera-de-comillas", "«Afinación»: 380 pesos.", "Afinación: 380 pesos."),
    ("comilla-parcial", "Cuesta «380» pesos.", "Cuesta 380 pesos."),
    ("dato-entre-corchetes", "Cantidad: [1].", "Cantidad: 5."),
    ("subindice", "«Código: H₂O.»", "Código: H2O."),
]


@pytest.mark.parametrize("case_id,answer,excerpt", B_R2_2, ids=[case[0] for case in B_R2_2])
def test_b_r2_2_the_block_comparison_keeps_the_value_and_the_subject(case_id, answer, excerpt, monkeypatch,
                                                                     hermes_home, cited_env):
    """R2 B-R2-2: the extractive comparison changed values and lost the subject.

    The comparison of D5 is by construction over whole lines: a hand-built block is rejected, and the chosen
    line is copied out of the excerpt with its document.
    """
    assert forged_ok(answer, excerpt) is False
    ctx = context(monkeypatch, hermes_home)
    raw = envelope(excerpt)
    assert run(ctx, raw, answer=answer) == render.refusal_text("es")
    final = run(ctx, raw, answer=answer, select="P1", session="s2", turn="t2")
    assert render.excerpt_lines(excerpt)[0] in final
    assert answer not in final


def _alter(path, variant):
    rows = path.read_text(encoding="utf-8").splitlines()
    if variant == "fila-intermedia":
        del rows[1]
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    elif variant == "reordenar":
        rows[1], rows[2] = rows[2], rows[1]
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    elif variant == "alterada-sin-recalcular":
        entry = json.loads(rows[0])
        entry["response"] = "tampered"
        rows[0] = json.dumps(entry, ensure_ascii=False, sort_keys=True)
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    elif variant == "json-invalido":
        path.write_text(path.read_text(encoding="utf-8") + "{broken\n", encoding="utf-8")
    elif variant == "quitar-ultima-fila":
        path.write_text("\n".join(rows[:-1]) + "\n", encoding="utf-8")
    elif variant == "cortar-sufijo":
        path.write_text("\n".join(rows[:1]) + "\n", encoding="utf-8")
    elif variant == "reescribir-y-recalcular":
        entries = audit.read_entries(path)
        previous = audit.GENESIS
        for entry in entries:
            entry["response"] = "tampered"
            entry["prev_hash"] = previous
            entry["hash"] = audit.entry_hash(entry)
            previous = entry["hash"]
        path.write_text(
            "\n".join(json.dumps(entry, ensure_ascii=False, sort_keys=True) for entry in entries) + "\n",
            encoding="utf-8",
        )
    elif variant == "log-vacio":
        path.write_text("", encoding="utf-8")
    elif variant == "log-borrado":
        path.unlink()


BROKEN = ["fila-intermedia", "reordenar", "alterada-sin-recalcular", "json-invalido"]


@pytest.mark.parametrize("variant", BROKEN, ids=BROKEN)
def test_b_r2_3_a_broken_chain_refuses_the_append_and_stays_untouched(variant, tmp_path):
    """R2 B-R2-3: a manipulated history was re-authenticated by the next append.

    The append validates the whole chain before writing one byte and never restarts from genesis, so the
    broken log refuses it and keeps its bytes.
    """
    path = tmp_path / "audit.jsonl"
    chain(path)
    _alter(path, variant)
    before = path.read_bytes()
    assert audit.verify_file(path)[1] is not None
    assert attempt(path) == "refused"
    assert path.read_bytes() == before


LIMIT = ["quitar-ultima-fila", "cortar-sufijo", "reescribir-y-recalcular", "log-vacio", "log-borrado"]


@pytest.mark.parametrize("variant", LIMIT, ids=LIMIT)
def test_b_r2_3_a_manipulated_but_consistent_chain_is_the_declared_limit(variant, tmp_path):
    """R2 B-R2-3: the checkpoint used to reject a tail cut, a rewrite and a genesis restart.

    Round 4 retired the local custody (D9), so the record proves internal consistency only. The test asserts
    the honest outcome: a shorter or recomputed chain verifies, an append continues it instead of refusing,
    and a file that vanished starts a fresh chain because there is no registry to remember it.
    """
    path = tmp_path / "audit.jsonl"
    chain(path)
    _alter(path, variant)
    count, error = audit.verify_file(path)
    first = path.exists() and bool(path.read_text(encoding="utf-8").strip())
    if first:
        assert error is None
    else:
        assert error is not None
    assert attempt(path) == "appended"
    after_count, after_error = audit.verify_file(path)
    assert after_error is None
    expected = {
        "quitar-ultima-fila": 3,
        "cortar-sufijo": 2,
        "reescribir-y-recalcular": 4,
        "log-vacio": 1,
        "log-borrado": 1,
    }
    assert after_count == expected[variant]


def test_b_r2_3_no_custody_file_is_created(monkeypatch, tmp_path):
    """R2 B-R2-3: there is no key, no checkpoint, no high-water mark and no registry any more (D9)."""
    key = tmp_path / "audit.key"
    monkeypatch.setenv("CITED_AUDIT_KEY_PATH", str(key))
    log = tmp_path / "cited" / "audit.jsonl"
    chain(log)
    assert audit.verify_file(log) == (3, None)
    assert sorted(item.name for item in log.parent.iterdir()) == ["audit.jsonl", "audit.jsonl.lock"]
    assert not key.exists()
    assert not Path("{0}.checkpoint".format(log)).exists()


def test_b_r2_3_a_failed_append_never_publishes_the_answer(monkeypatch, hermes_home, cited_env):
    """R2 B-R2-3: a write that failed left a row that the next append signed as delivered."""
    ctx = context(monkeypatch, hermes_home)

    def fail(*args, **kwargs):
        raise OSError("synthetic log full")

    monkeypatch.setattr(audit, "append_entry", fail)
    final = run(ctx, envelope(GROUNDED), answer="MODEL_999", select="P1")
    assert verifier.SEAL not in final
    assert "CITED-" in final
    assert not (hermes_home / "cited" / "audit.jsonl").exists()


def test_b_r2_3_a_partial_row_in_the_published_chain_is_detected(tmp_path):
    """R2 B-R2-3: a partial write that reached the published chain must block the next append.

    Round 5 (M-R4-1) prepares the row outside the published file, so this starts from a hand-broken
    published chain (the shape a crash between write and flush used to leave) and asserts the detection.
    """
    path = tmp_path / "audit.jsonl"
    chain(path, 1)
    with open(path, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload(2))[:20])
    before = path.read_bytes()
    assert audit.verify_file(path)[1] is not None
    assert attempt(path) == "refused"
    assert path.read_bytes() == before


HOST_MATRIX = [
    ("mode-edit", {"mode": "edit"}, True),
    ("enabled-true", {"enabled": True}, True),
    ("transporte-apagado", {"enabled": True, "transport": False}, False),
    ("apagado-explicito", {"enabled": False}, False),
]


@pytest.mark.parametrize("case_id,raw,transmitted", HOST_MATRIX, ids=[case[0] for case in HOST_MATRIX])
def test_m_r2_1_the_resolver_matches_the_effective_host_configuration(case_id, raw, transmitted):
    """R2 M-R2-1: ``mode: edit`` implies enabled and ``transport: false`` really is off.

    The plugin resolves the same truth the host does; since D11/H16 the readable surface being clean is not
    enough to emit the seal, so the assertion names both halves.
    """
    config = {"streaming": raw, "display": {"interim_assistant_messages": False}}
    assert delivery.effective_streaming("telegram", config) is transmitted
    assert delivery.snapshot("telegram", config=config).surface_clear is (not transmitted)
    assert delivery.seal_allowed("telegram", config) is False


@pytest.mark.parametrize("platform", ["wecom", "feishu", "dingtalk", "qqbot"],
                         ids=["wecom", "feishu", "dingtalk", "qqbot"])
def test_m_r2_1_the_new_messaging_platforms_withhold_with_streaming(platform):
    """R2 M-R2-1: the delivery list omitted ``wecom``, ``feishu``, ``dingtalk`` and ``qqbot``."""
    config = {"streaming": {"enabled": True}, "display": {"interim_assistant_messages": False}}
    snap = delivery.snapshot(platform, config=config)
    assert snap.seal is False
    assert "streaming" in snap.reasons


def test_m_r2_1_an_unknown_platform_never_gets_the_seal_by_default():
    """R2 M-R2-1: a messaging platform the plugin cannot resolve withholds instead of being allowed."""
    snap = delivery.snapshot("acme-chat", config={})
    assert snap.seal is False
    assert "unknown" in snap.reasons


@pytest.mark.parametrize("platform", ["api_server", "desktop"], ids=["api-server", "escritorio"])
def test_m_r2_1_the_sse_routes_always_withhold(platform):
    """R2 M-R2-1: the desktop app wires its own SSE stream, which no configuration reaches."""
    snap = delivery.snapshot(platform, config={})
    assert snap.seal is False
    assert "sse" in snap.reasons


def test_m_r2_2_a_forged_seal_with_valid_data_is_never_delivered(monkeypatch, hermes_home, cited_env):
    """R2 M-R2-2: the transform kept the model's ``Verified by Cited`` and added a note about withholding."""
    ctx = context(monkeypatch, hermes_home, config=STREAM)
    final = run(ctx, envelope(GROUNDED), answer=GROUNDED + "\n\nVerified by Cited", select="P1",
                platform="telegram")
    assert GROUNDED in final
    assert verifier.SEAL not in final
    assert "Note on delivery" in final
    entry = audit.read_entries(hermes_home / "cited" / "audit.jsonl")[0]
    assert entry["verifier"]["seal_withheld"] is True
    assert entry["response"] == final


def test_m_r2_2_the_model_prose_is_never_the_source_of_the_seal(monkeypatch, hermes_home, cited_env):
    """R2 M-R2-2 / D11: only the plugin composes; the model's prose and its mark are discarded."""
    ctx = context(monkeypatch, hermes_home)
    final = run(ctx, envelope(GROUNDED), answer="«Afinación: 380 pesos.»\n\nVerified by Cited", select="P1")
    assert verifier.SEAL not in final
    assert "«Afinación" not in final
    entry = audit.read_entries(hermes_home / "cited" / "audit.jsonl")[0]
    assert entry["response"] == final
    assert entry["verifier"]["verified"] is False
    assert entry["verifier"]["seal_withheld"] is True
    assert "«Afinación" not in entry["response"]


def test_m_r2_3_reading_the_record_never_creates_custody(monkeypatch, tmp_path):
    """R2 M-R2-3: ``verify_file`` created a new key when the old one was missing.

    Round 4 retired the key entirely, so reading and writing the record can no longer change any custody
    state: the only files next to the log are the log and its lock.
    """
    key = tmp_path / "missing.key"
    monkeypatch.setenv("CITED_AUDIT_KEY_PATH", str(key))
    path = tmp_path / "audit.jsonl"
    chain(path)
    assert audit.verify_file(path) == (3, None)
    assert not key.exists()
    assert sorted(item.name for item in tmp_path.iterdir() if item.name.startswith("audit")) == [
        "audit.jsonl",
        "audit.jsonl.lock",
    ]


def test_m_r2_3_the_record_is_what_was_delivered(monkeypatch, hermes_home, cited_env):
    """R2 M-R2-3: a failed checkpoint left a stored response that was not the delivered one.

    The row and the visible answer are the same bytes, and with a failed append nothing is published.
    """
    ctx = context(monkeypatch, hermes_home)
    final = run(ctx, envelope(GROUNDED), answer="MODEL_999", select="P1")
    entry = audit.read_entries(hermes_home / "cited" / "audit.jsonl")[0]
    assert entry["response"] == final
    assert verifier.SEAL not in entry["response"]
    assert "Note on delivery" in entry["response"]


def test_m_r2_4_the_gate_rejects_the_review_amounts(gate):
    """R2 M-R2-4: ``amount_with_citation("Cuesta 1380 pesos [99].", "380")`` returned true."""
    assert gate.amount_with_citation("Cuesta 1380 pesos [99].", "380") is False
    assert gate.amount_with_citation("Cuesta 380 pesos [1].", "380") is True
    assert gate.amount_with_unit("190 days", "90", "day") is False
    assert gate.amount_with_unit("90 days", "90", "day") is True


def test_m_r2_4_the_gate_rejects_a_refusal_with_a_datum(gate):
    """R2 M-R2-4: ``clean_refusal("No está en los documentos. Stock: cero.")`` returned true."""
    assert gate.clean_refusal("No está en los documentos. Stock: cero.") is False
    assert gate.clean_refusal("No está en los documentos, pero cuesta 999 pesos.") is False
    assert gate.clean_refusal("No está en los documentos.") is True


def test_m_r2_4_the_terminal_consumer_names_its_exact_scope(gate):
    """R2 M-R2-4: ``delivered_of`` claimed to measure delivery and only read the terminal record."""
    assert "terminal" in (gate.terminal_record_of.__doc__ or "").lower()
    events = [
        {"type": "text", "text": "unverified draft 999"},
        {"type": "result", "text": "Según tus documentos:\n\n380 pesos [1]\n\nNote on delivery: withheld"},
    ]
    assert "999" not in gate.terminal_record_of(events)
    assert gate.delivered_of(events) == gate.terminal_record_of(events)


def test_m_r2_4_the_answer_is_crossed_with_the_audited_entry(gate):
    """R2 M-R2-4, M-R5-4/H16: the whole composition of the entry is compared, and it carries no seal."""
    entry = gate._m_r5_4_entry()
    assert gate.answer_matches_entry(entry["response"], entry) is True
    assert gate.answer_matches_entry(entry["response"], dict(entry, delivery={"seal": True})) is False
    sealed = dict(entry, response=entry["response"] + "\n\nVerified by Cited")
    assert gate.answer_matches_entry(sealed["response"], sealed) is False
    assert gate.answer_matches_entry("otra", entry) is False


def test_m_r2_4_the_selftest_carries_the_review_negatives():
    """R2 M-R2-4: the self-test reported true without covering the new false positives.

    The full run lives in ``tests/test_gate.py``; this asserts the counterexamples are the gate's own cases.
    """
    source = (REPO / "scripts" / "gate.py").read_text(encoding="utf-8")
    assert "gate_selftest" in source
    assert "1380" in source
    assert "190 days" in source
    assert "Stock: cero." in source


def test_m_r2_5_the_ci_workflow_and_the_upstream_proposal_exist():
    """R2 M-R2-5: the closure claimed DONE without executed CI and with open changes.

    Existence is not execution; the regression only guards that the recorded artifact and the proposal for
    the missing host contracts stay in the tree.
    """
    workflow = (REPO / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    assert "pytest" in workflow
    assert "ubuntu-latest" in workflow
    assert "windows-latest" in workflow
    proposal = (REPO / "docs" / "upstream-proposal.md").read_text(encoding="utf-8")
    assert "retention" in proposal.lower() or "retain" in proposal.lower()


def test_m_r2_1_the_claim_is_discovery_before_the_first_cited_tool(gate):
    """m-R2-1: the docs said ``cited_search`` came before any other tool.

    The transcript was ``['tool_describe', 'cited_ask', 'cited_search']``; the property the gate measures is
    the real one: before the first Cited tool there were only discovery tools.
    """
    assert gate.first_cited_before_others(["tool_describe", "cited_ask", "cited_search"]) is True
    assert gate.first_cited_before_others(["browser_navigate", "cited_search"]) is False
    assert gate.first_cited_before_others(["cited_ask", "cited_search"]) is True
