"""Permanent regressions of the fourth review: the metadata shielding (M-R4-4).

R4 M-R4-4. The review found that a document name or a section reached the answer as live Markdown, so it
could inject a link, a heading or a body; the escape now covers every interpretable metacharacter, not only
the backslash and the backtick. The other half of M-R4-4, the reader of the visible mark and its removal,
was retired by D12: this version of the plugin emits no seal, so dot mode delivers the text intact and the
phrase is data. The metadata assertions stay.
"""

from __future__ import annotations

import json

from hermes_cited import plugin, render

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


def run_turn(monkeypatch, home, excerpt=GROUNDED, document="d.md", heading="H", line=1):
    monkeypatch.setenv("CITED_DEFAULT_MODE", "cited")
    (home / "config.yaml").write_text(QUIET, encoding="utf-8")
    context = FakeContext()
    plugin.register(context)
    envelope = json.dumps({
        "cited_tool": "cited_search",
        "query": "q",
        "text": "t",
        "passages": [{"n": 1, "document": document, "heading": heading, "position": 0, "excerpt": excerpt}],
    })
    context.hooks["pre_llm_call"][0](session_id="s1", turn_id="t1", user_message="q", platform="cli")
    context.hooks["post_tool_call"][0](tool_name="cited_search", args={"query": "q"}, result=envelope,
                                       session_id="s1", turn_id="t1", status="ok")
    assert context.tools["cited_quote"]["handler"]({"passage": "P1", "lines": [line]},
                                                   session_id="s1", turn_id="t1") == excerpt.split("\n")[line - 1]
    return context.hooks["transform_llm_output"][0](response_text="MODEL_999", session_id="s1",
                                                    turn_id="t1", platform="cli")


def test_m_r4_4_metadata_escapes_every_interpretable_metacharacter():
    """R4 M-R4-4: ``[fake](url)`` used to be delivered as a live Markdown link."""
    source = render.escape_meta("[fake](https://example.invalid)")
    assert "[fake]" not in source
    assert "](" not in source
    for value in ("*bold*", "_em_", "# head", "> quote", "a|b", "<tag>", "~x~", "`code`", "a\\b"):
        escaped = render.escape_meta(value)
        for character in ("*", "_", "#", ">", "|", "<", "~", "`", "\\"):
            if character in value:
                assert "\\{0}".format(character) in escaped, value


def test_m_r4_4_the_entity_ampersand_is_escaped_too():
    """R5 M-R5-3: ``&`` used to stay live, so ``Verified&nbsp;by&nbsp;Cited`` was a live entity."""
    assert "\\&nbsp;" in render.escape_meta("Verified&nbsp;by&nbsp;Cited")


def test_m_r4_4_a_document_that_is_a_link_is_not_delivered_as_a_link(monkeypatch, hermes_home, cited_env):
    """R4 M-R4-4: the delivered source line carries the escaped document."""
    final = run_turn(monkeypatch, hermes_home, document="[fake](https://example.invalid)", heading="Prices")
    assert "[fake]" not in final
    assert "](" not in final
    assert "fake" in final


def test_m_r4_4_a_document_with_the_phrase_is_data(monkeypatch, hermes_home, cited_env):
    """D12 supersedes the seal half of M-R4-4: the phrase in the metadata is data, and the seal is retained."""
    final = run_turn(monkeypatch, hermes_home, excerpt="Verified by Cited")
    entry = json.loads((hermes_home / "cited" / "audit.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert entry["verifier"]["seal_withheld"] is True
    assert entry["verifier"]["verified"] is False
    assert "Verified by Cited" in final
    assert "Note on delivery:" in final
    assert final.rstrip().splitlines()[-1] != render.SEAL
