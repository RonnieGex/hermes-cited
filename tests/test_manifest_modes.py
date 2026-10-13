"""H22: the two-mode manifest, the potential catalogs and the unique requirement IDs.

The manifest must implement the semantics of ``fixtures/plugin-search.yaml``: only ``CITED_URL`` is
unconditionally required, both tokens are conditional secrets and the mode defaults to full. The spec
synchronization is checked on a temporary copy, as the task asks.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
from openspec_paths import change_dir
CHANGE = change_dir("search-only-bridge")


def parse_manifest(text: str):
    """A tiny reader for the flat subset of YAML these manifests use; no third-party dependency."""
    top = {}
    lists = {}
    current = None
    item = None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.startswith("  - "):
            payload = raw[4:].strip()
            if ":" in payload and not payload.startswith(('"', "'")):
                key, _, value = payload.partition(":")
                item = {key.strip(): value.strip().strip('"').strip("'")}
                lists.setdefault(current, []).append(item)
            else:
                item = None
                lists.setdefault(current, []).append(payload.strip('"').strip("'"))
            continue
        if raw.startswith("    ") and item is not None and ":" in raw:
            key, _, value = raw.strip().partition(":")
            item[key.strip()] = value.strip().strip('"').strip("'")
            continue
        if not raw.startswith(" ") and ":" in raw:
            key, _, value = raw.partition(":")
            key = key.strip()
            value = value.strip()
            if value:
                if value in ("[]", "{}"):
                    lists[key] = []
                    current = None
                    item = None
                else:
                    top[key] = value.strip('"').strip("'")
                    current = None
                    item = None
            else:
                current = key
                lists.setdefault(key, [])
                item = None
    return top, lists


@pytest.fixture(scope="module")
def manifest():
    return parse_manifest((REPO / "plugin.yaml").read_text(encoding="utf-8"))


def test_the_manifest_is_version_two_modes(manifest):
    top, lists = manifest
    assert top["name"] == "hermes-cited"
    assert top["version"] == "0.2.0"
    assert top["kind"] == "standalone"
    assert "search" in top["description"].lower()
    assert "full" in top["description"].lower()


def test_only_the_url_is_unconditionally_required(manifest):
    _top, lists = manifest
    assert [entry["name"] for entry in lists["requires_env"]] == ["CITED_URL"]
    assert "secret" not in lists["requires_env"][0]


def test_both_tokens_are_conditional_secrets(manifest):
    _top, lists = manifest
    optional = {entry["name"]: entry for entry in lists["optional_env"]}
    assert set(optional) == {
        "CITED_BRIDGE_TOOLS",
        "CITED_SEARCH_TOKEN",
        "CITED_MCP_TOKEN",
        "CITED_TIMEOUT_MS",
        "CITED_DEFAULT_MODE",
        "CITED_LANGUAGE",
    }
    assert optional["CITED_SEARCH_TOKEN"]["secret"] == "true"
    assert optional["CITED_MCP_TOKEN"]["secret"] == "true"
    assert optional["CITED_BRIDGE_TOOLS"].get("secret") is None
    assert "full or search" in optional["CITED_BRIDGE_TOOLS"]["description"].lower()


def test_the_potential_catalogs_are_declared(manifest):
    _top, lists = manifest
    assert sorted(lists["provides_tools"]) == ["cited_ask", "cited_quote", "cited_search"]
    assert sorted(lists["provides_hooks"]) == ["post_tool_call", "pre_llm_call", "transform_llm_output"]
    assert lists["python_dependencies"] == []


def test_the_manifest_implements_the_delivered_fixture(manifest):
    target, target_lists = parse_manifest((CHANGE / "fixtures" / "plugin-search.yaml").read_text(encoding="utf-8"))
    actual, actual_lists = manifest
    assert actual == target
    assert actual_lists == target_lists


def test_the_manifest_carries_no_secret_value():
    text = (REPO / "plugin.yaml").read_text(encoding="utf-8")
    for marker in ("Bearer ", "token-", "sk-", "secret-"):
        assert marker not in text


def test_the_spec_copy_has_unique_requirement_ids(tmp_path):
    source = (CHANGE / "specs" / "hermes-plugin" / "spec.md").read_text(encoding="utf-8")
    copy = tmp_path / "spec.md"
    copy.write_text(source, encoding="utf-8")
    text = copy.read_text(encoding="utf-8")
    ids = re.findall(r"^### Requirement: (H\d+)\b", text, re.MULTILINE)
    assert len(ids) == len(set(ids)), "a duplicated requirement id: {0}".format(ids)
    assert {"H19", "H20", "H21", "H22"} <= set(ids)
    for number in range(1, 19):
        if number == 6:
            continue  # H6 is not restated by this change; it protects both modes and is cited, not redefined
        assert "H{0}".format(number) in ids, "H{0} is missing".format(number)


def test_the_modified_deltas_scope_the_legacy_requirements():
    text = (CHANGE / "specs" / "hermes-plugin" / "spec.md").read_text(encoding="utf-8")
    assert text.count("SHALL apply only to `full` mode") >= 17
    assert "H6 applies to both" in text


def test_the_wire_and_its_schema_are_delivered_together():
    wire = (CHANGE / "wire-contract.md").read_text(encoding="utf-8")
    schema = (CHANGE / "fixtures" / "search-wire-v1.schema.json").read_bytes()
    fixture = json.loads((CHANGE / "fixtures" / "search-wire-v1.json").read_text(encoding="utf-8"))
    import hashlib

    digest = hashlib.sha256(schema).hexdigest()
    assert digest in wire, "the wire contract must pin the schema by SHA-256"
    assert fixture["version"] == 1
    assert fixture["request"]["params"]["name"] == "cited_search"
