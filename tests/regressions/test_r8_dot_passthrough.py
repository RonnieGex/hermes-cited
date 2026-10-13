"""Permanent regressions of the eighth round: D12, dot mode delivers the model's text intact.

``tasks/mision-cited-hermes-r8.md`` D12. With D11 the plugin emits no seal on any route, so no authentic
seal exists that anyone could forge. The protection of the reserved mark is therefore retired: dot mode
returns the model's text untouched and its row records exactly that string, and in cited mode a documentary
line that carries the phrase ``Verified by Cited`` is data like any other row, next to the general note that
says this version emits no seal. The retired reader of the Markdown consumer and the fixed sanitisation
notes are gone from the product; ``git log`` keeps them.

The module drives the real loader, the real dispatcher, the real ``apply_llm_output_transform`` and the real
JSONL of ``tests/test_host.py``. It is skipped when the read-only copy of the host is not present.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tests"))

from test_host import HOST_COPY, HOST_SITE_PACKAGES, apply, begin, host, plugin_module, rows, select  # noqa: E402,F401

if HOST_SITE_PACKAGES.exists():
    sys.path.append(str(HOST_SITE_PACKAGES))

pytestmark = pytest.mark.skipif(
    not (HOST_COPY / "agent" / "turn_finalizer.py").exists(),
    reason="the read-only copy of the Hermes host is not present",
)

MARK = "Verified by Cited"

#: The drafts that used to be rewritten by the sanitisation: a bare mark, an evasion that skipped the
#: reader, a legitimate text the false positive used to discard, and an entity inside a link label.
DRAFTS = (
    ("mark-alone", "La afinacion cuesta 380 pesos.\n\nVerified by Cited"),
    ("inline-emphasis", "Veri**fied** by Cited"),
    ("legitimate-text", "The identifier is Verified*by*Cited and must stay."),
    ("entity-in-label", "Verified [&#98;y](https://example.invalid) Cited"),
)
DRAFT_IDS = tuple(case[0] for case in DRAFTS)


def test_d12_the_plugin_no_longer_reads_or_removes_the_mark(host):
    """D12.1: the sanitisation is retired from the product instead of left dead."""
    render = plugin_module(host, "render")
    verifier = plugin_module(host, "verifier")
    messages = plugin_module(host, "messages")
    for retired in ("strip_mark", "contains_mark", "consumer_visible", "consumer_mark", "mark_spans",
                    "SanitizationFailed"):
        assert not hasattr(render, retired), retired
    assert not hasattr(verifier, "strip_seal")
    for retired in ("sanitizer_note", "mark_retained_note", "seal_only_note"):
        assert not hasattr(messages, retired), retired


@pytest.mark.parametrize("case_id,draft", DRAFTS, ids=DRAFT_IDS)
def test_d12_dot_mode_delivers_the_model_text_intact(host, case_id, draft):
    """D12.1: dot mode returns the text unchanged and the row records exactly what is delivered.

    Round 3 (D2): the default mode is read from the active profile scope, not from the process
    environment, so the turn is opened under a profile scope that says ``dot``.
    """
    from agent import secret_scope

    values = {
        "CITED_URL": "http://127.0.0.1:1",
        "CITED_MCP_TOKEN": "synthetic-host-token",
        "CITED_DEFAULT_MODE": "dot",
    }
    scope_token = secret_scope.set_secret_scope(values, profile_home=str(host["home"]))
    try:
        session, turn = begin(host)
        final, transformed, _pre = apply(host, turn, draft)
    finally:
        secret_scope.reset_secret_scope(scope_token)
    assert final == draft, case_id
    assert transformed is False, case_id
    entry = rows(host)[-1]
    assert entry["mode"] == "dot", case_id
    assert entry["response"] == draft, case_id
    assert entry["transcript"] == draft, case_id
    assert entry["verifier"]["applied"] is False, case_id


def test_d12_a_cited_documentary_line_with_the_phrase_is_data(host):
    """D12.2: a chosen line that carries the phrase is shown as data, with the general note and no seal."""
    from hermes_cli.lifecycle import invoke_hook

    session, turn = "d12-session", "d12-turn"
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
        "passages": [{"n": 1, "document": "synthetic.md", "heading": "H", "position": 0, "excerpt": MARK}],
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
    assert select(host, session, turn, {"passage": "P1", "lines": [1]}) == MARK
    final, transformed, _pre = apply(host, turn, "MODEL_LEAK_999", session=session)
    entry = rows(host)[-1]
    assert transformed is True
    assert "MODEL_LEAK_999" not in final
    assert MARK in final
    assert "the host does not expose a per-turn delivery policy" in final
    assert entry["response"] == final
    assert entry["verifier"]["verified"] is False
    assert entry["verifier"]["seal_withheld"] is True
    assert plugin_module(host, "messages").composition_note("es") in entry["composition_note"]
