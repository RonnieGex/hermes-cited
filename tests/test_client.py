"""The JSON-RPC client against the fake Cited: transport, headers, errors and redaction (H2, H6)."""

from __future__ import annotations

import pytest

from hermes_cited.client import CitedError, call_tool
from hermes_cited.config import DEFAULT_TIMEOUT_MS, endpoint_of, settings_from_env


def _settings(**overrides):
    from hermes_cited.config import Settings

    values = {"url": "", "token": "", "timeout_ms": 5000, "default_mode": "dot"}
    values.update(overrides)
    return Settings(**values)


def test_settings_come_from_the_environment(cited_env):
    settings = settings_from_env()
    assert settings.url == cited_env.url
    assert settings.token == cited_env.token
    assert settings.timeout_ms == 5000


def test_timeout_defaults_to_thirty_seconds(monkeypatch):
    monkeypatch.delenv("CITED_TIMEOUT_MS", raising=False)
    assert settings_from_env().timeout_ms == DEFAULT_TIMEOUT_MS


@pytest.mark.parametrize(
    "value, expected",
    [
        ("http://host", "http://host/api/mcp"),
        ("http://host/", "http://host/api/mcp"),
        ("http://host/api/mcp", "http://host/api/mcp"),
        ("http://host/api/mcp/", "http://host/api/mcp"),
        ("https://cited.example.com/base", "https://cited.example.com/base/api/mcp"),
    ],
)
def test_endpoint_of_appends_the_mcp_path(value, expected):
    assert endpoint_of(value) == expected


def test_endpoint_of_refuses_a_relative_address():
    with pytest.raises(CitedError):
        endpoint_of("not-a-url")


def test_missing_url_is_a_sentence_that_names_it():
    with pytest.raises(CitedError) as caught:
        call_tool("cited_search", {"query": "x"}, _settings(url="", token="t"))
    assert "CITED_URL" in str(caught.value)


def test_missing_token_is_a_sentence_that_names_it():
    with pytest.raises(CitedError) as caught:
        call_tool("cited_search", {"query": "x"}, _settings(url="http://127.0.0.1:1", token=""))
    assert "CITED_MCP_TOKEN" in str(caught.value)


def test_search_returns_the_passages_with_their_excerpt(fake_cited):
    settings = _settings(url=fake_cited.url, token=fake_cited.token)
    structured = call_tool("cited_search", {"query": "precio"}, settings)
    assert structured["passages"][0]["excerpt"].startswith("Precios")
    assert structured["passages"][1]["document"] == "bike-workshop-policies.md"


def test_ask_returns_the_answer_and_its_citations(fake_cited):
    settings = _settings(url=fake_cited.url, token=fake_cited.token)
    structured = call_tool("cited_ask", {"question": "precio"}, settings)
    assert structured["status"] == "answered"
    assert "380 pesos" in structured["answer"]
    assert structured["citations"][0]["excerpt"] == "Afinacion de bicicleta: 380 pesos."


def test_the_request_carries_the_bearer_and_the_protocol_version(fake_cited):
    settings = _settings(url=fake_cited.url, token=fake_cited.token)
    call_tool("cited_search", {"query": "precio"}, settings)
    request = fake_cited.last_call("cited_search")
    assert request is not None
    assert request["path"] == "/api/mcp"
    assert request["headers"]["authorization"] == "Bearer {0}".format(fake_cited.token)
    assert request["headers"]["mcp-protocol-version"] == "2025-06-18"
    assert request["headers"]["content-type"].startswith("application/json")
    body = request["body"]
    assert body["jsonrpc"] == "2.0"
    assert body["method"] == "tools/call"
    assert body["params"]["name"] == "cited_search"
    assert body["params"]["arguments"] == {"query": "precio"}


def test_only_the_arguments_the_caller_gave_travel(fake_cited):
    settings = _settings(url=fake_cited.url, token=fake_cited.token)
    call_tool("cited_search", {"query": "precio", "limit": 2}, settings)
    assert fake_cited.last_call("cited_search")["body"]["params"]["arguments"] == {"query": "precio", "limit": 2}


@pytest.mark.parametrize(
    "behavior, needle",
    [
        ("401", "token"),
        ("403", "host"),
        ("404", "MCP endpoint"),
        ("405", "POST"),
        ("jsonrpc_error", "-32601"),
        ("isError", "refused"),
        ("nostructured", "structured"),
        ("badjson", "JSON"),
    ],
)
def test_every_failure_becomes_a_sentence(fake_cited, behavior, needle):
    fake_cited.behavior = behavior
    settings = _settings(url=fake_cited.url, token=fake_cited.token)
    with pytest.raises(CitedError) as caught:
        call_tool("cited_search", {"query": "precio"}, settings)
    assert needle.lower() in str(caught.value).lower()


def test_a_401_never_carries_the_token_value(fake_cited):
    fake_cited.behavior = "401"
    settings = _settings(url=fake_cited.url, token=fake_cited.token)
    with pytest.raises(CitedError) as caught:
        call_tool("cited_search", {"query": "precio"}, settings)
    assert fake_cited.token not in str(caught.value)


def test_a_network_failure_is_a_sentence(fake_cited, monkeypatch):
    import urllib.error

    from hermes_cited import client

    def refuse(*args, **kwargs):
        raise urllib.error.URLError(ConnectionRefusedError(10061, "connection refused"))

    monkeypatch.setattr(client, "_open", refuse)
    settings = _settings(url="http://127.0.0.1:9", token="an-unused-token", timeout_ms=1000)
    with pytest.raises(CitedError) as caught:
        call_tool("cited_search", {"query": "precio"}, settings)
    assert "could not be reached" in str(caught.value)


def test_a_timeout_is_a_sentence(fake_cited):
    fake_cited.delay_seconds = 1.5
    settings = _settings(url=fake_cited.url, token=fake_cited.token, timeout_ms=200)
    with pytest.raises(CitedError) as caught:
        call_tool("cited_search", {"query": "precio"}, settings)
    assert "did not answer" in str(caught.value)


def test_the_configured_url_is_the_only_host_that_is_called(fake_cited):
    settings = _settings(url=fake_cited.url, token=fake_cited.token)
    call_tool("cited_search", {"query": "precio"}, settings)
    assert len(fake_cited.requests) == 1
    assert fake_cited.requests[0]["method"] == "POST"


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_a_redirect_never_reaches_another_origin(cited_factory, status):
    """B3: the bearer must never travel to the Location of a 3xx."""
    origin = cited_factory()
    sink = cited_factory()
    origin.behavior = "redirect"
    origin.redirect_status = status
    origin.redirect_location = "{0}/sink".format(sink.url)
    settings = _settings(url=origin.url, token=origin.token)
    with pytest.raises(CitedError) as caught:
        call_tool("cited_search", {"query": "precio"}, settings)
    assert "redirect" in str(caught.value).lower()
    assert origin.token not in str(caught.value)
    assert sink.requests == []
    assert len(origin.requests) == 1


def test_a_redirect_to_the_same_origin_is_also_refused(fake_cited):
    fake_cited.behavior = "redirect"
    fake_cited.redirect_location = "{0}/other".format(fake_cited.url)
    settings = _settings(url=fake_cited.url, token=fake_cited.token)
    with pytest.raises(CitedError):
        call_tool("cited_search", {"query": "precio"}, settings)
    assert len(fake_cited.requests) == 1


def test_the_no_redirect_policy_also_covers_a_https_to_http_downgrade():
    """The handler refuses before any request is issued, whatever the scheme of the Location."""
    import urllib.request

    from hermes_cited.client import _RefuseRedirects

    handler = _RefuseRedirects()
    request = urllib.request.Request("https://cited.example.com/api/mcp", method="POST")
    assert handler.redirect_request(request, None, 302, "Found", {}, "http://cited.example.com/api/mcp") is None
    assert handler.redirect_request(request, None, 302, "Found", {}, "http://evil.example/api/mcp") is None


def test_the_global_opener_is_never_replaced():
    """A private opener keeps other Hermes HTTP clients untouched."""
    import urllib.request

    before = urllib.request._opener
    from hermes_cited import client

    client._opener()
    assert urllib.request._opener is before


def test_a_success_that_reflects_the_token_is_rejected(fake_cited):
    fake_cited.echo_token = True
    settings = _settings(url=fake_cited.url, token=fake_cited.token)
    with pytest.raises(CitedError) as caught:
        call_tool("cited_search", {"query": "precio"}, settings)
    assert "token" in str(caught.value).lower()
    assert fake_cited.token not in str(caught.value)
