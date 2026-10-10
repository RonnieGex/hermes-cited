"""Permanent regressions of the fifth review: the delivery policy of cited mode.

R5 M-R5-1 (``source=host`` did not accredit the effective receivers and hid the YAML read errors), D11
and H16 (the seal is retained while the host exposes no accreditable delivery contract). The real loader,
the ``FailedConfigRead`` and the real stream receiver live in ``test_r5_host.py``; this module exercises
the capability point and the snapshot on their own.
"""

from __future__ import annotations

import json

import pytest

from hermes_cited import delivery, messages, plugin, render, verifier

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
        self.tools[name] = {"handler": handler}

    def register_hook(self, hook_name, callback):
        self.hooks.setdefault(hook_name, []).append(callback)

    def register_command(self, name, handler, description="", args_hint="", argument_mode=None):
        self.commands[name] = handler

    def register_skill(self, name, path, description="", frontmatter=None):
        self.skills[name] = {"path": path}


def envelope(excerpt=GROUNDED):
    return json.dumps({
        "cited_tool": "cited_search",
        "query": "afinacion",
        "text": "t",
        "passages": [{"n": 1, "document": "cafe-la-horquilla.md", "heading": "Precios",
                      "position": 2, "excerpt": excerpt}],
    })


def run_cited(monkeypatch, home, platform="cli", answer="MODEL_LEAK_999"):
    monkeypatch.setenv("CITED_DEFAULT_MODE", "cited")
    (home / "config.yaml").write_text(QUIET, encoding="utf-8")
    context = FakeContext()
    plugin.register(context)
    context.hooks["pre_llm_call"][0](session_id="s1", turn_id="t1", user_message="q", platform=platform)
    context.hooks["post_tool_call"][0](tool_name="cited_search", args={"query": "q"}, result=envelope(),
                                       session_id="s1", turn_id="t1", status="ok")
    context.tools["cited_quote"]["handler"]({"passage": "P1", "lines": [1]}, session_id="s1", turn_id="t1")
    return context.hooks["transform_llm_output"][0](
        response_text=answer, session_id="s1", turn_id="t1", platform=platform)


def entry_of(home):
    return json.loads((home / "cited" / "audit.jsonl").read_text(encoding="utf-8").splitlines()[0])


def test_m_r5_1_the_capability_point_is_the_only_blocker(monkeypatch, tmp_path):
    """R5 M-R5-1 / D11: a quiet configuration is clear on its surfaces, and still not accredited."""
    (tmp_path / "config.yaml").write_text(QUIET, encoding="utf-8")
    assert delivery.accredited_delivery() is False
    snapshot = delivery.snapshot("cli", home=tmp_path)
    assert snapshot.surface_clear is True
    assert snapshot.accredited is False
    assert snapshot.seal is False
    monkeypatch.setattr(delivery, "ACCREDITED_DELIVERY", True)
    assert delivery.accredited_delivery() is True
    accredited = delivery.snapshot("cli", home=tmp_path)
    assert accredited.surface_clear is True and accredited.seal is True


def test_m_r5_1_the_snapshot_records_both_halves(monkeypatch, tmp_path):
    """R5 M-R5-1: the record separates what the plugin could read from what the host accredits."""
    (tmp_path / "config.yaml").write_text(QUIET, encoding="utf-8")
    data = delivery.snapshot("telegram", home=tmp_path).as_dict()
    assert data["surface_clear"] is True
    assert data["accredited"] is False
    assert data["seal"] is False
    monkeypatch.setattr(delivery, "ACCREDITED_DELIVERY", True)
    data = delivery.snapshot("telegram", home=tmp_path).as_dict()
    assert data["seal"] is True


def test_m_r5_1_a_read_error_is_not_a_configuration(monkeypatch, tmp_path):
    """R5 M-R5-1: a mapping that carries a ``read_error`` is the last valid state, not a policy."""
    import sys
    import types

    class FailedConfigRead(dict):
        read_error = "while parsing a flow node"

    module = types.ModuleType("hermes_cli.config")
    module.get_config_path = lambda: str(tmp_path / "config.yaml")
    module.load_config_readonly = lambda: FailedConfigRead({"streaming": {"enabled": False}})
    package = types.ModuleType("hermes_cli")
    package.config = module
    monkeypatch.setitem(sys.modules, "hermes_cli", package)
    monkeypatch.setitem(sys.modules, "hermes_cli.config", module)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text(QUIET, encoding="utf-8")
    with pytest.raises(delivery.UnreadableConfig):
        delivery.host_config(tmp_path)
    snapshot = delivery.snapshot("telegram", home=tmp_path)
    assert snapshot.readable is False
    assert snapshot.seal is False
    assert "unreadable" in snapshot.reasons


def test_m_r5_1_the_plugin_never_emits_the_mark_on_a_quiet_cli(monkeypatch, hermes_home, cited_env):
    """R5 M-R5-1 / H16: a quiet CLI used to be sealed; now the answer names the retention."""
    final = run_cited(monkeypatch, hermes_home, platform="cli")
    assert GROUNDED in final
    assert verifier.SEAL not in final
    assert "per-turn delivery policy" in final
    entry = entry_of(hermes_home)
    assert entry["delivery"]["surface_clear"] is True
    assert entry["delivery"]["accredited"] is False
    assert entry["delivery"]["seal"] is False
    assert entry["verifier"]["verified"] is False
    assert entry["verifier"]["seal_withheld"] is True
    assert entry["response"] == final
    assert entry["composition_note"] == messages.composition_note("es")


def test_m_r5_1_a_quiet_messaging_platform_also_withholds(monkeypatch, hermes_home, cited_env):
    """R5 M-R5-1: the retention is not a CLI exception; no route emits the mark while the host is silent."""
    final = run_cited(monkeypatch, hermes_home, platform="telegram")
    assert verifier.SEAL not in final
    assert entry_of(hermes_home)["delivery"]["seal"] is False


def test_m_r5_1_the_record_says_in_words_what_it_stores(monkeypatch, hermes_home, cited_env):
    """R5 M-R5-2 / D11.3: the row is the plugin's composition, never a record of the terminal message."""
    run_cited(monkeypatch, hermes_home, platform="cli")
    note = entry_of(hermes_home)["composition_note"]
    assert "host puede mostrar borradores" in note
    assert "no es constancia del mensaje terminal" in note


def test_m_r5_1_the_withheld_note_names_the_unaccredited_delivery(monkeypatch, tmp_path):
    """R5 M-R5-1: the note says why, instead of leaving a quiet but unaccredited answer unexplained."""
    (tmp_path / "config.yaml").write_text(QUIET, encoding="utf-8")
    note = delivery.withheld_note(delivery.snapshot("cli", home=tmp_path))
    assert "per-turn delivery policy" in note
    assert "withheld" in note
    assert render.SEAL not in note
