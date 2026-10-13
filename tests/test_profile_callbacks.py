"""Ronda 3, B01: cada callback de ``full`` y su estado de turno pertenecen al perfil registrado.

La revisión R2 de Codex reprodujo tres rutas que ignoraban el perfil activo: el modo por defecto
salía del entorno raíz, ``cited_quote`` devolvía el pasaje del perfil A con el perfil B activo y el
transformador preparaba una escritura de auditoría fuera del perfil dueño. Cada caso de este módulo
falla antes de la corrección y pasa después; todos usan un ``HERMES_HOME`` temporal y un alcance
explícito, nunca la instalación personal.
"""

from __future__ import annotations

import json
from pathlib import Path

import bridge_support as support
from hermes_cited import config, messages, plugin

FULL_TOKEN = "mcp-token-profile-a"  # synthetic
SEARCH_TOKEN = "search-token-profile-b"  # synthetic
SEARCH_URL = "http://127.0.0.1:60124"
EXCERPT = "Only profile A owns this synthetic line."


def full_values(**extra):
    values = {"CITED_BRIDGE_TOOLS": "full", "CITED_URL": "http://127.0.0.1:60123", "CITED_MCP_TOKEN": FULL_TOKEN}
    values.update(extra)
    return values


def search_values(**extra):
    values = support.search_values(SEARCH_URL, SEARCH_TOKEN)
    values.update(extra)
    return values


def envelope(excerpt=EXCERPT, document="profile-a-only.md"):
    return json.dumps(
        {
            "cited_tool": "cited_search",
            "query": "round three",
            "text": "transport",
            "passages": [
                {"n": 1, "document": document, "heading": None, "position": 0, "excerpt": excerpt}
            ],
        }
    )


def hook(context, name, **payload):
    results = [callback(**payload) for callback in context.hooks.get(name, [])]
    return results[0] if len(results) == 1 else results


def test_the_full_default_mode_comes_from_the_registration_profile(tmp_path, monkeypatch):
    """B01: el entorno raíz dice ``dot`` y el perfil A dice ``cited``; gana el perfil."""
    monkeypatch.setenv("CITED_DEFAULT_MODE", "dot")
    with support.bound_scope(full_values(CITED_DEFAULT_MODE="cited"), home=tmp_path / "profile-a"):
        context = support.FakeContext()
        plugin.register(context)
        response = hook(context, "pre_llm_call", session_id="r3-default", turn_id="r3-default", user_message="r3")
    assert response == {"context": plugin.CITED_RULES}


def test_the_full_language_comes_from_the_registration_profile(tmp_path, monkeypatch):
    """B01: el idioma de la composición y de la nota también es el del perfil, no el raíz."""
    writes = []
    monkeypatch.setenv("CITED_LANGUAGE", "es")
    monkeypatch.setattr(plugin.audit, "append_entry", lambda path, entry: writes.append(entry) or entry)
    with support.bound_scope(
        full_values(CITED_DEFAULT_MODE="cited", CITED_LANGUAGE="en"), home=tmp_path / "profile-a"
    ):
        context = support.FakeContext()
        plugin.register(context)
        hook(context, "pre_llm_call", session_id="r3-language", turn_id="r3-language", user_message="r3")
        hook(
            context,
            "post_tool_call",
            tool_name="cited_search",
            args={"query": "round three"},
            result=envelope(),
            session_id="r3-language",
            turn_id="r3-language",
            status="ok",
        )
        hook(context, "transform_llm_output", response_text="MODEL_999", session_id="r3-language", turn_id="r3-language")
    assert writes, "the cited transform must record one row"
    assert writes[0]["composition_note"] == messages.COMPOSITION_NOTE["en"]


def test_the_mode_command_speaks_the_language_of_the_registration_profile(tmp_path, monkeypatch):
    """B01: ``/dot`` responde en el idioma del perfil aunque el entorno raíz diga lo contrario."""
    monkeypatch.setenv("CITED_LANGUAGE", "es")
    with support.bound_scope(full_values(CITED_LANGUAGE="en"), home=tmp_path / "profile-a"):
        context = support.FakeContext()
        plugin.register(context)
        message = context.commands["dot"]("")
    assert message == messages.mode_text("en", "dot")


def test_a_quote_of_another_profile_is_refused(tmp_path):
    """B01: con el perfil B activo, ``cited_quote`` no ve ni devuelve el pasaje del perfil A."""
    with support.bound_scope(full_values(), home=tmp_path / "profile-a"):
        context = support.FakeContext()
        plugin.register(context)
        hook(context, "pre_llm_call", session_id="r3-shared", turn_id="r3-shared", user_message="r3")
        plugin._bind_result(envelope(), {"query": "round three"}, "r3-shared", "r3-shared", "")
    with support.bound_scope(search_values(), home=tmp_path / "profile-b"):
        answer = context.tools["cited_quote"]["handler"](
            {"passage": "P1", "lines": [1]}, session_id="r3-shared", turn_id="r3-shared"
        )
    assert EXCERPT not in answer


def test_a_full_transform_writes_nothing_after_a_profile_switch(tmp_path, monkeypatch):
    """B01: tras cambiar de perfil, el transformador de A no prepara ninguna escritura."""
    writes = []
    monkeypatch.setenv("CITED_DEFAULT_MODE", "dot")
    monkeypatch.setattr(
        plugin.audit, "append_entry", lambda path, entry: writes.append((str(path), entry)) or entry
    )
    with support.bound_scope(full_values(), home=tmp_path / "profile-a"):
        context = support.FakeContext()
        plugin.register(context)
        hook(context, "pre_llm_call", session_id="r3-switch", turn_id="r3-switch", user_message="r3")
    with support.bound_scope(search_values(), home=tmp_path / "profile-b"):
        hook(
            context,
            "transform_llm_output",
            response_text="scope B synthetic output",
            session_id="r3-switch",
            turn_id="r3-switch",
        )
    assert writes == []


def test_a_full_transform_writes_under_the_registration_home_not_the_root(tmp_path, monkeypatch):
    """B01: la bitácora pertenece al perfil dueño aunque el entorno raíz apunte a otro hogar."""
    writes = []
    root = tmp_path / "root"
    root.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(root))
    monkeypatch.setenv("CITED_DEFAULT_MODE", "dot")
    monkeypatch.setattr(
        plugin.audit, "append_entry", lambda path, entry: writes.append(str(path)) or entry
    )
    home = tmp_path / "profile-a"
    with support.bound_scope(full_values(), home=home):
        context = support.FakeContext()
        plugin.register(context)
        hook(context, "pre_llm_call", session_id="r3-home", turn_id="r3-home", user_message="r3")
        hook(context, "transform_llm_output", response_text="plain dot text", session_id="r3-home", turn_id="r3-home")
    assert writes, "the dot transform must record one row"
    assert config.canonical_home(writes[0]) == config.canonical_home(Path(home) / "cited" / "audit.jsonl")


def test_the_mode_state_of_one_profile_never_leaks_into_another(tmp_path, monkeypatch):
    """B01: con un ``ctx.state`` compartido, ``/cited`` del perfil A no cambia el modo del perfil B."""
    monkeypatch.delenv("CITED_DEFAULT_MODE", raising=False)
    shared = support.DictState()
    first = support.FakeContext()
    first.state = shared
    with support.bound_scope(full_values(), home=tmp_path / "profile-a"):
        plugin.register(first)
        first.commands["cited"]("")
    second = support.FakeContext()
    second.state = shared
    with support.bound_scope(full_values(), home=tmp_path / "profile-b"):
        plugin.register(second)
        response = hook(second, "pre_llm_call", session_id="r3-leak", turn_id="r3-leak", user_message="r3")
    assert response is None, "profile B must keep its own default dot, not the /cited of profile A"
