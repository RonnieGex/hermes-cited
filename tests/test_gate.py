"""The gate's own predicates against the reproductions of both reviews (M-R2-4, D8)."""

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


def test_the_delivery_consumer_takes_only_the_terminal_record(gate):
    events = [
        {"type": "text", "text": "unverified draft 999"},
        {"type": "tool_use", "name": "cited_search"},
        {"type": "text", "text": "more draft"},
        {"type": "result", "text": "Según tus documentos:\n\n380 pesos [1]\n\nVerified by Cited"},
    ]
    delivered = gate.delivered_of(events)
    assert "999" not in delivered
    assert delivered.endswith("Verified by Cited")


def test_the_seal_is_crossed_with_the_audited_entry(gate):
    text = "Según tus documentos:\n\n- Afinacion de bicicleta: 380 pesos. [1]\n\nVerified by Cited"
    entry = {
        "response": text,
        "verifier": {"applied": True, "ok": True, "seal_withheld": False},
    }
    assert gate.seal_matches_entry(text, entry) is True
    assert gate.seal_matches_entry(text, {"response": "otra", "verifier": {"ok": True}}) is False
    withheld = text.replace("\n\nVerified by Cited", "\n\nstreaming is on")
    assert gate.seal_matches_entry(withheld, {"response": withheld, "verifier": {"ok": True, "seal_withheld": True}}) is False


def test_the_gate_self_test_passes(gate, hermes_home):
    ok, detail = gate.gate_selftest()
    assert ok is True, detail


def test_the_gate_self_test_rejects_the_review_fixtures(gate, hermes_home):
    assert gate.amount_with_citation("Cuesta 1380 pesos [99].", "380") is False
    assert gate.amount_with_unit("190 days", "90", "day") is False
    assert gate.clean_refusal("No está en los documentos. Stock: cero.") is False
