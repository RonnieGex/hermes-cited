"""Fake of the search-only chassis surface, wire v1 (task 1.2 of search-only-bridge).

It implements exactly the closed subset of ``wire-contract.md``: ``POST /api/chassis/mcp``,
``Content-Type: application/json``, bearer ``CITED_SEARCH_TOKEN``, the ``tools/list`` envelope and the
``tools/call`` request/response of ``$defs.request/response``, plus every documented error, both redirect
classes and the reflection of the bearer. No real provider, no real installation and no personal port is
involved: the server binds a guarded free loopback port and refuses 3240/3241 through ``tests/search_guard``.

As a script (the curl checks of step 5.1):

    python tests/fakes/chassis_surface.py --port <free-port> --record <temporary-log>
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import search_guard  # noqa: E402  (the guard lives in tests/)

#: A synthetic bearer. It is not a secret of any installation and it is redacted in every recorded row.
SEARCH_TOKEN = "cited-search-token-3b7e11c9"
DEFAULT_LIMIT = 5
MIN_LIMIT = 1
MAX_LIMIT = 8
MAX_QUERY = 1000
MAX_BODY = 16 * 1024
PATH = "/api/chassis/mcp"

PASSAGES = [
    {
        "n": 1,
        "document": "sample.md",
        "heading": "Hours",
        "position": 0,
        "excerpt": "Open Monday to Friday.",
    },
    {
        "n": 2,
        "document": "sample.md",
        "heading": None,
        "position": 1,
        "excerpt": "The workshop closes at 18:00.",
    },
    {
        "n": 3,
        "document": "bike-workshop-policies.md",
        "heading": "Guarantee",
        "position": 3,
        "excerpt": "Every repair carries a guarantee of 90 days.",
    },
]

BEHAVIORS = (
    "ok",
    "401",
    "403",
    "404",
    "405",
    "413",
    "badjson",
    "badid",
    "badpassage",
    "jsonrpc_error",
    "isError",
    "reflect",
    "redirect_same",
    "redirect_other",
)


def search_text(passages) -> str:
    """The wire v1 composition of one content block: ``[n] document``, heading and excerpt."""
    blocks = []
    for passage in passages:
        head = "[{0}] {1}".format(passage["n"], passage["document"])
        heading = passage.get("heading")
        if heading is not None:
            head = "{0}\n{1}".format(head, heading)
        blocks.append("{0}\n{1}".format(head, passage["excerpt"]))
    return "\n\n".join(blocks)


class ChassisFake:
    """One configurable chassis: behaviour, canned passages, a request log and an optional record file."""

    def __init__(self, token=SEARCH_TOKEN, behavior="ok", log_path=None):
        self.token = token
        self.behavior = behavior
        self.delay_seconds = 0.0
        self.redirect_status = 302
        self.redirect_to = ""
        self.max_requests = 0
        self.passages = [dict(passage) for passage in PASSAGES]
        self.requests = []
        self.url = ""
        self.log_path = Path(log_path) if log_path else None
        self.recorded = []

    def record(self, entry: dict) -> None:
        """Keep the raw request in memory (a test may compare headers) and redact only what is written.

        The ``--record`` file and :attr:`recorded` carry sentinel labels, so no bearer ever reaches a
        report or a commit; :attr:`requests` is the in-memory log the tests compare against.
        """
        self.requests.append(entry)
        if self.log_path is not None:
            redacted = json.loads(json.dumps(entry).replace(self.token, "<search-token>"))
            self.recorded.append(redacted)
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(redacted, ensure_ascii=False) + "\n")

    def last_call(self):
        for request in reversed(self.requests):
            if (request.get("body") or {}).get("method") == "tools/call":
                return request
        return None


def _make_handler(fake: ChassisFake):
    class Handler(BaseHTTPRequestHandler):
        server_version = "FakeChassis/1.0"
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            return

        def _send(self, status, raw, content_type="application/json"):
            body = raw if isinstance(raw, bytes) else raw.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status, payload):
            self._send(status, json.dumps(payload))

        def _error(self, status, code, message, request_id=None):
            self._json(status, {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}})

        def do_GET(self):
            self._send(405, b"")

        def do_PUT(self):
            self._send(405, b"")

        def do_POST(self):
            if self.path != PATH:
                self._send(404, b"")
                return
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            try:
                message = json.loads(raw.decode("utf-8"))
            except ValueError:
                message = None
            headers = {key.lower(): value for key, value in self.headers.items()}
            entry = {
                "method": "POST",
                "path": self.path,
                "headers": headers,
                "body": message if isinstance(message, dict) else None,
                "raw": raw.decode("utf-8", "replace"),
            }
            fake.record(entry)

            if fake.delay_seconds:
                time.sleep(fake.delay_seconds)

            behavior = fake.behavior
            if behavior in {"redirect_same", "redirect_other"}:
                self.send_response(int(fake.redirect_status))
                self.send_header("Location", fake.redirect_to or fake.url)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if behavior == "413" or length > MAX_BODY:
                self._json(413, {"code": "body_too_large"})
                return

            authorization = headers.get("authorization") or ""
            expected = "Bearer {0}".format(fake.token)
            if authorization != expected:
                self._json(401, {"code": "unauthorized"})
                return

            if behavior in {"401", "403", "404", "405"}:
                self._send(int(behavior), b"")
                return

            if message is None:
                self._error(400, -32700, "Parse error")
                return
            if not isinstance(message, dict):
                self._error(400, -32600, "Invalid Request")
                return

            request_id = message.get("id")
            if not _valid_id(request_id):
                self._error(400, -32600, "Invalid Request")
                return
            if message.get("jsonrpc") != "2.0":
                self._error(400, -32600, "Invalid Request", request_id)
                return
            if behavior == "badjson":
                self._send(200, b"this is not json")
                return
            if behavior == "badid":
                self._json(200, {"jsonrpc": "2.0", "id": 999, "result": {"content": [], "structuredContent": {"passages": []}}})
                return
            if behavior == "badpassage":
                self._json(
                    200,
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "content": [{"type": "text", "text": "malformed"}],
                            "structuredContent": {"passages": [{"n": 1, "document": "sample.md"}]},
                        },
                    },
                )
                return
            if behavior == "jsonrpc_error":
                self._error(200, -32601, "Method not found", request_id)
                return

            method = message.get("method")
            params = message.get("params")
            if method == "tools/list":
                if params != {}:
                    self._error(200, -32602, "Invalid params", request_id)
                    return
                self._json(
                    200,
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "tools": [
                                {
                                    "name": "cited_search",
                                    "description": "Search unsealed document passages.",
                                    "inputSchema": {
                                        "type": "object",
                                        "properties": {
                                            "query": {"type": "string", "minLength": 1, "maxLength": MAX_QUERY, "pattern": "\\S"},
                                            "limit": {"type": "integer", "minimum": MIN_LIMIT, "maximum": MAX_LIMIT, "default": DEFAULT_LIMIT},
                                        },
                                        "required": ["query"],
                                        "additionalProperties": False,
                                    },
                                }
                            ]
                        },
                    },
                )
                return
            if method != "tools/call":
                self._error(200, -32601, "Method not found", request_id)
                return

            if not isinstance(params, dict) or params.get("name") != "cited_search":
                self._error(200, -32601, "Unknown tool", request_id)
                return
            arguments = params.get("arguments")
            error = _invalid_arguments(arguments)
            if error is not None:
                self._error(200, -32602, error, request_id)
                return
            limit = arguments.get("limit", DEFAULT_LIMIT)
            passages = [dict(passage) for passage in fake.passages[: int(limit)]]
            for index, passage in enumerate(passages, start=1):
                passage["n"] = index
            text = search_text(passages)
            if behavior == "reflect":
                text = "{0} {1}".format(text, fake.token)
            if behavior == "isError":
                self._json(
                    200,
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {"isError": True, "content": [{"type": "text", "text": "Cited refused the call."}]},
                    },
                )
                return
            self._json(
                200,
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [{"type": "text", "text": text}],
                        "structuredContent": {"passages": passages},
                    },
                },
            )

    return Handler


def _valid_id(value) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return 0 <= value <= 9007199254740991
    if isinstance(value, str):
        return 1 <= len(value) <= 128
    return False


def _invalid_arguments(arguments):
    if not isinstance(arguments, dict):
        return "Invalid params"
    if set(arguments) - {"query", "limit"}:
        return "Invalid params"
    query = arguments.get("query")
    if not isinstance(query, str) or not 1 <= len(query) <= MAX_QUERY or not any(char.strip() for char in query):
        return "Invalid params"
    if "limit" in arguments:
        limit = arguments["limit"]
        if isinstance(limit, bool) or not isinstance(limit, int) or not MIN_LIMIT <= limit <= MAX_LIMIT:
            return "Invalid params"
    return None


class RunningChassis:
    """A started fake, so a test can stop exactly the server it owns."""

    def __init__(self, fake: ChassisFake, server: ThreadingHTTPServer, thread: threading.Thread):
        self.fake = fake
        self.server = server
        self.thread = thread
        self.url = "http://127.0.0.1:{0}".format(server.server_address[1])

    @property
    def port(self) -> int:
        return int(self.server.server_address[1])

    @property
    def token(self) -> str:
        return self.fake.token

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def start_chassis(port=0, token=SEARCH_TOKEN, behavior="ok", log_path=None) -> RunningChassis:
    """Start one fake on a guarded free loopback port and return it."""
    if port:
        search_guard.guard_target("127.0.0.1", port)
    fake = ChassisFake(token=token, behavior=behavior, log_path=log_path)
    server = ThreadingHTTPServer(("127.0.0.1", port), _make_handler(fake))
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    running = RunningChassis(fake, server, thread)
    fake.url = running.url
    return running


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Fake of the Cited search-only chassis surface (wire v1).")
    parser.add_argument("--port", type=int, default=0, help="loopback port; 0 picks a free one")
    parser.add_argument("--record", default="", help="append every redacted request as one JSON line")
    parser.add_argument("--token", default=SEARCH_TOKEN, help="synthetic bearer expected by the fake")
    parser.add_argument("--behavior", default="ok", choices=BEHAVIORS)
    parser.add_argument("--requests", type=int, default=0, help="stop after N requests (0 = until killed)")
    parser.add_argument("--redirect-status", type=int, default=302)
    parser.add_argument("--redirect-to", default="")
    args = parser.parse_args(argv)

    running = start_chassis(port=args.port, token=args.token, behavior=args.behavior, log_path=args.record or None)
    running.fake.redirect_status = args.redirect_status
    running.fake.redirect_to = args.redirect_to
    print("chassis fake on {0} (path {1})".format(running.url, PATH), flush=True)
    try:
        while True:
            time.sleep(0.1)
            if args.requests and len(running.fake.requests) >= args.requests:
                break
    except KeyboardInterrupt:
        pass
    finally:
        running.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
