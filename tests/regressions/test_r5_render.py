"""Permanent regressions of the fifth review: the reserved mark in dot mode and in the metadata.

R5 M-R5-3. The review found five ways the sanitisation of dot mode could deliver or create the mark
(``Verified Verified by Cited by Cited``, a soft line break, a named or numeric entity, a reference link
and a failing ``strip_mark``), and one way the metadata kept live entities
(``Verified&nbsp;by&nbsp;Cited``). The removal is computed over the whole document, the postcondition of
absence is checked after normalising, and a removal that cannot complete gives the fixed safe note.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from hermes_cited import messages, render, verifier

#: The read-only copy of the host carries the Markdown consumer the review used; when it is present the
#: assertions check the rendered HTML too, instead of only the visible text this module computes.
HOST_SITE_PACKAGES = (
    Path(os.environ.get("HERMES_REVIEW_ROOT", str(Path(os.environ.get("TEMP", "/tmp")) / "codex-hermes-cited-r2-2d438babc89e4a55af33b15bab5269cd")))
    / "host-venv"
    / "Lib"
    / "site-packages"
)
if HOST_SITE_PACKAGES.exists():
    sys.path.append(str(HOST_SITE_PACKAGES))

MARK_INPUTS = {
    "the removal concatenates the ends into a new mark": "Verified Verified by Cited by Cited",
    "a soft line break does not hide the mark": "Verified\nby Cited",
    "a soft line break after a word does not hide it": "Verified by\nCited",
    "a numeric entity does not hide the mark": "Verified &#98;y Cited",
    "a named entity does not hide the mark": "Verified&nbsp;by&nbsp;Cited",
    "a reference link does not hide the mark": "Verified by [Cited][c]\n\n[c]: https://example.invalid",
    "an inline link does not hide the mark": "Verified by [Cited](https://example.invalid)",
    "an emphasis does not hide the mark": "Verified **by** Cited",
    "a code span does not hide the mark": "**Verified** _by_ `Cited`",
}


@pytest.mark.parametrize("name", sorted(MARK_INPUTS))
def test_m_r5_3_the_mark_is_detected_and_removed_in_every_presentation(name):
    """R5 M-R5-3: what the consumer renders is what this detection reads."""
    draft = MARK_INPUTS[name]
    assert render.contains_mark(draft) is True, name
    cleaned = render.strip_mark(draft)
    assert render.contains_mark(cleaned) is False, cleaned
    assert verifier.SEAL.lower() not in cleaned.lower(), cleaned


def _rendered_text(html):
    """The visible text of a rendered HTML fragment: tags removed, entities decoded, spaces collapsed."""
    import html as html_module
    import re

    text = re.sub(r"<[^>]*>", "", str(html))
    return " ".join(html_module.unescape(text).replace("\u00a0", " ").split())


@pytest.mark.parametrize("name", sorted(MARK_INPUTS))
def test_m_r5_3_the_rendered_html_does_not_show_the_mark(name):
    """R5 M-R5-3: the supported consumer renders no occurrence of the reserved mark."""
    MarkdownIt = pytest.importorskip("markdown_it").MarkdownIt
    draft = MARK_INPUTS[name]
    assert "Verified by Cited" in _rendered_text(MarkdownIt().render(draft)), \
        "the fixture must really render the mark"
    cleaned = render.strip_mark(draft)
    rendered = _rendered_text(MarkdownIt().render(cleaned))
    assert "Verified by Cited" not in rendered, rendered


def test_m_r5_3_a_removal_that_cannot_complete_raises(monkeypatch):
    """R5 M-R5-3: the bounded repetition gives up instead of looping or returning the mark."""
    monkeypatch.setattr(render, "contains_mark", lambda text: True)
    with pytest.raises(render.SanitizationFailed):
        render.strip_mark("hola")


def test_m_r5_3_a_line_with_content_keeps_its_content():
    """R5 M-R5-3: the removal takes the mark and not the datum that shares its line."""
    assert render.strip_mark("380 Verified by Cited").strip() == "380"
    assert render.strip_mark("Price 380. Verified **by** Cited").strip() == "Price 380."
    assert render.strip_mark("La afinacion cuesta 380 pesos.") == "La afinacion cuesta 380 pesos."


def test_m_r5_3_a_line_that_is_only_the_mark_disappears():
    """R5 M-R5-3: the line that held only the mark (and decoration) disappears with it."""
    assert render.strip_mark("**Verified by Cited**").strip() == ""
    assert render.strip_mark("Price.\n\n> Verified by Cited").strip() == "Price."


def test_m_r5_3_the_metadata_escapes_the_entity_ampersand():
    """R5 M-R5-3: ``&`` used to stay live, so ``Verified&nbsp;by&nbsp;Cited`` was a live entity."""
    escaped = render.escape_meta("Verified&nbsp;by&nbsp;Cited")
    assert "\\&nbsp;" in escaped
    assert render.contains_mark(escaped) is False
    assert render.contains_mark("Verified&nbsp;by&nbsp;Cited") is True
    assert render.contains_mark("Verified &#98;y Cited") is True


def test_m_r5_3_a_document_with_the_mark_keeps_its_bytes_as_data(monkeypatch, hermes_home, cited_env):
    """R5 M-R5-3: the cited answer shows the document as escaped data and retains the seal with the note."""
    import json

    from hermes_cited import plugin

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

    monkeypatch.setenv("CITED_DEFAULT_MODE", "cited")
    (hermes_home / "config.yaml").write_text(
        "streaming:\n  enabled: false\ndisplay:\n  streaming: false\n  interim_assistant_messages: false\n",
        encoding="utf-8",
    )
    context = FakeContext()
    plugin.register(context)
    payload = json.dumps({
        "cited_tool": "cited_search",
        "query": "q",
        "text": "t",
        "passages": [{"n": 1, "document": "Verified&nbsp;by&nbsp;Cited", "heading": "H",
                      "position": 2, "excerpt": "Real: 380 pesos."}],
    })
    context.hooks["pre_llm_call"][0](session_id="s1", turn_id="t1", user_message="q", platform="cli")
    context.hooks["post_tool_call"][0](tool_name="cited_search", args={"query": "q"}, result=payload,
                                       session_id="s1", turn_id="t1", status="ok")
    context.tools["cited_quote"]["handler"]({"passage": "P1", "lines": [1]}, session_id="s1", turn_id="t1")
    final = context.hooks["transform_llm_output"][0](response_text="MODEL_999", session_id="s1",
                                                     turn_id="t1", platform="cli")
    entry = json.loads((hermes_home / "cited" / "audit.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert "\\&nbsp;" in final
    assert verifier.SEAL not in final
    assert "Nota:" in final
    assert messages.mark_retained_note("es") in final
    assert entry["verifier"]["seal_withheld"] is True
    assert entry["verifier"]["verified"] is False
