"""Permanent regressions of the sixth review: the installed skill and the public documents.

R6 M-R6-2. The skill the plugin registers with ``ctx.register_skill`` still said that the plugin adds the
seal and showed a render that ends in ``Verified by Cited``, and the public documents still universalised the
terminal message and the record (``community-hermes/docs/mcp.md``, both READMEs and
``docs/upstream-proposal.md``). This module reads the skill the plugin **really registers** and hunts the old
promises in the public documents with a list of **forbidden** phrases; it is not enough to check that the new
phrases appear.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
COMMUNITY = REPO.parent / "community-hermes"
SKILL = REPO / "hermes_cited" / "skills" / "cited" / "SKILL.md"

ENGLISH = (
    "For a cited turn that reaches the hook, the plugin's composition is the documentary render, the fixed "
    "refusal or the operational refusal; the host may add text afterwards."
)
SPANISH = (
    "Para un turno cited que llega al hook, la composición del plugin es el render documental, la negativa "
    "fija o la negativa operativa; el host puede agregar texto después."
)

#: The promises of the pre-D11 contract. Every one of them is a claim about the terminal message or about
#: the record of what was delivered, and D11 bounds the plugin to its own composition.
FORBIDDEN = (
    "the delivered text is exactly one of",
    "is always exactly one of three",
    "is one of three fixed forms",
    "one of three fixed forms",
    "the promise is about the final message",
    "the promise of cited mode is about the **final message**",
    "every delivered response appends one line",
    "one hash-chained jsonl line per delivered answer",
    "consistency record of what was delivered",
    "two pending host-side contracts",
    "and the seal `verified by cited`",
    "el texto entregado es exactamente uno de",
    "el texto de un turno cited siempre es uno de los tres",
    "cada respuesta entregada agrega un renglón",
    "registro local de consistencia encadenado por hash de lo que se entregó",
    "la promesa del modo cited es sobre el **mensaje final**",
    "los dos contratos pendientes",
)

DOCUMENTS = {
    "README.md": (REPO / "README.md", ENGLISH),
    "README.es.md": (REPO / "README.es.md", SPANISH),
    "docs/upstream-proposal.md": (REPO / "docs" / "upstream-proposal.md", ENGLISH),
    "hermes_cited/skills/cited/SKILL.md": (SKILL, ENGLISH),
    "community-hermes/docs/mcp.md": (COMMUNITY / "docs" / "mcp.md", ENGLISH),
}


def normalized(text) -> str:
    return " ".join(str(text or "").split())


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
        self.skills[name] = {"path": path, "description": description}


def registered_skill():
    """The skill the plugin really registers, read from the path it passes to the loader."""
    from hermes_cited import plugin

    context = FakeContext()
    plugin.register(context)
    assert "cited" in context.skills, "the plugin did not register a cited skill"
    path = Path(context.skills["cited"]["path"])
    assert path.exists(), path
    return path.read_text(encoding="utf-8")


def fenced_blocks(text):
    return re.findall(r"```[^\n]*\n(.*?)```", text, re.DOTALL)


def test_m_r6_2_the_registered_skill_declares_the_retained_seal():
    """R6 M-R6-2: the installed skill says that this version does not emit the seal, with a real render."""
    text = registered_skill()
    flat = normalized(text)
    assert ENGLISH.lower() in flat.lower(), "the skill does not carry the composition wording"
    assert "not emitted" in flat or "does not emit" in flat, "the skill does not say the seal is not emitted"
    assert "plugin's composition" in flat
    assert "drafts" in flat
    assert "empty" in flat
    for forbidden in FORBIDDEN:
        assert forbidden not in flat.lower(), forbidden
    blocks = fenced_blocks(text)
    assert blocks, "the skill shows no real render"
    for block in blocks:
        assert "Verified by Cited" not in block, block
        assert "Note on delivery:" in block, block


@pytest.mark.parametrize("name", sorted(DOCUMENTS))
def test_m_r6_2_no_public_document_keeps_an_old_promise(name):
    """R6 M-R6-2: the forbidden phrases of the previous contract are gone from every public document."""
    path, wording = DOCUMENTS[name]
    assert path.exists(), path
    flat = normalized(path.read_text(encoding="utf-8"))
    assert wording.lower() in flat.lower(), name
    for forbidden in FORBIDDEN:
        assert forbidden not in flat.lower(), "{0}: {1}".format(name, forbidden)


@pytest.mark.parametrize(
    "name",
    ["README.md", "README.es.md", "docs/upstream-proposal.md", "community-hermes/docs/mcp.md"],
)
def test_m_r6_2_the_three_pending_contracts_are_aligned(name):
    """R6 M-R6-2: the count and the names of the pending contracts agree in every public document."""
    path, _wording = DOCUMENTS[name]
    flat = normalized(path.read_text(encoding="utf-8")).lower()
    assert (
        "three contracts" in flat
        or "tres contratos" in flat
        or "three pending host-side contracts" in flat
    ), name
    assert "two contracts" not in flat and "dos contratos" not in flat, name
    if name == "README.es.md":
        markers = ("retención síncrona", "vacía", "frontera")
    else:
        markers = ("synchronous retention", "empty", "footer")
    for marker in markers:
        assert marker in flat, "{0}: {1}".format(name, marker)
