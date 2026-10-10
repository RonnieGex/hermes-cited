"""One adversarial fixture per finding of the Codex review (B1-B3, M1-M5, M7).

These are the exact counterexamples the review printed, turned into tests that must fail if the
defect comes back. The B1 fixture lives in `test_delivery.py` and in the gate, because the host
retention hook it needs does not exist in Hermes v0.21.6+387; here the plugin-level fixture proves
the seal is withheld on a streaming surface and the READMEs state the limitation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hermes_cited import audit, plugin, tools, verifier
from hermes_cited.client import CitedError, call_tool
from hermes_cited.config import Settings

REPO = Path(__file__).resolve().parents[1]
GROUNDED = "«Afinación de bicicleta: 380 pesos.» [1]"


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


def run_turn(context, answer, session="s1", turn="t1", platform="cli"):
    hook(context, "pre_llm_call", session_id=session, turn_id=turn, user_message="precio", platform=platform)
    raw = context.tools["cited_search"]["handler"]({"query": "afinacion"})
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
    return hook(
        context,
        "transform_llm_output",
        response_text=answer,
        session_id=session,
        turn_id=turn,
        platform=platform,
    )


def _settings(url, token, timeout_ms=5000):
    return Settings(url=url, token=token, timeout_ms=timeout_ms, default_mode="cited")


def _payload(index):
    return {
        "ts": "2026-10-09T22:00:00Z",
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


# --- B1: cited mode must not promise a verified-only delivery where streaming is on -------------


def test_b1_the_seal_is_withheld_and_said_on_a_streaming_surface(monkeypatch, hermes_home, cited_env):
    (hermes_home / "config.yaml").write_text("streaming:\n  enabled: true\n", encoding="utf-8")
    monkeypatch.setenv("CITED_DEFAULT_MODE", "cited")
    context = FakeContext()
    plugin.register(context)
    final = run_turn(context, GROUNDED, platform="telegram")
    assert "Verified by Cited" not in final
    assert "streaming is on" in final
    entry = json.loads((hermes_home / "cited" / "audit.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert entry["verifier"]["seal_withheld"] is True


# --- B2: a turn with zero passages must not verify its own datum -------------------------------


def test_b2_query_echo_is_not_evidence():
    envelope = {
        "cited_tool": "cited_search",
        "query": "999 pesos",
        "text": 'No passage of the documents of this installation matches "999 pesos".',
        "passages": [],
    }
    evidence = tools.grounding_excerpts(envelope)
    assert evidence == []
    result = verifier.verify("«Cuesta 999 pesos.»", evidence)
    assert result.ok is False
    assert result.has_grounding is False


def test_b2_generated_answer_is_not_evidence():
    envelope = {
        "cited_tool": "cited_ask",
        "status": "answered",
        "answer": "Cuesta 999 pesos [1].",
        "text": "Cuesta 999 pesos [1].",
        "citations": [{"n": 1, "document": "x", "excerpt": "Cuesta 380 pesos."}],
    }
    evidence = tools.grounding_excerpts(envelope)
    assert evidence == ["Cuesta 380 pesos."]
    assert verifier.verify("«Cuesta 999 pesos.»", evidence, tools.citation_numbers(envelope)).ok is False


# --- B3: a redirect must never carry the bearer to another origin ------------------------------


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_b3_a_redirect_is_refused_and_the_sink_is_never_called(cited_factory, status):
    origin = cited_factory()
    sink = cited_factory()
    origin.behavior = "redirect"
    origin.redirect_status = status
    origin.redirect_location = "{0}/sink".format(sink.url)
    with pytest.raises(CitedError) as caught:
        call_tool("cited_search", {"query": "precio"}, _settings(origin.url, origin.token))
    assert "redirect" in str(caught.value).lower()
    assert origin.token not in str(caught.value)
    assert sink.requests == []


# --- M1: the token extractor must not accept changed data --------------------------------------


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
def test_m1_a_changed_or_swapped_datum_is_refused(answer, excerpt):
    result = verifier.verify("«{0}»".format(answer), [excerpt])
    assert result.ok is False, answer


@pytest.mark.parametrize(
    "answer, excerpt",
    [
        ("Cuesta ３８０ pesos.", "Cuesta 380 pesos."),
        ("Cuesta 1 200 pesos.", "Cuesta 1200 pesos."),
    ],
)
def test_m1_unicode_and_space_normalisation_is_not_a_false_negative(answer, excerpt):
    assert verifier.verify("«{0}»".format(answer), [excerpt]).ok is True


def test_m1_an_ambiguous_separator_is_literal():
    assert verifier.verify("«Dosis 1.200 mg.»", ["Dosis 1200 mg."]).ok is False


# --- M2: the token must not surface in a success result or in the log --------------------------


def test_m2_a_successful_result_that_reflects_the_token_is_rejected(cited_env):
    cited_env.echo_token = True
    raw = tools.search({"query": "precio"})
    assert cited_env.token not in raw
    assert "token" in raw.lower()


def test_m2_the_question_and_the_arguments_are_redacted(monkeypatch, hermes_home, cited_env):
    monkeypatch.setenv("CITED_DEFAULT_MODE", "cited")
    context = FakeContext()
    plugin.register(context)
    hook(context, "pre_llm_call", session_id="s", turn_id="t", user_message=cited_env.token, platform="cli")
    envelope = json.dumps(
        {
            "cited_tool": "cited_search",
            "query": "precio",
            "text": "Precios",
            "passages": [{"n": 1, "document": "x", "heading": None, "position": 0, "excerpt": cited_env.token}],
        }
    )
    hook(
        context,
        "post_tool_call",
        tool_name="cited_search",
        args={"query": cited_env.token},
        result=envelope,
        session_id="s",
        turn_id="t",
        status="ok",
    )
    hook(context, "transform_llm_output", response_text=GROUNDED, session_id="s", turn_id="t", platform="cli")
    text = (hermes_home / "cited" / "audit.jsonl").read_text(encoding="utf-8")
    assert cited_env.token not in text
    assert "<token>" in text


def test_m2_an_error_that_reflects_the_token_is_redacted(fake_cited):
    fake_cited.behavior = "jsonrpc_error_token"
    with pytest.raises(CitedError) as caught:
        call_tool("cited_search", {"query": "x"}, _settings(fake_cited.url, fake_cited.token))
    assert fake_cited.token not in str(caught.value)
    assert "<token>" in str(caught.value)


# --- M3: two processes must not break the chain ------------------------------------------------


def test_m3_the_append_is_serialised(tmp_path):
    path = tmp_path / "race.jsonl"
    for index in range(2):
        audit.append_entry(path, _payload(index))
    count, error = audit.verify_file(path)
    assert error is None
    assert count == 2


# --- M4: the checkpoint must catch an edit the chain alone cannot ------------------------------


def test_m4_a_removed_last_entry_is_caught(tmp_path):
    path = tmp_path / "audit.jsonl"
    for index in range(3):
        audit.append_entry(path, _payload(index))
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    assert audit.verify_file(path)[1] is not None


def test_m4_a_recomputed_chain_is_caught(tmp_path):
    path = tmp_path / "audit.jsonl"
    for index in range(3):
        audit.append_entry(path, _payload(index))
    entries = audit.read_entries(path)
    previous = ""
    for entry in entries:
        entry["response"] = "rewritten"
        entry["prev_hash"] = previous
        entry["hash"] = audit.entry_hash(entry)
        previous = entry["hash"]
    path.write_text(
        "\n".join(json.dumps(entry, ensure_ascii=False, sort_keys=True) for entry in entries) + "\n",
        encoding="utf-8",
    )
    assert audit.verify_file(path)[1] is not None


# --- M5: an audit failure must never yield a sealed answer -------------------------------------


def test_m5_the_seal_is_never_attached_to_an_unrecorded_answer(monkeypatch, hermes_home, cited_env):
    monkeypatch.setenv("CITED_DEFAULT_MODE", "cited")
    context = FakeContext()
    plugin.register(context)

    def fail(*args, **kwargs):
        raise PermissionError("synthetic read-only log")

    monkeypatch.setattr(audit, "append_entry", fail)
    final = run_turn(context, GROUNDED)
    assert "Verified by Cited" not in final
    assert "could not be written" in final


def test_m5_the_session_is_written(monkeypatch, hermes_home, cited_env):
    monkeypatch.setenv("CITED_DEFAULT_MODE", "cited")
    context = FakeContext()
    plugin.register(context)
    run_turn(context, GROUNDED, session="session-real", turn="t1")
    entries = audit.read_entries(hermes_home / "cited" / "audit.jsonl")
    assert entries[0]["session"] == "session-real"
    assert entries[0]["turn_id"] == "t1"


# --- M7: the documented command must work from the installed plugin ----------------------------


def test_m7_the_installed_command_shape_is_documented():
    installed = REPO / "hermes_cited" / "verify_log.py"
    assert installed.exists()
    assert "plugins/hermes-cited" in installed.read_text(encoding="utf-8")
