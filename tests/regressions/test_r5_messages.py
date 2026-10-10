"""Permanent regressions of the fifth review: the commands and the visible promise.

R5 M-R5-5. The review executed the handlers of both modes and read the promises of round 4: ``/cited``
still said the answer carries the seal and ``/dot`` still said that nothing is replaced. The handlers now
state the scope of the final message, the condition of the seal and the removal of the mark in any answer.
"""

from __future__ import annotations

from hermes_cited import messages, plugin


class State:
    def __init__(self):
        self.data = {}

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value


class FakeContext:
    def __init__(self):
        self.state = State()
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


def commands(monkeypatch):
    monkeypatch.setenv("CITED_DEFAULT_MODE", "dot")
    context = FakeContext()
    plugin.register(context)
    return context.commands


def test_m_r5_5_the_cited_command_states_the_scope_and_the_condition_of_the_seal(monkeypatch):
    """R5 M-R5-5: ``/cited`` used to promise the seal with no condition."""
    text = commands(monkeypatch)["cited"]("")
    assert "renglones" in text
    assert "sello" in text
    assert "no se emite" in text
    assert "mensaje final" in text
    assert "borradores" in text
    assert "con su fuente y su sello" not in text


def test_m_r5_5_the_dot_command_states_that_the_mark_is_removed_anywhere(monkeypatch):
    """R5 M-R5-5: ``/dot`` used to say that no answer is replaced, without naming the mark."""
    text = commands(monkeypatch)["dot"]("")
    assert "cualquier respuesta" in text
    assert "entidades" in text
    assert "enlaces" in text
    assert "ninguna respuesta se sella ni se reemplaza" not in text


def test_m_r5_5_the_messages_come_from_the_module_the_plugin_ships(monkeypatch):
    """R5 M-R5-5: the fixtures read the returned text, not a document that quotes it."""
    handlers = commands(monkeypatch)
    assert handlers["cited"]("") == messages.mode_text("es", "cited")
    assert handlers["dot"]("") == messages.mode_text("es", "dot")


def test_m_r5_5_the_english_commands_say_the_same(monkeypatch):
    monkeypatch.setenv("CITED_LANGUAGE", "en")
    handlers = commands(monkeypatch)
    cited = handlers["cited"]("")
    dot = handlers["dot"]("")
    assert "is not emitted" in cited and "final message" in cited
    assert "any answer" in dot and "entities" in dot
