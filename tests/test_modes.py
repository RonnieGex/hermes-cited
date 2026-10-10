"""The two conversation modes: /cited, /dot and CITED_DEFAULT_MODE (H4)."""

from __future__ import annotations

from hermes_cited import modes


class DictState:
    def __init__(self):
        self.data = {}

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value


def test_the_default_mode_is_dot(monkeypatch):
    monkeypatch.delenv("CITED_DEFAULT_MODE", raising=False)
    assert modes.resolve_mode(DictState(), "s1") == "dot"


def test_the_environment_sets_the_initial_mode(monkeypatch):
    monkeypatch.setenv("CITED_DEFAULT_MODE", "cited")
    assert modes.resolve_mode(DictState(), "s1") == "cited"


def test_an_unknown_default_mode_reads_as_dot(monkeypatch):
    monkeypatch.setenv("CITED_DEFAULT_MODE", "banana")
    assert modes.resolve_mode(DictState(), "s1") == "dot"


def test_the_command_writes_the_profile_key_without_a_session(monkeypatch):
    monkeypatch.delenv("CITED_DEFAULT_MODE", raising=False)
    state = DictState()
    modes.set_mode(state, "cited")
    assert state.get("mode.profile") == "cited"
    assert modes.resolve_mode(state, "s1") == "cited"


def test_a_session_key_wins_over_the_profile(monkeypatch):
    monkeypatch.delenv("CITED_DEFAULT_MODE", raising=False)
    state = DictState()
    modes.set_mode(state, "cited")
    modes.set_mode(state, "dot", session_id="s1")
    assert modes.resolve_mode(state, "s1") == "dot"
    assert modes.resolve_mode(state, "s2") == "cited"


def test_the_profile_wins_over_the_environment(monkeypatch):
    monkeypatch.setenv("CITED_DEFAULT_MODE", "dot")
    state = DictState()
    modes.set_mode(state, "cited", session_id="s1")
    assert modes.resolve_mode(state, "s1") == "cited"


def test_slash_cited_turns_the_mode_on(monkeypatch):
    monkeypatch.delenv("CITED_DEFAULT_MODE", raising=False)
    state = DictState()
    handler = modes.mode_command(state, "cited")
    message = handler("")
    assert "cited" in message.lower()
    assert modes.resolve_mode(state, "") == "cited"


def test_slash_dot_turns_the_mode_off(monkeypatch):
    monkeypatch.setenv("CITED_DEFAULT_MODE", "cited")
    state = DictState()
    modes.mode_command(state, "dot")("")
    assert modes.resolve_mode(state, "") == "dot"


def test_current_session_key_is_empty_outside_the_gateway(monkeypatch):
    monkeypatch.setenv("HERMES_SESSION_KEY", "")
    monkeypatch.setenv("HERMES_SESSION_ID", "")
    assert modes.current_session_key() == ""


def test_the_session_key_candidates_include_the_bound_session(monkeypatch):
    state = DictState()
    monkeypatch.setattr(modes, "current_session_key", lambda: "gw-1")
    modes.set_mode(state, "cited", session_id="gw-1")
    assert modes.resolve_for_turn(state, "agent-session", None) == "cited"


def test_the_mode_is_dot_when_nothing_is_configured(monkeypatch):
    monkeypatch.delenv("CITED_DEFAULT_MODE", raising=False)
    assert modes.resolve_for_turn(DictState(), "s1", None) == "dot"
