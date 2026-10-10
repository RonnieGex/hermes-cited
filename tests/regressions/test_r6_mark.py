"""Permanent regressions of the sixth review: the reserved mark composed with entities and references.

R6 M-R6-1. The sixth review reproduced six dot-mode evasions and three cited-mode omissions of the reserved
mark ``Verified by Cited``: an entity inside a link label (``Verified [&#98;y](https://example.invalid)
Cited``), an entity inside the label of an inline link, a whole link whose label carries the mark, a shortcut
reference resolved against its definition, an explicit reference with an entity, and an HTML ``<br>``. The
detection now reads the visible text of the same Markdown consumer the host uses (``markdown_it``), the
removal maps that text back to the spans of the original document, and the postcondition is checked on the
render and not on the detector again.

The module drives the real loader, the real dispatcher, the real ``apply_llm_output_transform`` and the real
JSONL of ``tests/test_host.py``, and it asserts the compliance of the product — the mark is absent from the
visible text of the render in dot mode and the fixed documentary note is present in cited mode — with the
independent renderer instead of the plugin's own detector. It is skipped when the read-only copy of the host
is not present.
"""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tests"))

from test_host import HOST_COPY, HOST_SITE_PACKAGES, apply, begin, host, plugin_module, rows, select  # noqa: E402,F401

if HOST_SITE_PACKAGES.exists():
    sys.path.append(str(HOST_SITE_PACKAGES))

from markdown_it import MarkdownIt  # noqa: E402

pytestmark = pytest.mark.skipif(
    not (HOST_COPY / "agent" / "turn_finalizer.py").exists(),
    reason="the read-only copy of the Hermes host is not present",
)

MARK = "Verified by Cited"

#: The nine counterexamples of the review's annex: six dot-mode drafts and, as documentary rows, the first
#: three of them (R6 M-R6-1).
DOT_DRAFTS = (
    "Verified [&#98;y](https://example.invalid) Cited",
    "Verified by [Ci&#116;ed](https://example.invalid)",
    "[Verified &#98;y Cited](https://example.invalid)",
    "Verified by [Cited]\n\n[Cited]: https://example.invalid",
    "Verified by [Ci&#116;ed][c]\n\n[c]: https://example.invalid",
    "Verified<br>by Cited",
)
CITED_DRAFTS = DOT_DRAFTS[:3]
IDS = ("entity-in-inline-label", "entity-in-second-label", "mark-is-the-label",
       "shortcut-reference", "explicit-reference-entity", "html-line-break")


def visible(value):
    """The render of the supported consumer and the visible text a reader of that render receives."""
    rendered = MarkdownIt().render(str(value or ""))
    return rendered, " ".join(html.unescape(re.sub(r"<[^>]+>", " ", rendered)).split())


def dot_final(host, monkeypatch, draft):
    """Deliver one dot-mode draft through the real loader, dispatcher and finalizer."""
    monkeypatch.setenv("CITED_DEFAULT_MODE", "dot")
    session, turn = begin(host)
    final, transformed, _pre = apply(host, turn, draft)
    return final, transformed


def cited_final(host, draft, session="r6-session", turn="r6-turn"):
    """Deliver one cited-mode row whose chosen line is the draft, through the real hook path."""
    from hermes_cli.lifecycle import invoke_hook

    invoke_hook(
        "pre_llm_call",
        session_id=session,
        turn_id=turn,
        user_message="synthetic",
        platform="cli",
        sender_id="",
    )
    payload = json.dumps({
        "cited_tool": "cited_search",
        "query": "synthetic",
        "text": "transport",
        "passages": [{"n": 1, "document": "synthetic.md", "heading": "H", "position": 0, "excerpt": draft}],
    })
    invoke_hook(
        "post_tool_call",
        tool_name="cited_search",
        args={"query": "synthetic"},
        result=payload,
        session_id=session,
        turn_id=turn,
        status="ok",
    )
    assert select(host, session, turn, {"passage": "P1", "lines": [1]}) == draft
    final, transformed, _pre = apply(host, turn, "MODEL_LEAK_999", session=session)
    assert transformed is True
    return final


@pytest.mark.parametrize("draft", DOT_DRAFTS, ids=IDS)
def test_m_r6_1_dot_removes_the_mark_of_every_combination(host, monkeypatch, draft):
    """R6 M-R6-1: the render of the supported consumer must not show the mark after dot mode."""
    _rendered, draft_text = visible(draft)
    assert MARK in draft_text, "the fixture must really render the mark"
    final, _transformed = dot_final(host, monkeypatch, draft)
    _rendered, text = visible(final)
    assert MARK not in text, text
    assert MARK.lower() not in str(final).lower(), final
    assert rows(host)[-1]["response"] == final


@pytest.mark.parametrize("draft", CITED_DRAFTS, ids=IDS[:3])
def test_m_r6_1_cited_keeps_the_row_and_adds_the_documentary_note(host, draft):
    """R6 M-R6-1: the documentary row stays as data, the note is added and the seal is withheld."""
    messages = plugin_module(host, "messages")

    final = cited_final(host, draft)
    entry = rows(host)[-1]
    assert messages.mark_retained_note("es") in final
    assert "MODEL_LEAK_999" not in final
    assert entry["verifier"]["verified"] is False
    assert entry["verifier"]["seal_withheld"] is True
    assert entry["response"] == final
    assert draft in entry["transcript"]


@pytest.mark.parametrize("draft", DOT_DRAFTS, ids=IDS)
def test_m_r6_1_the_detector_reads_the_render_of_the_consumer(host, draft):
    """R6 M-R6-1: the detector answers True exactly because the supported consumer renders the mark."""
    render = plugin_module(host, "render")
    _rendered, text = visible(draft)
    assert render.contains_mark(draft) is (MARK in text)


def test_m_r6_1_a_removal_that_cannot_complete_delivers_the_fixed_note(host, monkeypatch):
    """R6 M-R6-1: the safe note of M-R5-3 survives the round 7 rewrite of the sanitisation."""
    render = plugin_module(host, "render")
    messages = plugin_module(host, "messages")
    monkeypatch.setattr(render, "mark_spans", lambda text: [])
    monkeypatch.setattr(render, "consumer_mark", lambda text: True)
    final, _transformed = dot_final(host, monkeypatch, "Verified by Cited")
    assert final == messages.sanitizer_note("es")
    assert rows(host)[-1]["response"] == final
