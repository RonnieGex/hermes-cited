"""Permanent regressions of the fifth review: the gate's own binding predicates.

R5 M-R5-4. The review found six false positives: an altered line number, an altered original number, an
invented extra block that kept the good one, a cited answer with no block, an amount whose citation
belonged to another statement and a run that was selected by question instead of by its execution. The
gate resolves each selection by call, ``pid``, original number, position and line number with its text,
compares the whole answer against the plugin's fixed templates and identifies a run by the entries its
execution appended.
"""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

from hermes_cited import messages, plugin, verifier

REPO = Path(__file__).resolve().parents[2]
GROUNDED = "- Afinacion de bicicleta: 380 pesos."
QUIET = (
    "streaming:\n  enabled: false\ndisplay:\n  streaming: false\n  interim_assistant_messages: false\n"
)


@pytest.fixture(scope="module")
def gate():
    spec = importlib.util.spec_from_file_location("gate_r5_regressions", REPO / "scripts" / "gate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def real_entry(monkeypatch, home, question=GROUNDED):
    monkeypatch.setenv("CITED_DEFAULT_MODE", "cited")
    (home / "config.yaml").write_text(QUIET, encoding="utf-8")
    context = FakeContext()
    plugin.register(context)
    envelope = json.dumps({
        "cited_tool": "cited_search",
        "query": "afinacion",
        "text": "t",
        "passages": [{"n": 1, "document": "cafe-la-horquilla.md", "heading": "Precios",
                      "position": 2, "excerpt": GROUNDED}],
    })
    context.hooks["pre_llm_call"][0](session_id="s1", turn_id="t1", user_message=question, platform="cli")
    context.hooks["post_tool_call"][0](tool_name="cited_search", args={"query": "q"}, result=envelope,
                                       session_id="s1", turn_id="t1", status="ok")
    context.tools["cited_quote"]["handler"]({"passage": "P1", "lines": [1]}, session_id="s1", turn_id="t1")
    context.hooks["transform_llm_output"][0](response_text="MODEL_999", session_id="s1", turn_id="t1",
                                             platform="cli")
    return json.loads((home / "cited" / "audit.jsonl").read_text(encoding="utf-8").splitlines()[0])


def test_m_r5_4_the_answer_is_compared_as_the_whole_composition(gate, monkeypatch, hermes_home, cited_env):
    """R5 M-R5-4: the review added an invented block and kept the good one; the whole render must fail."""
    entry = real_entry(monkeypatch, hermes_home)
    assert gate.answer_matches_entry(entry["response"], entry) is True
    forged = copy.deepcopy(entry)
    forged["response"] = forged["response"].replace(
        "\n\n", "\n\nINVENTED_999 [99]\nFuente: forged.md\n\n", 1)
    assert gate.every_block_is_bound([forged])[0] is False
    deleted = copy.deepcopy(entry)
    deleted["response"] = deleted["response"].replace(GROUNDED + " [1]", "INVENTED_999 [1]")
    assert gate.every_block_is_bound([deleted])[0] is False


def test_m_r5_4_a_cited_entry_with_no_block_is_not_a_refusal(gate, monkeypatch, hermes_home, cited_env):
    """R5 M-R5-4: a cited answer that is not a refusal and holds no block used to pass as bound."""
    entry = real_entry(monkeypatch, hermes_home)
    empty = copy.deepcopy(entry)
    empty["quoted_lines"] = []
    empty["response"] = "INVENTED_999"
    assert gate.is_refusal_answer(empty["response"]) is False
    assert gate.every_block_is_bound([empty])[0] is False
    refusal = copy.deepcopy(entry)
    refusal["quoted_lines"] = []
    refusal["response"] = verifier.refusal_text("es")
    assert gate.every_block_is_bound([entry, refusal])[0] is True
    assert gate.every_block_is_bound([refusal])[0] is False


@pytest.mark.parametrize("field", ["number", "original"])
def test_m_r5_4_the_line_number_and_the_original_number_are_bound(gate, monkeypatch, hermes_home, cited_env, field):
    """R5 M-R5-4: the review changed ``number`` and ``original`` to 999 and both were accepted."""
    entry = real_entry(monkeypatch, hermes_home)
    altered = copy.deepcopy(entry)
    altered["quoted_lines"][0][field] = 999
    assert gate.blocks_are_bound(altered, altered["quoted_lines"][0]) is False


def test_m_r5_4_the_amount_is_measured_inside_its_own_resolved_block(gate, monkeypatch, hermes_home, cited_env):
    """R5 M-R5-4: the amount and its citation used to be two independent conditions of the answer."""
    entry = real_entry(monkeypatch, hermes_home)
    assert gate.bound_amount(entry, "380", unit="currency", cite=True) is True
    other = copy.deepcopy(entry)
    other["response"] = other["response"].replace(GROUNDED, "Price: 380 pesos. Fee: 999 pesos")
    other["response"] = other["response"].replace(
        GROUNDED + " [1]", "Price: 380 pesos. Fee: 999 pesos [1]")
    other["quoted_lines"][0]["text"] = "Price: 380 pesos. Fee: 999 pesos"
    assert gate.amount_statement("Price: 380 pesos. Fee: 999 pesos [1]", "380", unit="currency", mark=1) is False


def test_m_r5_4_a_run_needs_the_turn_its_execution_captured(gate, monkeypatch, hermes_home, cited_env):
    """R5 M-R5-4: prepending a row with the same question and mode used to select the older turn."""
    entry = real_entry(monkeypatch, hermes_home)
    older = copy.deepcopy(entry)
    older["turn_id"] = "unrelated-old-turn"
    entries = [older, entry]
    assert gate.entry_of_run(entries, entry["question"]) is None
    assert gate.entry_of_run(entries, entry["question"], "cited", turn_id=entry["turn_id"]) is entry
    duplicated = [older, entry, copy.deepcopy(entry)]
    assert gate.entry_of_run(duplicated, entry["question"], "cited", turn_id=entry["turn_id"]) is None


def test_m_r5_4_a_run_is_bound_to_what_the_execution_appended(gate, monkeypatch, hermes_home, cited_env):
    """R5 M-R5-4: absence, ambiguity and duplicates of a run are errors, not a guess."""
    entry = real_entry(monkeypatch, hermes_home)
    found, error = gate.phase_entry([entry], 0, entry["question"], "cited")
    assert found is entry and error is None
    assert gate.phase_entry([entry], 1)[1]
    assert gate.phase_entry([entry], 0, "otra pregunta", "cited")[1]
    assert gate.phase_entry([entry, entry], 0)[1]


def test_m_r5_4_an_operational_refusal_must_be_the_validated_template(gate):
    """R5 M-R5-4: the review replaced the whole template match with a ``startswith``."""
    good = messages.operational_text("es", "CITED-ABC123")
    assert gate.is_refusal_answer(good) is True
    assert gate.is_refusal_answer("No puedo entregar 999 pesos sin registro.") is False
    assert gate.is_refusal_answer("No puedo entregar esta respuesta como verificada.") is False
    assert gate.is_refusal_answer(verifier.refusal_text("es")) is True


def test_m_r5_4_the_self_test_carries_the_counterexamples(gate, hermes_home):
    """R5 M-R5-4: the counterexamples must be in the self-test, and a red one must name itself."""
    ok, detail = gate.gate_selftest()
    assert ok is True, detail
    original = gate.answer_matches_entry
    gate.answer_matches_entry = lambda text, entry: True
    try:
        ok, detail = gate.gate_selftest()
        assert ok is False
        assert "failed fixtures" in detail
    finally:
        gate.answer_matches_entry = original


def test_m_r5_4_the_vacuous_binding_of_the_review_fails(gate, monkeypatch, hermes_home, cited_env):
    """R5 M-R5-4: the four observations the review recorded must all be false now."""
    entry = real_entry(monkeypatch, hermes_home)
    for field in ("number", "original"):
        altered = copy.deepcopy(entry)
        altered["quoted_lines"][0][field] = 999
        assert gate.blocks_are_bound(altered, altered["quoted_lines"][0]) is False
    extra = copy.deepcopy(entry)
    extra["response"] = extra["response"].replace(
        "\n\n", "\n\nINVENTED_999 [99]\nFuente: forged.md\n\n", 1)
    assert gate.every_block_is_bound([extra])[0] is False
    empty = copy.deepcopy(entry)
    empty["quoted_lines"] = []
    empty["response"] = "INVENTED_999"
    assert gate.every_block_is_bound([empty])[0] is False
    assert gate.amount_statement("Price: 380 pesos. Fee: 999 pesos [1]", "380", unit="currency", mark=1) is False
    older = copy.deepcopy(entry)
    older["turn_id"] = "unrelated-old-turn"
    assert gate.entry_of_run([older, entry], entry["question"]) is None
