"""The repository as Hermes sees it: manifest, entry point, packaged skill, docs (H2, H3, H7)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


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
    for tool in ("cited_search", "cited_ask"):
        assert tool in lists["provides_tools"]
    for hook in ("pre_llm_call", "post_tool_call", "transform_llm_output"):
        assert hook in lists["provides_hooks"]
    for variable in ("CITED_URL", "CITED_MCP_TOKEN"):
        assert variable in lists["requires_env"]


def test_the_entry_point_exposes_register():
    """Load the repository the way hermes_cli.plugins_loader loads a directory plugin."""
    import importlib.util
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


def test_the_packaged_skill_names_both_tools_and_both_modes():
    text = (REPO / "hermes_cited" / "skills" / "cited" / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---")
    assert "cited_search" in text
    assert "cited_ask" in text
    assert "/cited" in text
    assert "/dot" in text


def test_the_two_readmes_exist_and_name_what_was_tested():
    english = (REPO / "README.md").read_text(encoding="utf-8")
    spanish = (REPO / "README.es.md").read_text(encoding="utf-8")
    assert "CITED_URL" in english and "CITED_URL" in spanish
    assert "CITED_MCP_TOKEN" in english and "CITED_MCP_TOKEN" in spanish
    assert "2026-10-09" in english and "2026-10-09" in spanish
