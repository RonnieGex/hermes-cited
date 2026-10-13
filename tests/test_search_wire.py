"""H21: the versioned wire, the dedicated bearer and the validation of both directions.

Every case drives the real search path (``tools.search_only`` over an explicit profile scope) against the
fake chassis of step 1.2. No case touches a personal installation: the fake binds a free loopback port and
the guard of task 1.1 forbids 3240/3241 for the whole suite.
"""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

import bridge_support as support
from hermes_cited import client, config, tools

REPO = Path(__file__).resolve().parents[1]
from openspec_paths import change_dir
SCHEMA = json.loads(
    (
        change_dir("search-only-bridge") / "fixtures" / "search-wire-v1.schema.json"
    ).read_text(encoding="utf-8")
)


def run(scope_values, home, args, mode="search", registration_home=None):
    base = Path(home)
    base.mkdir(parents=True, exist_ok=True)
    registration = support.registration(mode=mode, home=registration_home if registration_home is not None else base)
    with support.bound_scope(scope_values, home=base):
        return tools.search_only(args, registration)


def wire(chassis, **extra):
    values = support.search_values(chassis.url, chassis.token)
    values.update(extra)
    return values


# --------------------------------------------------------------------------------------------------
# The exact request, response and model envelope
# --------------------------------------------------------------------------------------------------


def test_the_exact_v1_request_travels(chassis, tmp_path):
    run(wire(chassis), tmp_path, {"query": "hours", "limit": 3})
    assert chassis.fake.last_call()["body"] == {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "cited_search", "arguments": {"query": "hours", "limit": 3}},
    }


def test_an_omitted_limit_is_not_transmitted_and_the_surface_means_five(chassis, tmp_path):
    chassis.fake.passages = [
        {"n": index, "document": "doc{0}.md".format(index), "heading": None, "position": index - 1,
         "excerpt": "line {0}".format(index)}
        for index in range(1, 9)
    ]
    answer = run(wire(chassis), tmp_path, {"query": "hours"})
    assert chassis.fake.last_call()["body"]["params"]["arguments"] == {"query": "hours"}
    envelope = json.loads(answer)
    assert len(envelope["passages"]) == 5
    assert [passage["n"] for passage in envelope["passages"]] == [1, 2, 3, 4, 5]


def test_the_model_envelope_is_not_the_rpc_wrapper(chassis, tmp_path):
    answer = run(wire(chassis), tmp_path, {"query": "hours", "limit": 3})
    envelope = json.loads(answer)
    assert set(envelope) == {"cited_tool", "query", "text", "passages"}
    assert isinstance(envelope["text"], str) and envelope["text"]
    for index, passage in enumerate(envelope["passages"], start=1):
        assert set(passage) == {"n", "document", "heading", "position", "excerpt", "lines"}
        assert passage["n"] == index
        assert isinstance(passage["lines"], list)
        assert passage["lines"] and passage["lines"][0]["line"] == 1


def test_the_schema_and_the_handler_agree_without_coercion():
    assert tools.SEARCH_WIRE_SCHEMA == SCHEMA["$defs"]["arguments"]
    assert tools.SEARCH_WIRE_SCHEMA["additionalProperties"] is False
    assert tools.SEARCH_WIRE_SCHEMA["properties"]["limit"]["default"] == 5


# --------------------------------------------------------------------------------------------------
# Boundaries and malformed values
# --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("query", ["", "   ", 5, None, ["hours"], {"q": "hours"}])
def test_an_invalid_query_connects_nothing(chassis, tmp_path, query):
    answer = run(wire(chassis), tmp_path, {"query": query})
    assert isinstance(answer, str) and answer.startswith("Cited")
    assert chassis.fake.requests == []


def test_a_thousand_code_points_connect_and_a_thousand_and_one_do_not(chassis, tmp_path):
    answer = run(wire(chassis), tmp_path, {"query": "a" * 1000})
    assert chassis.fake.last_call() is not None
    assert chassis.fake.last_call()["body"]["params"]["arguments"]["query"] == "a" * 1000
    assert isinstance(json.loads(answer)["text"], str)

    before = len(chassis.fake.requests)
    answer = run(wire(chassis), tmp_path, {"query": "a" * 1001})
    assert answer.startswith("Cited")
    assert len(chassis.fake.requests) == before


@pytest.mark.parametrize("limit", [1, 8])
def test_a_valid_limit_connects(chassis, tmp_path, limit):
    run(wire(chassis), tmp_path, {"query": "hours", "limit": limit})
    assert chassis.fake.last_call()["body"]["params"]["arguments"] == {"query": "hours", "limit": limit}


@pytest.mark.parametrize("limit", [0, 9, True, False, 1.5, "3", -1])
def test_an_invalid_limit_connects_nothing(chassis, tmp_path, limit):
    answer = run(wire(chassis), tmp_path, {"query": "hours", "limit": limit})
    assert answer.startswith("Cited")
    assert chassis.fake.requests == []


def test_an_unknown_argument_connects_nothing(chassis, tmp_path):
    answer = run(wire(chassis), tmp_path, {"query": "hours", "top_k": 3})
    assert answer.startswith("Cited")
    assert chassis.fake.requests == []


# --------------------------------------------------------------------------------------------------
# Missing configuration and unsafe URLs
# --------------------------------------------------------------------------------------------------


def test_a_missing_url_names_the_setting_and_makes_no_request(chassis, tmp_path):
    values = {"CITED_BRIDGE_TOOLS": "search", "CITED_SEARCH_TOKEN": chassis.token}
    answer = run(values, tmp_path, {"query": "hours"})
    assert "CITED_URL" in answer
    assert chassis.fake.requests == []


def test_a_missing_search_token_names_the_setting_and_makes_no_request(chassis, tmp_path):
    answer = run(wire(chassis, CITED_SEARCH_TOKEN=""), tmp_path, {"query": "hours"})
    assert "CITED_SEARCH_TOKEN" in answer
    assert chassis.fake.requests == []


@pytest.mark.parametrize(
    "unsafe",
    [
        "{url}/base",
        "{url}/",
        "{url}?x=1",
        "{url}#f",
        "http://user:secret@127.0.0.1:{port}",
        "ftp://127.0.0.1:{port}",
        "not-a-url",
    ],
)
def test_an_unsafe_url_names_the_setting_and_makes_no_request(chassis, tmp_path, unsafe):
    value = unsafe.format(url=chassis.url, port=chassis.port)
    answer = run(wire(chassis, CITED_URL=value), tmp_path, {"query": "hours"})
    assert "CITED_URL" in answer
    assert chassis.fake.requests == []


@pytest.mark.parametrize("timeout", ["abc", "0", "-5", "120001", "1.5", "30000ms"])
def test_an_invalid_timeout_names_the_setting_and_makes_no_request(chassis, tmp_path, timeout):
    answer = run(wire(chassis, CITED_TIMEOUT_MS=timeout), tmp_path, {"query": "hours"})
    assert "CITED_TIMEOUT_MS" in answer
    assert chassis.fake.requests == []


@pytest.mark.parametrize("timeout", ["30000", "120000"])
def test_a_valid_timeout_connects(chassis, tmp_path, timeout):
    run(wire(chassis, CITED_TIMEOUT_MS=timeout), tmp_path, {"query": "hours"})
    assert chassis.fake.last_call() is not None


def test_the_minimum_timeout_is_valid(chassis, tmp_path):
    """One millisecond is a valid configuration: the request is issued, whatever the surface answers."""
    answer = run(wire(chassis, CITED_TIMEOUT_MS="1"), tmp_path, {"query": "hours"})
    assert "CITED_TIMEOUT_MS" not in answer
    assert len(chassis.fake.requests) == 1


# --------------------------------------------------------------------------------------------------
# Bad responses
# --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "behavior",
    ["badjson", "badid", "badpassage", "jsonrpc_error", "isError", "reflect", "401", "403", "404", "405", "413"],
)
def test_every_bad_response_becomes_a_redacted_sentence(chassis, tmp_path, behavior):
    chassis.fake.behavior = behavior
    answer = run(wire(chassis), tmp_path, {"query": "hours"})
    assert answer.startswith("Cited"), answer
    assert chassis.token not in answer
    assert "Bearer" not in answer
    assert "Traceback" not in answer


def test_invalid_json_is_named_as_json(chassis, tmp_path):
    chassis.fake.behavior = "badjson"
    assert "JSON" in run(wire(chassis), tmp_path, {"query": "hours"})


def test_a_reflected_token_is_discarded(chassis, tmp_path):
    chassis.fake.behavior = "reflect"
    answer = run(wire(chassis), tmp_path, {"query": "hours"})
    assert "token" in answer.lower() or "bearer" in answer.lower()
    assert chassis.token not in answer


def test_a_mismatched_id_is_refused(chassis, tmp_path):
    chassis.fake.behavior = "badid"
    answer = run(wire(chassis), tmp_path, {"query": "hours"})
    assert "id" in answer.lower()


def test_a_malformed_passage_is_refused(chassis, tmp_path):
    chassis.fake.behavior = "badpassage"
    answer = run(wire(chassis), tmp_path, {"query": "hours"})
    assert "passage" in answer.lower()


def test_a_timeout_is_a_sentence_and_only_one_request_is_made(chassis, tmp_path):
    chassis.fake.delay_seconds = 1.0
    answer = run(wire(chassis, CITED_TIMEOUT_MS="200"), tmp_path, {"query": "hours"})
    assert "did not answer" in answer
    assert len(chassis.fake.requests) == 1


def test_a_network_failure_is_a_sentence(monkeypatch, chassis, tmp_path):
    def refuse(*args, **kwargs):
        raise urllib.error.URLError(ConnectionRefusedError(10061, "connection refused"))

    monkeypatch.setattr(client, "_open", refuse)
    answer = run(wire(chassis), tmp_path, {"query": "hours"})
    assert "could not be reached" in answer
    assert chassis.token not in answer


def test_an_unexpected_transport_exception_is_never_exposed(monkeypatch, chassis, tmp_path):
    """M02: an exception outside the known categories is a fixed sentence, never its own text."""

    def explode(*args, **kwargs):
        raise RuntimeError("private transport metadata marker-r2")

    monkeypatch.setattr(client, "_open", explode)
    answer = run(wire(chassis), tmp_path, {"query": "hours"})
    assert "marker-r2" not in answer
    assert "RuntimeError" not in answer
    assert answer.startswith("Cited")


def test_a_timeout_exception_text_is_never_exposed(monkeypatch, chassis, tmp_path):
    def explode(*args, **kwargs):
        raise TimeoutError("private timeout marker-r2")

    monkeypatch.setattr(client, "_open", explode)
    answer = run(wire(chassis), tmp_path, {"query": "hours"})
    assert "marker-r2" not in answer
    assert "did not answer" in answer


def test_a_url_error_reason_is_never_exposed(monkeypatch, chassis, tmp_path):
    def explode(*args, **kwargs):
        raise urllib.error.URLError(RuntimeError("private reason marker-r2"))

    monkeypatch.setattr(client, "_open", explode)
    answer = run(wire(chassis), tmp_path, {"query": "hours"})
    assert "marker-r2" not in answer
    assert "could not be reached" in answer


def test_an_os_error_text_is_never_exposed(monkeypatch, chassis, tmp_path):
    def explode(*args, **kwargs):
        raise OSError("private os marker-r2")

    monkeypatch.setattr(client, "_open", explode)
    answer = run(wire(chassis), tmp_path, {"query": "hours"})
    assert "marker-r2" not in answer
    assert "could not be reached" in answer


def test_a_read_failure_text_is_never_exposed(monkeypatch, chassis, tmp_path):
    class BadResponse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            raise RuntimeError("private read marker-r2")

    monkeypatch.setattr(client, "_open", lambda *args, **kwargs: BadResponse(b"{}"))
    answer = run(wire(chassis), tmp_path, {"query": "hours"})
    assert "marker-r2" not in answer
    assert "could not be read" in answer


# --------------------------------------------------------------------------------------------------
# Redirects
# --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_no_redirect_is_ever_followed(chassis_factory, tmp_path, status):
    origin = chassis_factory()
    sink = chassis_factory()
    origin.fake.behavior = "redirect_other"
    origin.fake.redirect_status = status
    origin.fake.redirect_to = "{0}/api/chassis/mcp".format(sink.url)
    answer = run(wire(origin), tmp_path, {"query": "hours"})
    assert "redirect" in answer.lower()
    assert origin.token not in answer
    assert sink.fake.requests == []
    assert len(origin.fake.requests) == 1


def test_a_redirect_to_the_same_origin_is_refused(chassis, tmp_path):
    chassis.fake.behavior = "redirect_same"
    chassis.fake.redirect_to = "{0}/api/chassis/mcp".format(chassis.url)
    answer = run(wire(chassis), tmp_path, {"query": "hours"})
    assert "redirect" in answer.lower()
    assert len(chassis.fake.requests) == 1


# --------------------------------------------------------------------------------------------------
# The fake itself serves the whole v1 subset, tools/list included
# --------------------------------------------------------------------------------------------------


def test_the_fake_serves_tools_list_with_the_wire_schema(chassis):
    request = urllib.request.Request(
        "{0}/api/chassis/mcp".format(chassis.url),
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "Authorization": "Bearer {0}".format(chassis.token)},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        body = json.loads(response.read().decode("utf-8"))
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == 1
    tool = body["result"]["tools"][0]
    assert tool["name"] == "cited_search"
    assert tool["description"] == "Search unsealed document passages."
    assert tool["inputSchema"] == SCHEMA["$defs"]["listResponse"]["properties"]["result"]["properties"]["tools"]["items"]["properties"]["inputSchema"]["const"]


def test_the_search_endpoint_is_the_chassis_path(tmp_path):
    assert config.chassis_endpoint_of("http://127.0.0.1:60123") == "http://127.0.0.1:60123/api/chassis/mcp"
    assert config.chassis_endpoint_of("https://cited.example.com") == "https://cited.example.com/api/chassis/mcp"
