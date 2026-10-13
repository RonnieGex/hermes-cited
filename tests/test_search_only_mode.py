"""H19 and H20: the search mode registers exactly one tool, writes nothing and never reads the MCP token.

Every case uses an explicit profile scope over a temporary home and the fake chassis of step 1.2; the
personal installation and the ports 3240/3241 are out of reach through the guard of task 1.1.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import bridge_support as support
from hermes_cited import config, plugin, tools

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "openspec" / "changes" / "search-only-bridge" / "fixtures" / "search-wire-v1.json"
MCP_TOKEN = "mcp-token-5e1c0a"  # synthetic


@pytest.mark.parametrize("value", [None, "", "full"])
def test_absent_empty_and_full_register_the_full_surface(value, tmp_path):
    values = {"CITED_URL": "http://127.0.0.1:60123", "CITED_MCP_TOKEN": MCP_TOKEN}
    if value is not None:
        values["CITED_BRIDGE_TOOLS"] = value
    with support.bound_scope(values, home=tmp_path):
        context = support.FakeContext()
        plugin.register(context)
    assert set(context.tools) == {"cited_search", "cited_ask", "cited_quote"}
    assert set(context.hooks) == {"pre_llm_call", "post_tool_call", "transform_llm_output"}
    assert set(context.commands) == {"cited", "dot"}
    assert set(context.skills) == {"cited"}


def test_search_registers_exactly_one_tool_and_nothing_else(chassis, tmp_path):
    values = support.search_values(chassis.url, chassis.token)
    with support.bound_scope(values, home=tmp_path):
        context = support.FakeContext()
        plugin.register(context)
    assert set(context.tools) == {"cited_search"}
    assert context.tools["cited_search"]["toolset"] == tools.TOOLSET
    assert context.tools["cited_search"]["description"] == tools.SEARCH_ONLY_DESCRIPTION
    assert context.hooks == {}
    assert context.commands == {}
    assert context.skills == {}


@pytest.mark.parametrize("value", ["bridge", " FULL "])
def test_an_unknown_mode_registers_nothing_with_a_redacted_error(tmp_path, capsys, value):
    values = {
        "CITED_BRIDGE_TOOLS": value,
        "CITED_URL": "http://127.0.0.1:60123",
        "CITED_MCP_TOKEN": MCP_TOKEN,
        "CITED_SEARCH_TOKEN": "search-token-9ab34f",
    }
    with support.bound_scope(values, home=tmp_path):
        context = support.FakeContext()
        plugin.register(context)
    captured = capsys.readouterr()
    assert context.tools == {}
    assert context.hooks == {}
    assert context.commands == {}
    assert context.skills == {}
    assert config.BRIDGE_TOOLS_ENV in captured.err
    assert MCP_TOKEN not in captured.err
    assert "search-token-9ab34f" not in captured.err


def test_the_registered_search_handler_returns_the_model_envelope(chassis, tmp_path):
    values = support.search_values(chassis.url, chassis.token)
    with support.bound_scope(values, home=tmp_path):
        context = support.FakeContext()
        plugin.register(context)
        raw = context.tools["cited_search"]["handler"]({"query": "hours", "limit": 3})
    request = chassis.fake.last_call()
    assert request["path"] == "/api/chassis/mcp"
    assert request["headers"]["authorization"] == "Bearer {0}".format(chassis.token)
    assert request["headers"]["content-type"].startswith("application/json")
    assert request["body"]["jsonrpc"] == "2.0"
    assert request["body"]["id"] == 1
    assert request["body"]["method"] == "tools/call"
    assert request["body"]["params"] == {"name": "cited_search", "arguments": {"query": "hours", "limit": 3}}

    envelope = json.loads(raw)
    assert "jsonrpc" not in envelope
    assert envelope["cited_tool"] == "cited_search"
    assert envelope["query"] == "hours"
    assert set(envelope) == {"cited_tool", "query", "text", "passages"}
    first = envelope["passages"][0]
    assert set(first) == {"n", "document", "heading", "position", "excerpt", "lines"}
    assert "pid" not in first
    assert first["lines"][0] == {"line": 1, "text": "Open Monday to Friday."}


def test_the_search_handler_and_its_registration_never_read_the_mcp_token(chassis, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    values = support.SpyMapping(
        support.search_values(chassis.url, chassis.token, CITED_MCP_TOKEN=MCP_TOKEN)
    )
    with support.bound_scope(values, home=home):
        context = support.FakeContext()
        plugin.register(context)
        context.tools["cited_search"]["handler"]({"query": "hours"})
        context.tools["cited_search"]["handler"]({"query": ""})
    assert values.violations == []
    assert "CITED_MCP_TOKEN" not in values.accessed


def test_search_writes_nothing_under_the_home_on_success_and_on_error(chassis, tmp_path, monkeypatch):
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    home = tmp_path / "hermes-home"
    home.mkdir()
    (home / "config.yaml").write_text("streaming:\n  enabled: false\n", encoding="utf-8")
    before = support.inventory(home)
    assert before  # the home is not empty, so an empty inventory cannot pass by accident

    values = support.search_values(chassis.url, chassis.token)
    with support.bound_scope(values, home=home):
        context = support.FakeContext()
        plugin.register(context)
        context.tools["cited_search"]["handler"]({"query": "hours"})
        context.tools["cited_search"]["handler"]({"query": ""})
    after = support.inventory(home)
    assert after == before
    assert not (home / "cited").exists()


def test_the_search_schema_is_the_wire_arguments_schema():
    schema = json.loads(
        (REPO / "openspec" / "changes" / "search-only-bridge" / "fixtures" / "search-wire-v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert tools.SEARCH_WIRE_SCHEMA == schema["$defs"]["arguments"]


def test_search_handler_wire_matches_the_fixture(chassis, tmp_path, monkeypatch):
    """Step 5.2: the registered handler's actual wire is the delivered fixture, and it writes nothing."""
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    expected = fixture["response"]["result"]["structuredContent"]["passages"][0]
    chassis.fake.passages = [dict(expected)]
    home = tmp_path / "hermes-home"
    home.mkdir()
    (home / "config.yaml").write_text("streaming:\n  enabled: false\n", encoding="utf-8")
    before = support.inventory(home)

    values = support.search_values(chassis.url, chassis.token)
    with support.bound_scope(values, home=home):
        context = support.FakeContext()
        plugin.register(context)
        arguments = dict(fixture["request"]["params"]["arguments"])
        raw = context.tools["cited_search"]["handler"](arguments)

    request = chassis.fake.last_call()
    assert request["body"] == fixture["request"]
    envelope = json.loads(raw)
    first = envelope["passages"][0]
    for key in ("n", "document", "heading", "position", "excerpt"):
        assert first[key] == expected[key]
    assert first["lines"] == [{"line": 1, "text": expected["excerpt"]}]
    assert envelope["text"] == fixture["response"]["result"]["content"][0]["text"]
    assert support.inventory(home) == before
    print("WIRE REQUEST:", json.dumps(request["body"], ensure_ascii=False, sort_keys=True))
    print("MODEL ENVELOPE:", raw)
