"""Permanent regressions of D12.3 and D12.4: the documents state the retired mark honestly.

D12.3: in plain language, nothing in dot mode is verified whatever the text says, and this version of the
plugin writes no seal, so the phrase ``Verified by Cited`` in an answer never comes from the plugin. D12.4:
the future activation of the seal, in ``docs/upstream-proposal.md`` and in ``design.md``, requires
protecting the reserved mark again with the render semantics of the host, checked against its consumer.

The check of ``community-hermes/docs/mcp.md`` is skipped with an explicit reason when ``CITED_DOCS_REPO`` is
not set, so the suite still runs in an isolated checkout.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

OMITTED_REASON = (
    "CITED_DOCS_REPO is not set: the cross-repository check of community-hermes/docs/mcp.md is omitted"
)

ENGLISH_DOT = "nothing in dot mode is verified"
ENGLISH_NO_SEAL = "never comes from the plugin"
ENGLISH_ACTIVATION = "protect the reserved mark again"
SPANISH_DOT = "nada en modo dot está verificado"
SPANISH_NO_SEAL = "nunca viene del plugin"


def normalized(text) -> str:
    return " ".join(str(text or "").split())


def community_documents():
    value = os.environ.get("CITED_DOCS_REPO", "").strip()
    return Path(value) / "docs" / "mcp.md" if value else None


def read(path) -> str:
    return normalized(path.read_text(encoding="utf-8"))


def change_dir(name: str) -> Path:
    """A change lives in `openspec/changes/<name>` while open and in `archive/<date>-<name>` once archived."""
    changes = REPO / "openspec" / "changes"
    if (changes / name).is_dir():
        return changes / name
    archived = sorted(changes.glob(f"archive/*-{name}"))
    assert archived, f"the change {name} is neither open nor archived"
    return archived[-1]


@pytest.mark.parametrize(
    "name",
    ["README.md", "README.es.md", "docs/upstream-proposal.md", "hermes_cited/skills/cited/SKILL.md"],
)
def test_d12_the_public_documents_state_the_retired_mark(name):
    text = read(REPO / name).lower()
    if name == "README.es.md":
        assert SPANISH_DOT in text, name
        assert SPANISH_NO_SEAL in text, name
    else:
        assert ENGLISH_DOT in text, name
        assert ENGLISH_NO_SEAL in text, name


def test_d12_the_future_activation_requires_the_mark_protection_again():
    proposal = read(REPO / "docs" / "upstream-proposal.md").lower()
    design = read(change_dir("hermes-plugin-r4") / "design.md").lower()
    assert ENGLISH_ACTIVATION in proposal, "the proposal does not require the mark protection again"
    assert ENGLISH_ACTIVATION in design, "the design does not require the mark protection again"


def test_d12_the_cited_route_document_states_the_retired_mark():
    path = community_documents()
    if path is None:
        pytest.skip(OMITTED_REASON)
    text = read(path).lower()
    assert ENGLISH_DOT in text, path
    assert ENGLISH_NO_SEAL in text, path
