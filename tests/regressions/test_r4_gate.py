"""Permanent regressions of the fourth review: the gate's own binding predicates.

R4 M-R4-7. The three counterexamples the review ran: a sign separated by a space, a mark that belongs
to another statement of the same text, and a forged block whose source was never returned by the
search. ``blocks_are_bound`` resolves call, pid, document, position and the full line against the
evidence table the entry stored, instead of accepting any substring of the answer.
"""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

from hermes_cited import plugin, verifier

REPO = Path(__file__).resolve().parents[2]
GROUNDED = "- Afinacion de bicicleta: 380 pesos."
QUIET = (
    "streaming:\n  enabled: false\ndisplay:\n  streaming: false\n  interim_assistant_messages: false\n"
)


@pytest.fixture(scope="module")
def gate():
    spec = importlib.util.spec_from_file_location("gate_r4_regressions", REPO / "scripts" / "gate.py")
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


def real_entry(monkeypatch, home):
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
    context.hooks["pre_llm_call"][0](session_id="s1", turn_id="t1", user_message=GROUNDED, platform="cli")
    context.hooks["post_tool_call"][0](tool_name="cited_search", args={"query": "q"}, result=envelope,
                                       session_id="s1", turn_id="t1", status="ok")
    context.tools["cited_quote"]["handler"]({"passage": "P1", "lines": [1]}, session_id="s1", turn_id="t1")
    context.hooks["transform_llm_output"][0](response_text="MODEL_999", session_id="s1", turn_id="t1",
                                             platform="cli")
    return json.loads((home / "cited" / "audit.jsonl").read_text(encoding="utf-8").splitlines()[0])


def test_m_r4_7_a_sign_separated_by_a_space_is_not_the_plain_amount(gate):
    """R4 M-R4-7: ``amount_statement('- 380 pesos [1]', '380', unit='currency', mark=1)`` used to pass."""
    assert gate.amount_statement("- 380 pesos [1]", "380", unit="currency", mark=1) is False
    assert gate.amount_statement("-380 pesos [1]", "380", unit="currency", mark=1) is False
    assert gate.amount_statement("-380 pesos [1]", "380", unit="currency", mark=1, sign="-") is True
    assert gate.amount_statement("380 pesos [1]", "380", unit="currency", mark=1) is True


def test_m_r4_7_the_mark_belongs_to_the_statement_of_the_amount(gate):
    """R4 M-R4-7: ``999 pesos [1]. Price: 380 pesos [99]`` used to satisfy the ``380``/``[1]`` pair."""
    assert gate.amount_statement("999 pesos [1]. Price: 380 pesos [99]", "380", unit="currency", mark=1) is False
    assert gate.amount_statement("380 pesos [1].", "380", unit="currency", mark=1) is True
    assert gate.amount_statement("380 pesos [99].", "380", unit="currency", mark=1) is False
    assert gate.amount_statement("380 pesos [1]. 380 pesos [99]", "380", unit="currency", mark=1) is True


def test_m_r4_7_a_forged_block_is_not_bound(gate, monkeypatch, hermes_home, cited_env):
    """R4 M-R4-7: forged call, pid, document and position with an answer that does not hold the line."""
    entry = real_entry(monkeypatch, hermes_home)
    assert gate.blocks_are_bound(entry, entry["quoted_lines"][0]) is True
    forged = copy.deepcopy(entry)
    forged["response"] = "INVENTED_999 [1]\nFuente: forged.md - Elsewhere"
    forged["quoted_lines"][0].update(
        document="forged.md", heading="Elsewhere", call=999, position=999, number=999,
        uid="{0}:999:P1".format(entry["turn_id"]), text="INVENTED_999",
    )
    assert gate.blocks_are_bound(forged, forged["quoted_lines"][0]) is False


def test_m_r4_7_the_source_must_be_the_one_the_search_returned(gate, monkeypatch, hermes_home, cited_env):
    """R4 M-R4-7: a document written in the answer but never returned as a passage is not bound."""
    entry = real_entry(monkeypatch, hermes_home)
    forged = copy.deepcopy(entry)
    forged["quoted_lines"][0]["document"] = "forged.md"
    forged["response"] = forged["response"].replace("cafe-la-horquilla.md", "forged.md")
    assert gate.blocks_are_bound(forged, forged["quoted_lines"][0]) is False
    no_text = copy.deepcopy(entry)
    no_text["response"] = "Según tus documentos:\n\nINVENTED_999 [1]\nFuente: cafe-la-horquilla.md - Precios"
    assert gate.blocks_are_bound(no_text, no_text["quoted_lines"][0]) is False


def test_m_r4_7_every_block_of_every_entry_is_checked(gate, monkeypatch, hermes_home, cited_env):
    entry = real_entry(monkeypatch, hermes_home)
    ok, detail = gate.every_block_is_bound([entry])
    assert ok is True, detail
    forged = copy.deepcopy(entry)
    forged["quoted_lines"][0]["text"] = "INVENTED_999"
    assert gate.every_block_is_bound([forged])[0] is False


def test_m_r4_7_a_refusal_entry_is_explicitly_excluded(gate, monkeypatch, hermes_home, cited_env):
    """R4 M-R4-7: the refusal is excluded by name, not skipped because its block list is empty."""
    entry = real_entry(monkeypatch, hermes_home)
    refusal = copy.deepcopy(entry)
    refusal["response"] = verifier.refusal_text("es")
    refusal["quoted_lines"] = []
    refusal["verifier"]["ok"] = True
    assert gate.every_block_is_bound([entry, refusal])[0] is True
    forged = copy.deepcopy(entry)
    forged["quoted_lines"] = [dict(item, text="INVENTED_999") for item in entry["quoted_lines"]]
    assert gate.every_block_is_bound([forged])[0] is False


def test_m_r4_7_the_self_test_names_the_three_counterexamples(gate, hermes_home):
    ok, detail = gate.gate_selftest()
    assert ok is True, detail
    original = gate.blocks_are_bound
    gate.blocks_are_bound = lambda entry, line: True
    try:
        ok, detail = gate.gate_selftest()
        assert ok is False
        assert "failed fixtures" in detail
    finally:
        gate.blocks_are_bound = original
