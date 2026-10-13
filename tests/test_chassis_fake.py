"""H21 and task 1.2: the delivered fake speaks the closed wire, authentication and envelope included.

The fake is the oracle of every other H21 case, so its own contract is checked here against the wire
sentences: authentication precedes body parsing, the JSON-RPC envelope rejects unknown properties, a
``null`` body is invalid rather than a parse error, an invalid version or id answers a null id, a batch
or a notification is invalid, and the documented status codes are the only ones it returns. Every server
binds a free loopback port guarded by ``tests/search_guard``; no personal service is reachable.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from fakes.chassis_surface import start_chassis

TOKEN = "cited-search-token-3b7e11c9"


def call(running, raw, auth="Bearer {0}".format(TOKEN), content_type="application/json", path=None):
    """One raw request to the fake, returning ``(status, parsed_body_or_None)``."""
    headers = {"Content-Type": content_type}
    if auth is not None:
        headers["Authorization"] = auth
    target = (path or "/api/chassis/mcp")
    request = urllib.request.Request(
        "{0}{1}".format(running.url, target), data=raw, headers=headers, method="POST"
    )
    try:
        reply = urllib.request.urlopen(request, timeout=5)
    except urllib.error.HTTPError as error:
        reply = error
    with reply:
        body = reply.read().decode("utf-8", "replace")
        try:
            payload = json.loads(body)
        except ValueError:
            payload = None
        return reply.status, payload


def envelope(**overrides):
    body = {"jsonrpc": "2.0", "id": 41, "method": "tools/list", "params": {}}
    body.update(overrides)
    return json.dumps(body).encode("utf-8")


def test_authentication_precedes_the_body_even_when_it_is_oversized():
    running = start_chassis()
    try:
        status, payload = call(running, b"x" * 17000, auth="Bearer deliberately-wrong")
    finally:
        running.stop()
    assert (status, payload) == (401, {"code": "unauthorized"})
    assert running.fake.requests[-1]["body"] is None, "the body must not be parsed before authentication"


def test_an_authenticated_oversized_body_is_413():
    running = start_chassis()
    try:
        status, payload = call(running, b"x" * 17000)
    finally:
        running.stop()
    assert (status, payload) == (413, {"code": "body_too_large"})


@pytest.mark.parametrize(
    "raw, label",
    [
        (json.dumps({"jsonrpc": "2.0", "id": 41, "method": "tools/list", "params": {}, "extra": 1}).encode(), "extra property"),
        (b"null", "json null"),
        (b"[]", "batch"),
        (b"{}", "empty object"),
        (json.dumps({"id": 41, "method": "tools/list", "params": {}}).encode(), "missing version"),
        (json.dumps({"jsonrpc": "2.0", "method": "tools/list", "params": {}}).encode(), "notification"),
        (envelope(jsonrpc="1.0"), "wrong version"),
        (json.dumps({"jsonrpc": "2.0", "id": True, "method": "tools/list", "params": {}}).encode(), "boolean id"),
    ],
)
def test_an_invalid_envelope_is_32600_with_a_null_id(raw, label):
    running = start_chassis()
    try:
        status, payload = call(running, raw)
    finally:
        running.stop()
    assert status == 400, label
    assert payload == {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid Request"}}, label


def test_a_parse_error_is_32700_with_a_null_id():
    running = start_chassis()
    try:
        status, payload = call(running, b"{not json")
    finally:
        running.stop()
    assert status == 400
    assert payload == {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}


def test_a_valid_tools_list_is_served():
    running = start_chassis()
    try:
        status, payload = call(running, envelope())
    finally:
        running.stop()
    assert status == 200
    assert payload["id"] == 41
    assert payload["result"]["tools"][0]["name"] == "cited_search"
    assert running.fake.requests[-1]["body"]["method"] == "tools/list"


def test_an_unknown_method_is_32601():
    running = start_chassis()
    try:
        status, payload = call(running, envelope(method="tools/nope"))
    finally:
        running.stop()
    assert status == 200
    assert payload["error"]["code"] == -32601
    assert payload["id"] == 41


def test_an_unknown_tool_is_32601():
    running = start_chassis()
    try:
        status, payload = call(
            running,
            envelope(method="tools/call", params={"name": "cited_ask", "arguments": {"question": "x"}}),
        )
    finally:
        running.stop()
    assert status == 200
    assert payload["error"]["code"] == -32601


def test_invalid_arguments_are_32602():
    running = start_chassis()
    try:
        status, payload = call(
            running,
            envelope(method="tools/call", params={"name": "cited_search", "arguments": {"query": "hours", "limit": 0}}),
        )
    finally:
        running.stop()
    assert status == 200
    assert payload["error"]["code"] == -32602


def test_another_path_is_404_and_another_method_is_405():
    running = start_chassis()
    try:
        status, _payload = call(running, envelope(), path="/api/mcp")
        assert status == 404
        request = urllib.request.Request("{0}/api/chassis/mcp".format(running.url), method="GET")
        try:
            reply = urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError as error:
            reply = error
        with reply:
            assert reply.status == 405
    finally:
        running.stop()
