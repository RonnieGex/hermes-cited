"""Permanent regressions of the fourth review: the effective delivery policy of the host.

R4 M-R4-2. The seal decision is taken from the configuration object the host has loaded, frozen at the
start of the cited turn; when the host cannot answer with it provably, the seal is withheld instead of
falling back to the file. A YAML syntax or type error is an unreadable snapshot, never a permissive one.
"""

from __future__ import annotations

import json

import pytest

from hermes_cited import delivery, plugin, verifier

GROUNDED = "- Afinacion de bicicleta: 380 pesos."
QUIET = (
    "streaming:\n  enabled: false\ndisplay:\n  streaming: false\n  interim_assistant_messages: false\n"
)
MALFORMED = "display:\n  interim_assistant_messages: false\nstreaming: [\n"


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


def test_m_r4_2_the_loaded_host_policy_beats_the_file(tmp_path, monkeypatch):
    """R4 M-R4-2: commentary is on in the loaded object while the file says off; the host object wins."""
    (tmp_path / "config.yaml").write_text(QUIET, encoding="utf-8")
    loaded = {"streaming": {"enabled": False}, "display": {"interim_assistant_messages": True}}
    monkeypatch.setattr(delivery, "host_config", lambda home=None: loaded)
    snap = delivery.snapshot("telegram", home=tmp_path)
    assert snap.readable is True
    assert snap.commentary is True
    assert snap.seal is False
    assert snap.as_dict()["source"] == "host"


def test_m_r4_2_a_host_that_cannot_answer_withholds(tmp_path, monkeypatch):
    """R4 M-R4-2: the host module is present but does not answer; C2 withholds the seal."""
    (tmp_path / "config.yaml").write_text(QUIET, encoding="utf-8")

    def broken(home=None):
        raise delivery.UnreadableConfig("the host configuration did not answer")

    monkeypatch.setattr(delivery, "host_config", broken)
    snap = delivery.snapshot("cli", home=tmp_path)
    assert snap.readable is False
    assert snap.seal is False
    assert "unreadable" in snap.reasons


def test_m_r4_2_malformed_yaml_is_unreadable_not_permissive(tmp_path):
    """R4 M-R4-2: ``streaming: [`` used to become a permissive configuration with ``seal=true``."""
    (tmp_path / "config.yaml").write_text(MALFORMED, encoding="utf-8")
    snap = delivery.snapshot("telegram", home=tmp_path)
    assert snap.readable is False
    assert snap.seal is False
    assert "unreadable" in snap.reasons


def test_m_r4_2_the_snapshot_is_frozen_at_the_start(tmp_path, monkeypatch):
    """R4 M-R4-2: the policy is frozen when the turn starts, not re-read later."""
    (tmp_path / "config.yaml").write_text(QUIET, encoding="utf-8")
    loaded = {"display": {"streaming": False, "interim_assistant_messages": False}}
    monkeypatch.setattr(delivery, "host_config", lambda home=None: loaded)
    snap = delivery.snapshot("cli", home=tmp_path)
    assert snap.seal is True and snap.as_dict()["source"] == "host"
    loaded["tts"] = {"auto_tts": True}
    assert snap.tts is False and snap.seal is True


def test_m_r4_2_the_plugin_withholds_when_the_loaded_host_speaks(tmp_path, monkeypatch):
    """R4 M-R4-2: TTS is on in the loaded object and off in the file; the answer is not sealed."""
    monkeypatch.setenv("CITED_DEFAULT_MODE", "cited")
    home = tmp_path / "home"
    (home / "cited").mkdir(parents=True)
    (home / "config.yaml").write_text(QUIET, encoding="utf-8")
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("CITED_MCP_TOKEN", "synthetic")
    monkeypatch.setenv("CITED_URL", "http://127.0.0.1:1")
    monkeypatch.setattr(delivery, "host_config", lambda home=None: {"tts": {"auto_tts": True}})
    context = FakeContext()
    plugin.register(context)
    pre = context.hooks["pre_llm_call"][0]
    post = context.hooks["post_tool_call"][0]
    quote = context.tools["cited_quote"]["handler"]
    transform = context.hooks["transform_llm_output"][0]
    envelope = json.dumps({
        "cited_tool": "cited_search",
        "query": "afinacion",
        "text": "t",
        "passages": [{"n": 1, "document": "d.md", "heading": "H", "position": 0, "excerpt": GROUNDED}],
    })
    pre(session_id="s1", turn_id="t1", user_message="q", platform="cli")
    post(tool_name="cited_search", args={"query": "q"}, result=envelope, session_id="s1", turn_id="t1", status="ok")
    assert quote({"passage": "P1", "lines": [1]}, session_id="s1", turn_id="t1") == GROUNDED
    final = transform(response_text="MODEL_LEAK_999", session_id="s1", turn_id="t1", platform="cli")
    assert GROUNDED in final
    assert verifier.SEAL not in final
    assert "text to speech" in final
