"""The gate's own predicates against the reproductions of the three reviews (M-R2-4, M-R3-6, D8)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def load_gate():
    spec = importlib.util.spec_from_file_location("gate_under_test", REPO / "scripts" / "gate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def gate():
    return load_gate()


def test_a_different_amount_is_not_the_amount_with_a_citation(gate):
    assert gate.amount_with_citation("Cuesta 1380 pesos [99].", "380") is False


def test_the_amount_with_its_unit_and_its_citation_passes(gate):
    assert gate.amount_with_citation("Cuesta 380 pesos [1].", "380") is True


def test_an_amount_without_a_citation_does_not_pass(gate):
    assert gate.amount_with_citation("Cuesta 380 pesos.", "380") is False


def test_the_amount_must_be_a_whole_token(gate):
    assert gate.amount_with_citation("Cuesta 1380 pesos afuera.", "380") is False
    assert gate.amount_with_citation("Cuesta 1380 pesos [1].", "380") is False
    assert gate.amount_with_citation("Cuesta 380.5 pesos [1].", "380") is False


def test_a_negative_amount_is_not_the_positive_one(gate):
    """M-R3-6, first new negative: the sign is part of the statement."""
    assert gate.amount_with_citation("-380 pesos [99].", "380") is False
    assert gate.amount_statement("-380 pesos [1].", "380", unit="currency", mark=1, sign="-") is True
    assert gate.amount_with_citation("380 pesos [1].", "380") is True


def test_a_unit_of_another_class_is_not_the_requested_unit(gate):
    """M-R3-6, second new negative: ``380 kg`` is not a price and ``-90 days`` is not 90 days."""
    assert gate.amount_with_citation("380 kg, pesos [99]", "380") is False
    assert gate.amount_with_unit("-90 days", "90", "day") is False
    assert gate.amount_with_unit("90 days", "90", "day") is True


def test_a_citation_must_be_the_mark_of_the_selected_passage(gate):
    """M-R3-6, third new negative: a mark that names another passage is not a bound citation."""
    assert gate.amount_statement("380 pesos [99].", "380", unit="currency", mark=1) is False
    assert gate.amount_statement("380 pesos [1].", "380", unit="currency", mark=1) is True


def test_a_different_duration_is_not_the_duration(gate):
    assert gate.amount_with_unit("190 days", "90", "day") is False


def test_the_mcp_route_amount_accepts_a_mark_or_a_document_name(gate):
    assert gate.amount_with_source("Cuesta 380 pesos [1].", "380") is True
    assert gate.amount_with_source("Cuesta 380 pesos, segun cafe-la-horquilla.md.", "380") is True
    assert gate.amount_with_source("Cuesta 380 pesos.", "380") is False
    assert gate.amount_with_source("Cuesta 1380 pesos, segun doc.md.", "380") is False


def test_the_duration_with_its_unit_passes(gate):
    assert gate.amount_with_unit("90 days", "90", "day") is True
    assert gate.amount_with_unit("90-day guarantee", "90", "day") is True


def test_the_refusal_predicate_is_the_conservative_contract(gate):
    assert gate.clean_refusal("No está en los documentos.") is True
    assert gate.clean_refusal("It is not in the documents.") is True
    assert gate.clean_refusal("No está en los documentos. Stock: cero.") is False
    assert gate.clean_refusal("No está en los documentos, pero cuesta 999 pesos.") is False


def test_the_discovery_allow_list_before_the_first_cited_tool(gate):
    assert gate.first_cited_before_others(["tool_describe", "cited_search"]) is True
    assert gate.first_cited_before_others(["browser_navigate", "cited_search"]) is False
    assert gate.first_cited_before_others(["cited_ask", "cited_search"]) is True
    assert gate.first_cited_before_others([]) is False


def test_recompute_digests_needs_excerpts(gate):
    ok, detail = gate.recompute_digests([])
    assert ok is False
    assert detail


def test_the_terminal_record_consumer_takes_only_the_terminal_record(gate):
    """M-R3-6: the helper names its exact scope: the terminal record of the documented consumer."""
    events = [
        {"type": "text", "text": "unverified draft 999"},
        {"type": "tool_use", "name": "cited_search"},
        {"type": "text", "text": "more draft"},
        {"type": "result", "text": "Según tus documentos:\n\n380 pesos [1]\n\nVerified by Cited"},
    ]
    delivered = gate.terminal_record_of(events)
    assert "999" not in delivered
    assert delivered.endswith("Verified by Cited")
    assert gate.delivered_of(events) == delivered


def test_the_seal_is_crossed_with_the_audited_entry(gate):
    text = "Según tus documentos:\n\n- Afinacion de bicicleta: 380 pesos. [1]\n\nVerified by Cited"
    entry = {
        "response": text,
        "delivery": {"seal": True},
        "verifier": {"applied": True, "ok": True, "verified": True, "seal_withheld": False},
    }
    assert gate.seal_matches_entry(text, entry) is True
    assert gate.seal_matches_entry(text, {"response": "otra", "verifier": {"ok": True}}) is False
    forged = dict(entry)
    forged["delivery"] = {"seal": False}
    assert gate.seal_matches_entry(text, forged) is False, "a seal the entry says was withheld cannot pass"
    withheld = text.replace("\n\nVerified by Cited", "\n\nwithheld")
    assert gate.seal_matches_entry(
        withheld, {"response": withheld, "delivery": {"seal": False}, "verifier": {"applied": True, "ok": True, "seal_withheld": True}}
    ) is True


def test_a_recorded_block_is_bound_to_its_own_turn(gate):
    """M-R3-6 and M-R4-7: the block resolves against its evidence row, its source and its turn."""
    line = {
        "pid": "P1",
        "uid": "t1:0:P1",
        "call": 0,
        "text": "- Afinacion de bicicleta: 380 pesos.",
        "document": "cafe-la-horquilla.md",
        "heading": "Precios",
        "position": 2,
    }
    entry = {
        "turn_id": "t1",
        "mode": "cited",
        "response": "Según tus documentos:\n\n- Afinacion de bicicleta: 380 pesos. [1]\nFuente: cafe-la-horquilla.md - Precios\n\nVerified by Cited",
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
    other_turn = dict(entry, turn_id="t2")
    assert gate.blocks_are_bound(other_turn, entry["quoted_lines"][0]) is False
    unbound = dict(entry["quoted_lines"][0], pid="")
    assert gate.blocks_are_bound(entry, unbound) is False
    wrong_source = dict(entry["quoted_lines"][0], document="otro.md")
    assert gate.blocks_are_bound(entry, wrong_source) is False
    wrong_call = dict(entry["quoted_lines"][0], call=9, uid="t1:9:P1")
    assert gate.blocks_are_bound(entry, wrong_call) is False
    ok, detail = gate.every_block_is_bound([entry])
    assert ok is True, detail


def test_the_gate_self_test_passes(gate, hermes_home):
    ok, detail = gate.gate_selftest()
    assert ok is True, detail


def test_the_gate_self_test_reports_its_failures(gate, hermes_home, monkeypatch):
    """M-R3-6: a red self-test names the failing fixtures; it never reports success."""
    original = gate.amount_with_citation

    def always_true(*args, **kwargs):
        return True

    monkeypatch.setattr(gate, "amount_with_citation", always_true)
    ok, detail = gate.gate_selftest()
    assert ok is False
    assert "failed fixtures" in detail
    monkeypatch.setattr(gate, "amount_with_citation", original)


def test_the_gate_self_test_rejects_the_review_fixtures(gate, hermes_home):
    assert gate.amount_with_citation("Cuesta 1380 pesos [99].", "380") is False
    assert gate.amount_with_unit("190 days", "90", "day") is False
    assert gate.clean_refusal("No está en los documentos. Stock: cero.") is False
    assert gate.amount_with_citation("-380 pesos [99].", "380") is False
    assert gate.amount_with_unit("-90 days", "90", "day") is False
    assert gate.amount_with_citation("380 kg, pesos [99]", "380") is False
    assert gate.amount_statement("380 pesos [99].", "380", unit="currency", mark=1) is False
