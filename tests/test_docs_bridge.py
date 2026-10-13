"""H22: the two READMEs and the technical manual document the search mode and its pin.

These are the README/manual tests of task 1.4. They fail until step 6.1 writes the documentation, so the
documentation they demand is the contract, not a formality.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def read(name: str) -> str:
    return (REPO / name).read_text(encoding="utf-8")


def test_the_english_readme_documents_the_search_mode():
    text = read("README.md")
    for marker in (
        "CITED_BRIDGE_TOOLS",
        "CITED_SEARCH_TOKEN",
        "/api/chassis/mcp",
        "search",
        "full",
    ):
        assert marker in text, marker
    flat = " ".join(text.split()).lower()
    assert "writes nothing" in flat
    assert "tools/list" in flat
    assert "tools/call" in flat
    assert "per-profile" in flat or "--profile" in flat


def test_the_english_readme_pins_the_install_by_commit():
    text = read("README.md")
    assert "plugins install" in text
    assert "--profile" in text
    assert "--ref" in text
    assert "git archive --format=tar" in text


def test_the_spanish_readme_documents_the_search_mode():
    text = read("README.es.md")
    for marker in (
        "CITED_BRIDGE_TOOLS",
        "CITED_SEARCH_TOKEN",
        "/api/chassis/mcp",
    ):
        assert marker in text, marker
    flat = " ".join(text.split()).lower()
    assert "no escribe" in flat
    assert "--profile" in text
    assert "--ref" in text
    assert "git archive --format=tar" in text


def test_the_technical_manual_exists_and_covers_the_contract():
    path = REPO / "docs" / "technical-manual.md"
    assert path.is_file(), "docs/technical-manual.md is part of H22"
    text = path.read_text(encoding="utf-8")
    for marker in (
        "CITED_BRIDGE_TOOLS",
        "CITED_SEARCH_TOKEN",
        "CITED_MCP_TOKEN",
        "/api/chassis/mcp",
        "/api/mcp",
        "tools/list",
        "tools/call",
        "--profile",
        "--ref",
        "git archive --format=tar",
    ):
        assert marker in text, marker
    flat = " ".join(text.split()).lower()
    assert "scope" in flat
    assert "writes nothing" in flat or "no escribe" in flat
    assert "redirect" in flat


@pytest.mark.parametrize("name", ["README.md", "README.es.md", "docs/technical-manual.md"])
def test_the_documents_never_carry_a_secret(name):
    text = read(name)
    for marker in ("Bearer ey", "cited-search-token-", "mcp-token-5e1c0a"):
        assert marker not in text
