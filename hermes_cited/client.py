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

from .config import CitedError, Settings, endpoint_of, token_of

MCP_PROTOCOL_VERSION = "2025-06-18"
JSON_RPC_VERSION = "2.0"


@dataclass(frozen=True)
class CitedResult:
    text: str
    structured: dict


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
        response = urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.HTTPError as error:
        status = error.code
        body = _read_body(error)
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
