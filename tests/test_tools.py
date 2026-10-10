"""The two native tools: schemas, envelopes, clear unconfigured errors and no token leak (H2, H6)."""

from __future__ import annotations

import json

import pytest

from hermes_cited import tools


def test_the_schemas_use_the_cited_parameter_names():
    search = tools.SEARCH_SCHEMA
    ask = tools.ASK_SCHEMA
    assert search["properties"]["query"]["type"] == "string"
    assert search["required"] == ["query"]
    assert search["properties"]["limit"]["minimum"] == 1
    assert search["properties"]["limit"]["maximum"] == 8
    assert ask["properties"]["question"]["type"] == "string"
    assert ask["properties"]["sessionId"]["type"] == "string"
    assert ask["required"] == ["question"]


def test_the_toolset_and_the_tool_names():
    assert tools.TOOLSET == "cited"
    assert tools.TOOL_NAMES == ("cited_search", "cited_ask")


def test_search_returns_the_passages_with_their_excerpt(cited_env):
    raw = tools.search({"query": "precio"})
    envelope = json.loads(raw)
    assert envelope["cited_tool"] == "cited_search"
    assert "Cited found 2 passage(s)" in envelope["text"]
    assert envelope["passages"][0]["n"] == 1
    assert envelope["passages"][0]["excerpt"].startswith("Precios")
    assert envelope["passages"][0]["document"] == "cafe-la-horquilla.md"


def test_ask_returns_the_answer_and_its_citations(cited_env):
    raw = tools.ask({"question": "precio"})
    envelope = json.loads(raw)
    assert envelope["cited_tool"] == "cited_ask"
    assert envelope["status"] == "answered"
    assert "380 pesos" in envelope["answer"]
    assert envelope["citations"][0]["excerpt"] == "Afinacion de bicicleta: 380 pesos."
    assert "Sources:" in envelope["text"]


def test_the_token_never_appears_in_a_result(cited_env):
    assert cited_env.token not in tools.search({"query": "precio"})
    assert cited_env.token not in tools.ask({"question": "precio"})


def test_search_without_configuration_names_the_variable(monkeypatch):
    monkeypatch.delenv("CITED_URL", raising=False)
    monkeypatch.delenv("CITED_MCP_TOKEN", raising=False)
    raw = tools.search({"query": "precio"})
    assert "CITED_URL" in raw
    assert not raw.lstrip().startswith("{")


def test_ask_without_a_token_names_the_variable(monkeypatch):
    monkeypatch.setenv("CITED_URL", "http://127.0.0.1:9")
    monkeypatch.delenv("CITED_MCP_TOKEN", raising=False)
    raw = tools.ask({"question": "precio"})
    assert "CITED_MCP_TOKEN" in raw


def test_a_refused_search_is_a_sentence_not_an_exception(cited_env):
    cited_env.behavior = "401"
    raw = tools.search({"query": "precio"})
    assert "token" in raw.lower()
    assert cited_env.token not in raw


def test_an_empty_query_is_refused(cited_env):
    raw = tools.search({"query": "   "})
    assert "query" in raw.lower()
    assert not raw.lstrip().startswith("{")


def test_a_limit_out_of_range_is_refused(cited_env):
    assert "limit" in tools.search({"query": "precio", "limit": 99}).lower()
    assert "limit" in tools.search({"query": "precio", "limit": 0}).lower()


def test_ask_passes_the_session_id(cited_env):
    tools.ask({"question": "precio", "sessionId": "abc"})
    arguments = cited_env.last_call("cited_ask")["body"]["params"]["arguments"]
    assert arguments == {"question": "precio", "sessionId": "abc"}


def test_parse_tool_result_recovers_the_envelope(cited_env):
    raw = tools.search({"query": "precio"})
    parsed = tools.parse_tool_result(raw)
    assert parsed is not None
    assert parsed["passages"]


def test_parse_tool_result_ignores_a_plain_error_sentence():
    assert tools.parse_tool_result("Cited is not configured: set CITED_URL.") is None
    assert tools.parse_tool_result("") is None
    assert tools.parse_tool_result("not json at all") is None


def test_grounding_texts_include_the_text_documents_and_excerpts(cited_env):
    envelope = tools.parse_tool_result(tools.search({"query": "precio"}))
    grounding = tools.grounding_texts(envelope)
    joined = "\n".join(grounding)
    assert "Cited found 2 passage(s)" in joined
    assert "bike-workshop-policies.md" in joined
    assert "guarantee of 90 days" in joined


def test_source_labels_name_the_document_and_the_section(cited_env):
    envelope = tools.parse_tool_result(tools.ask({"question": "precio"}))
    labels = tools.source_labels(envelope)
    assert labels == ["cafe-la-horquilla.md - Precios"]


@pytest.mark.parametrize("name", ["cited_search", "cited_ask"])
def test_the_handler_never_raises(cited_env, monkeypatch, name):
    cited_env.behavior = "404"
    handler = getattr(tools, "search" if name == "cited_search" else "ask")
    argument = {"query": "x"} if name == "cited_search" else {"question": "x"}
    assert isinstance(handler(argument), str)
