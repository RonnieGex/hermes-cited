"""The repository as Hermes sees it: manifest, entry point, packaged skill, docs (H2, H3, H7, H11)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def change_dir(name: str) -> Path:
    """A change lives in `openspec/changes/<name>` while open and in `archive/<date>-<name>` once archived."""
    changes = REPO / "openspec" / "changes"
    if (changes / name).is_dir():
        return changes / name
    archived = sorted(changes.glob(f"archive/*-{name}"))
    assert archived, f"the change {name} is neither open nor archived"
    return archived[-1]


def read_manifest():
    """A tiny reader for the flat subset of YAML plugin.yaml uses; no third-party dependency."""
    top = {}
    lists = {}
    current = None
    for raw in (REPO / "plugin.yaml").read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.startswith("  - ") and current:
            item = raw.strip()[2:].strip().strip('"').strip("'")
            if item.startswith("name:"):
                item = item.partition(":")[2].strip().strip('"').strip("'")
            lists.setdefault(current, []).append(item)
            continue
        if not raw.startswith(" ") and ":" in raw:
            key, _, value = raw.partition(":")
            key = key.strip()
            value = value.strip()
            if value:
                top[key] = value.strip('"').strip("'")
                current = None
            else:
                current = key
                lists.setdefault(key, [])
    return top, lists


def test_the_manifest_is_valid_and_names_the_plugin():
    top, lists = read_manifest()
    assert top["name"] == "hermes-cited"
    assert top["version"]
    assert top["kind"] == "standalone"
    for tool in ("cited_search", "cited_ask", "cited_quote"):
        assert tool in lists["provides_tools"]
    for hook in ("pre_llm_call", "post_tool_call", "transform_llm_output"):
        assert hook in lists["provides_hooks"]
    for variable in ("CITED_URL", "CITED_MCP_TOKEN"):
        assert variable in lists["requires_env"]


def test_the_manifest_documents_the_new_optional_variables():
    text = (REPO / "plugin.yaml").read_text(encoding="utf-8")
    assert "CITED_LANGUAGE" in text


def test_the_entry_point_exposes_register():
    """Load the repository the way hermes_cli.plugins_loader loads a directory plugin."""
    import sys
    import types

    name = "hermes_plugins.hermes_cited"
    parent = types.ModuleType("hermes_plugins")
    parent.__path__ = []
    sys.modules["hermes_plugins"] = parent
    spec = importlib.util.spec_from_file_location(
        name, REPO / "__init__.py", submodule_search_locations=[str(REPO)]
    )
    module = importlib.util.module_from_spec(spec)
    module.__package__ = name
    module.__path__ = [str(REPO)]
    sys.modules[name] = module
    spec.loader.exec_module(module)
    assert callable(module.register)
    assert module.register.__name__ == "register"


def test_the_packaged_skill_names_the_three_tools_and_both_modes():
    text = (REPO / "hermes_cited" / "skills" / "cited" / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---")
    assert "cited_search" in text
    assert "cited_ask" in text
    assert "cited_quote" in text
    assert "/cited" in text
    assert "/dot" in text
    assert "MCP-only route" in text
    assert "native plugin" in text


def test_the_two_readmes_document_the_plugin_written_render():
    english = (REPO / "README.md").read_text(encoding="utf-8")
    spanish = (REPO / "README.es.md").read_text(encoding="utf-8")
    for text in (english, spanish):
        assert "CITED_URL" in text
        assert "CITED_MCP_TOKEN" in text
        assert "CITED_DEFAULT_MODE" in text
        assert "CITED_LANGUAGE" in text
        assert "cited_quote" in text
        assert "stream-json" in text
        assert "2026-10-10" in text
    assert "Según tus documentos" in spanish
    assert "From your documents" in english


def test_the_readmes_document_the_consistency_record_and_the_delivery_policy():
    english = (REPO / "README.md").read_text(encoding="utf-8").lower()
    assert "internal consistency" in english or "internally consistent" in english
    assert "not tamper-proof" in english
    assert "cited ledger" in english
    assert "api_server" in english
    assert "interim" in english
    assert "auto_tts" in english


def test_the_readmes_no_longer_promise_local_custody():
    """D9: the claims of the retired custody are gone from the documentation."""
    for name in ("README.md", "README.es.md"):
        text = (REPO / name).read_text(encoding="utf-8").lower()
        assert "high-water" not in text
        assert "audit.key" not in text
        assert "checkpoint" not in text


def test_the_upstream_proposal_names_the_hook_it_asks_for():
    proposal = (REPO / "docs" / "upstream-proposal.md").read_text(encoding="utf-8")
    assert "delivery policy" in proposal.lower()
    assert "agent/stream_delivery.py" in proposal
    assert "agent/turn_finalizer.py" in proposal
    assert "api_server_openai_routes.py" in proposal
    assert "No pull request" in proposal or "no pull request" in proposal


def test_the_reports_live_inside_the_change():
    for name in ("hermes-plugin", "hermes-plugin-r2", "hermes-plugin-r3", "hermes-plugin-r4"):
        assert (change_dir(name) / "reports").is_dir(), name


def test_only_two_changes_are_open_at_once():
    """The standard allows at most two open changes per repository (M-R3-7)."""
    changes = REPO / "openspec" / "changes"
    open_changes = sorted(item.name for item in changes.iterdir() if item.is_dir() and item.name != "archive")
    assert len(open_changes) <= 2, open_changes


def test_the_living_spec_exists_once_the_changes_are_archived():
    """Archiving the four rounds consolidated their latest requirements into the living spec."""
    spec = REPO / "openspec" / "specs" / "hermes-plugin" / "spec.md"
    assert spec.is_file()
    text = spec.read_text(encoding="utf-8")
    for number in range(0, 19):
        assert f"### Requirement: H{number} " in text, f"H{number} is missing from the living spec"
