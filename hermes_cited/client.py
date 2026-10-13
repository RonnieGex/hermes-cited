"""The JSON-RPC client of Cited's ``POST <CITED_URL>/api/mcp``.

The plugin speaks the endpoint directly instead of going through Hermes's MCP client, so that
installation is one step and so that the verifier and the audit log can see every result. The
transport, the headers and the failure sentences mirror the ones the endpoint documents.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from .config import (
    DEFAULT_SEARCH_LIMIT,
    MAX_SEARCH_LIMIT,
    CitedError,
    Settings,
    chassis_endpoint_of,
    endpoint_of,
    token_of,
    token_of_search,
)

MCP_PROTOCOL_VERSION = "2025-06-18"
JSON_RPC_VERSION = "2.0"
MAX_SEARCH_BODY = 16 * 1024


@dataclass(frozen=True)
class CitedResult:
    text: str
    structured: dict


@dataclass(frozen=True)
class SearchResult:
    """One validated answer of the wire v1 chassis surface: its text block and its passages."""

    text: str
    passages: list


def redact(text: str, secret: str = "") -> str:
    value = str(text)
    if secret:
        value = value.replace(secret, "<token>")
    return value


def _fail(message: str, token: str) -> "CitedError":
    return CitedError(redact(message, token))


def _origin_of(endpoint: str) -> str:
    from urllib.parse import urlsplit

    parts = urlsplit(endpoint)
    return "{0}://{1}".format(parts.scheme, parts.netloc)


def _read_body(stream) -> str:
    try:
        return stream.read().decode("utf-8", "replace")
    except Exception:
        return ""


class _RefuseRedirects(urllib.request.HTTPRedirectHandler):
    """Every request here is authenticated, so no redirect is ever followed (H6).

    Returning ``None`` makes the opener raise the 3xx as an ``HTTPError`` instead of issuing a
    second request to whatever origin the ``Location`` header names.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _opener() -> urllib.request.OpenerDirector:
    """A private opener. The global opener is never installed, so no other client changes."""
    return urllib.request.build_opener(_RefuseRedirects)


def _open(request, timeout):
    return _opener().open(request, timeout=timeout)


def _string_values(value):
    """Every string inside a parsed JSON value, for the reflection check of the token (M2)."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _string_values(key)
            yield from _string_values(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _string_values(item)


def reflects_secret(value, secret: str) -> bool:
    if not secret:
        return False
    return any(secret in text for text in _string_values(value))


def call_tool_full(name: str, arguments: dict, settings: Settings) -> CitedResult:
    """Call one Cited tool and return the text and the structured content Cited answered with."""
    endpoint = endpoint_of(settings.url)
    token = token_of(settings.token)
    request_id = 1
    payload = {
        "jsonrpc": JSON_RPC_VERSION,
        "id": request_id,
        "method": "tools/call",
        "params": {"name": name, "arguments": dict(arguments or {})},
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": "Bearer {0}".format(token),
            "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
        },
    )
    timeout = max(int(settings.timeout_ms or 0), 1) / 1000.0

    try:
        response = _open(request, timeout)
    except urllib.error.HTTPError as error:
        status = error.code
        body = _read_body(error)
        if 300 <= status < 400:
            raise _fail(
                "Cited answered a redirect ({0}) at {1}. This client refuses to follow it, so the "
                "bearer is never sent to another origin. Point CITED_URL at the final address.".format(
                    status, endpoint
                ),
                token,
            )
        if status == 401:
            raise _fail(
                "Cited rejected the bearer (401). Check that CITED_MCP_TOKEN is the token of that "
                "installation.",
                token,
            )
        if status == 403:
            raise _fail(
                "Cited refused the request (403) at {0}: that installation answers only its own host.".format(
                    _origin_of(endpoint)
                ),
                token,
            )
        if status == 404:
            raise _fail(
                "Cited answered 404 at {0}: the address points at a server whose MCP endpoint is off. "
                "Set CITED_MCP_TOKEN on that installation, or fix CITED_URL.".format(endpoint),
                token,
            )
        if status == 405:
            raise _fail(
                "Cited answered 405 at {0}: the MCP endpoint accepts POST only.".format(endpoint),
                token,
            )
        raise _fail(_json_rpc_sentence(body, status), token)
    except CitedError:
        raise
    except TimeoutError as error:
        raise _fail("Cited did not answer within {0} ms: {1}".format(settings.timeout_ms, error), token)
    except urllib.error.URLError as error:
        reason = getattr(error, "reason", error)
        if isinstance(reason, TimeoutError):
            raise _fail("Cited did not answer within {0} ms.".format(settings.timeout_ms), token)
        raise _fail(
            "Cited could not be reached at {0}: {1}".format(_origin_of(endpoint), reason),
            token,
        )
    except OSError as error:
        raise _fail("Cited could not be reached at {0}: {1}".format(_origin_of(endpoint), error), token)

    try:
        with response:
            body = _read_body(response)
            status = getattr(response, "status", 200)
    except Exception as error:
        raise _fail("the answer of Cited at {0} could not be read: {1}".format(_origin_of(endpoint), error), token)

    if status == 202:
        raise _fail("Cited took the message as a notification instead of answering the call.", token)
    if status >= 400:
        raise _fail(_json_rpc_sentence(body, status), token)

    try:
        envelope = json.loads(body)
    except ValueError:
        raise _fail("Cited answered {0} with a body that is not JSON.".format(status), token)
    if not isinstance(envelope, dict):
        raise _fail("Cited answered {0} with a body that is not a JSON-RPC response.".format(status), token)
    if envelope.get("error"):
        error = envelope["error"]
        code = error.get("code") if isinstance(error, dict) else "?"
        message = error.get("message") if isinstance(error, dict) else str(error)
        raise _fail("Cited refused the call with the JSON-RPC error {0}: {1}".format(code, message), token)
    if reflects_secret(envelope, token):
        raise _fail(
            "Cited answered with a body that reflects the bearer token. The answer was discarded "
            "and nothing of it is shown or recorded.",
            token,
        )

    result = envelope.get("result")
    if not isinstance(result, dict):
        raise _fail("Cited answered {0} without a result.".format(status), token)
    text = _text_of(result)
    if result.get("isError") is True:
        raise _fail(text or "Cited refused the call without a message.", token)
    structured = result.get("structuredContent")
    if not isinstance(structured, dict):
        raise _fail("Cited answered without the structured content of the tool.", token)
    return CitedResult(text=text, structured=structured)


def call_tool(name: str, arguments: dict, settings: Settings) -> dict:
    """Call one Cited tool and return its structured content."""
    return call_tool_full(name, arguments, settings).structured


def _text_of(result: dict) -> str:
    content = result.get("content")
    if not isinstance(content, list):
        return ""
    parts = [
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str)
    ]
    return "\n".join(parts).strip()


def _json_rpc_sentence(body: str, status: int) -> str:
    try:
        parsed = json.loads(body)
    except ValueError:
        parsed = None
    if isinstance(parsed, dict) and isinstance(parsed.get("error"), dict):
        message = parsed["error"].get("message")
        if isinstance(message, str) and message:
            return "Cited answered {0}: {1}".format(status, message)
    return "Cited answered {0} without a JSON-RPC error.".format(status)


def search_content_text(passages) -> str:
    """The wire v1 composition of the single content block: ``[n] document``, heading and excerpt."""
    blocks = []
    for passage in passages or []:
        head = "[{0}] {1}".format(passage.get("n"), passage.get("document"))
        heading = passage.get("heading")
        if heading is not None:
            head = "{0}\n{1}".format(head, heading)
        blocks.append("{0}\n{1}".format(head, passage.get("excerpt")))
    return "\n\n".join(blocks)


def call_tool_search(settings, arguments, request_id: int = 1) -> SearchResult:
    """Call the search-only chassis surface with wire v1 and validate both directions (H21).

    The bearer is ``CITED_SEARCH_TOKEN`` and it travels only to ``<CITED_URL>/api/chassis/mcp``. Every
    failure is a redacted sentence: no raw body, no exception text, no credential and no header.
    """
    endpoint = chassis_endpoint_of(settings.url)
    token = token_of_search(settings.token)
    payload = {
        "jsonrpc": JSON_RPC_VERSION,
        "id": request_id,
        "method": "tools/call",
        "params": {"name": "cited_search", "arguments": dict(arguments or {})},
    }
    body = json.dumps(payload).encode("utf-8")
    if len(body) > MAX_SEARCH_BODY:
        raise _fail(
            "Cited could not search: the request body exceeds the 16 KiB limit of the chassis surface.",
            token,
        )
    request = urllib.request.Request(
        endpoint,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer {0}".format(token),
        },
    )
    timeout = max(int(settings.timeout_ms or 0), 1) / 1000.0

    try:
        response = _open(request, timeout)
    except urllib.error.HTTPError as error:
        status = error.code
        raw = _read_body(error)
        if 300 <= status < 400:
            raise _fail(
                "Cited answered a redirect ({0}) at {1}. This client refuses to follow it, so the "
                "search bearer is never sent to another destination. Point CITED_URL at the final "
                "origin.".format(status, endpoint),
                token,
            )
        if status == 401:
            raise _fail(
                "Cited rejected the search bearer (401). Check that CITED_SEARCH_TOKEN is the search "
                "token of that installation.",
                token,
            )
        if status == 403:
            raise _fail(
                "Cited refused the search request (403) at {0}: that installation answers only its own "
                "host.".format(_origin_of(endpoint)),
                token,
            )
        if status == 404:
            raise _fail(
                "Cited answered 404 at {0}: the search-only chassis surface is off or CITED_URL points "
                "at another server.".format(endpoint),
                token,
            )
        if status == 405:
            raise _fail(
                "Cited answered 405 at {0}: the chassis surface accepts POST only.".format(endpoint),
                token,
            )
        if status == 413:
            raise _fail(
                "Cited refused the search request (413): the body exceeds the limit of the chassis "
                "surface.",
                token,
            )
        raise _fail(_json_rpc_sentence(raw, status), token)
    except CitedError:
        raise
    except TimeoutError as error:
        raise _fail("Cited did not answer within {0} ms: {1}".format(settings.timeout_ms, error), token)
    except urllib.error.URLError as error:
        reason = getattr(error, "reason", error)
        if isinstance(reason, TimeoutError):
            raise _fail("Cited did not answer within {0} ms.".format(settings.timeout_ms), token)
        raise _fail(
            "Cited could not be reached at {0}: {1}".format(_origin_of(endpoint), reason),
            token,
        )
    except OSError as error:
        raise _fail("Cited could not be reached at {0}: {1}".format(_origin_of(endpoint), error), token)

    try:
        with response:
            raw = _read_body(response)
            status = getattr(response, "status", 200)
    except Exception as error:
        raise _fail("the answer of Cited at {0} could not be read: {1}".format(_origin_of(endpoint), error), token)

    if status >= 400:
        raise _fail(_json_rpc_sentence(raw, status), token)
    try:
        envelope = json.loads(raw)
    except ValueError:
        raise _fail("Cited answered {0} with a body that is not JSON.".format(status), token)
    if not isinstance(envelope, dict):
        raise _fail("Cited answered {0} with a body that is not a JSON-RPC response.".format(status), token)
    if envelope.get("jsonrpc") != JSON_RPC_VERSION:
        raise _fail("Cited answered without the JSON-RPC 2.0 version.", token)
    if isinstance(envelope.get("id"), bool) or envelope.get("id") != request_id:
        raise _fail("Cited answered with a response id that does not match the request id.", token)
    if envelope.get("error") is not None:
        error = envelope["error"]
        code = error.get("code") if isinstance(error, dict) else "?"
        message = error.get("message") if isinstance(error, dict) else str(error)
        raise _fail("Cited refused the search with the JSON-RPC error {0}: {1}".format(code, message), token)
    if reflects_secret(envelope, token):
        raise _fail(
            "Cited answered with a body that reflects the search bearer. The answer was discarded and "
            "nothing of it is shown.",
            token,
        )
    result = envelope.get("result")
    if not isinstance(result, dict):
        raise _fail("Cited answered without a result.", token)
    if result.get("isError") is True:
        raise _fail("Cited refused the search call.", token)
    return _validated_search_result(result, token, arguments)


def _validated_search_result(result: dict, token: str, arguments) -> SearchResult:
    """Reject anything that is not exactly ``$defs.result`` of wire v1 before a passage is exposed."""
    if set(result) != {"content", "structuredContent"}:
        raise _fail("Cited answered the search with a result that is not the wire v1 result.", token)
    content = result["content"]
    if not isinstance(content, list) or len(content) != 1:
        raise _fail("Cited answered the search without exactly one content block.", token)
    block = content[0]
    if (
        not isinstance(block, dict)
        or set(block) != {"type", "text"}
        or block.get("type") != "text"
        or not isinstance(block.get("text"), str)
    ):
        raise _fail("Cited answered the search with a malformed content block.", token)
    structured = result["structuredContent"]
    if (
        not isinstance(structured, dict)
        or set(structured) != {"passages"}
        or not isinstance(structured.get("passages"), list)
    ):
        raise _fail("Cited answered the search with a malformed structured content.", token)
    limit = (arguments or {}).get("limit")
    bound = limit if isinstance(limit, int) and not isinstance(limit, bool) else DEFAULT_SEARCH_LIMIT
    passages = structured["passages"]
    if len(passages) > bound or len(passages) > MAX_SEARCH_LIMIT:
        raise _fail("Cited answered the search with more passages than the requested limit.", token)
    for index, passage in enumerate(passages, start=1):
        if not isinstance(passage, dict) or set(passage) != {
            "n",
            "document",
            "heading",
            "position",
            "excerpt",
        }:
            raise _fail("Cited answered the search with a malformed passage.", token)
        number = passage["n"]
        if isinstance(number, bool) or not isinstance(number, int) or number != index:
            raise _fail(
                "Cited answered the search with a passage number that is not sequential from 1.",
                token,
            )
        if not isinstance(passage["document"], str) or not passage["document"]:
            raise _fail("Cited answered the search with a passage whose document is not a stored name.", token)
        if passage["heading"] is not None and not isinstance(passage["heading"], str):
            raise _fail(
                "Cited answered the search with a passage whose heading is neither a string nor null.",
                token,
            )
        if isinstance(passage["position"], bool) or not isinstance(passage["position"], int) or passage["position"] < 0:
            raise _fail(
                "Cited answered the search with a passage whose position is not a non-negative integer.",
                token,
            )
        if not isinstance(passage["excerpt"], str):
            raise _fail("Cited answered the search with a passage whose excerpt is not text.", token)
    if search_content_text(passages) != block["text"]:
        raise _fail("Cited answered the search with a content block that does not match its passages.", token)
    return SearchResult(text=block["text"], passages=passages)
