"""Fixtures for the hermes-cited suite: a local fake Cited that imitates POST /api/mcp.

No test in this suite touches the network: the fake is an HTTP server on the loopback
interface, and every fact about the real endpoint was read in its source (reports/hermes-facts.md,
reports/2026-10-09-cited-runbook.md).
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

TOKEN = "cited-test-token-6f2c1a0d"

PASSAGES = [
    {
        "n": 1,
        "document": "cafe-la-horquilla.md",
        "heading": "Precios",
        "position": 2,
        "excerpt": "Precios\n- Espresso: 35 pesos.\n- Cafe de olla: 45 pesos.\n- Afinacion de bicicleta: 380 pesos.",
    },
    {
        "n": 2,
        "document": "bike-workshop-policies.md",
        "heading": "Guarantee",
        "position": 3,
        "excerpt": "Every repair carries a guarantee of 90 days from the day of delivery.",
    },
]

CITATIONS = [
    {
        "n": 1,
        "document": "cafe-la-horquilla.md",
        "heading": "Precios",
        "position": 2,
        "excerpt": "Afinacion de bicicleta: 380 pesos.",
        "lead": 0,
    },
]

ANSWER = "La afinacion de bicicleta cuesta 380 pesos [1]."


def search_text(passages, query):
    lines = [
        "{0}. {1} - {2}\n{3}".format(
            passage["n"], passage["document"], passage.get("heading") or "", passage["excerpt"]
        )
        for passage in passages
    ]
    return 'Cited found {0} passage(s) for "{1}". Cite each one by its number, like [1].\n\n{2}'.format(
        len(passages), query, "\n".join(lines)
    )


def ask_text(answer, citations):
    lines = [
        "{0}. {1} - {2} (position {3})\n{4}".format(
            citation["n"], citation["document"], citation.get("heading") or "", citation["position"], citation["excerpt"]
        )
        for citation in citations
    ]
    return "{0}\n\nSources:\n{1}".format(answer, "\n".join(lines))


class FakeCited:
    """One configurable Cited endpoint: behaviour, canned payloads and a request log."""

    def __init__(self):
        self.token = TOKEN
        self.behavior = "ok"
        self.delay_seconds = 0.0
        self.passages = [dict(passage) for passage in PASSAGES]
        self.citations = [dict(citation) for citation in CITATIONS]
        self.answer = ANSWER
        self.redirect_status = 302
        self.redirect_location = ""
        self.echo_token = False
        self.requests = []
        self.url = ""

    def last_call(self, tool):
        for request in reversed(self.requests):
            body = request.get("body") or {}
            if body.get("method") == "tools/call" and (body.get("params") or {}).get("name") == tool:
                return request
        return None


def _make_handler(fake):
    class Handler(BaseHTTPRequestHandler):
        server_version = "FakeCited/1.0"
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            return

        def _send(self, status, raw, content_type="application/json"):
            body = raw if isinstance(raw, bytes) else raw.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            if status == 401:
                self.send_header("WWW-Authenticate", "Bearer")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status, payload):
            self._send(status, json.dumps(payload))

        def do_GET(self):
            fake.requests.append({"method": "GET", "path": self.path, "headers": dict(self.headers), "body": None})
            self._send(405, b"")

        def do_DELETE(self):
            self._send(405, b"")

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            try:
                body = json.loads(raw.decode("utf-8"))
            except ValueError:
                body = None
            fake.requests.append(
                {
                    "method": "POST",
                    "path": self.path,
                    "headers": {key.lower(): value for key, value in self.headers.items()},
                    "body": body,
                    "raw": raw.decode("utf-8", "replace"),
                }
            )

            if fake.delay_seconds:
                time.sleep(fake.delay_seconds)

            behavior = fake.behavior
            if behavior == "redirect":
                self.send_response(int(fake.redirect_status))
                self.send_header("Location", fake.redirect_location or fake.url)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if behavior in {"401", "403", "404", "405"}:
                self._send(int(behavior), b"")
                return
            if behavior == "badjson":
                self._send(200, b"this is not json")
                return

            message = body if isinstance(body, dict) else {}
            rid = message.get("id")
            method = message.get("method")
            params = message.get("params") if isinstance(message.get("params"), dict) else {}

            if behavior == "jsonrpc_error":
                self._json(200, {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "Method not found"}})
                return
            if behavior == "jsonrpc_error_token":
                self._json(
                    200,
                    {
                        "jsonrpc": "2.0",
                        "id": rid,
                        "error": {"code": -32000, "message": "bad bearer {0}".format(fake.token)},
                    },
                )
                return
            if method == "initialize":
                self._json(
                    200,
                    {
                        "jsonrpc": "2.0",
                        "id": rid,
                        "result": {
                            "protocolVersion": "2025-06-18",
                            "capabilities": {"tools": {}},
                            "serverInfo": {"name": "cited", "version": "test"},
                        },
                    },
                )
                return
            if method == "tools/list":
                self._json(
                    200,
                    {"jsonrpc": "2.0", "id": rid, "result": {"tools": [{"name": "cited_search"}, {"name": "cited_ask"}]}},
                )
                return
            if method != "tools/call":
                self._json(200, {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "not implemented"}})
                return

            name = params.get("name")
            arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
            if behavior == "isError":
                self._json(
                    200,
                    {
                        "jsonrpc": "2.0",
                        "id": rid,
                        "result": {"isError": True, "content": [{"type": "text", "text": "Cited refused the call."}]},
                    },
                )
                return
            if behavior == "nostructured":
                self._json(
                    200,
                    {"jsonrpc": "2.0", "id": rid, "result": {"content": [{"type": "text", "text": "no structure"}]}},
                )
                return
            if name == "cited_search":
                text = search_text(fake.passages, str(arguments.get("query") or ""))
                structured = {"passages": [dict(passage) for passage in fake.passages]}
            else:
                text = ask_text(fake.answer, fake.citations)
                structured = {
                    "status": "answered",
                    "answer": fake.answer,
                    "citations": [dict(citation) for citation in fake.citations],
                }
            if fake.echo_token:
                text = "{0}\n{1}".format(text, fake.token)
                if name == "cited_search":
                    structured["passages"][0]["excerpt"] = "{0} {1}".format(
                        structured["passages"][0]["excerpt"], fake.token
                    )
                else:
                    structured["answer"] = "{0} {1}".format(structured["answer"], fake.token)
            self._json(
                200,
                {
                    "jsonrpc": "2.0",
                    "id": rid,
                    "result": {"content": [{"type": "text", "text": text}], "structuredContent": structured},
                },
            )

    return Handler


@pytest.fixture()
def fake_cited():
    fake = FakeCited()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(fake))
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    fake.url = "http://127.0.0.1:{0}".format(server.server_address[1])
    try:
        yield fake
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture()
def cited_factory():
    """Build as many loopback Cited servers as one test needs, and stop them all."""
    servers = []

    def factory():
        fake = FakeCited()
        server = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(fake))
        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        fake.url = "http://127.0.0.1:{0}".format(server.server_address[1])
        servers.append((server, thread))
        return fake

    try:
        yield factory
    finally:
        for server, thread in servers:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


@pytest.fixture()
def cited_env(fake_cited, monkeypatch):
    monkeypatch.setenv("CITED_URL", fake_cited.url)
    monkeypatch.setenv("CITED_MCP_TOKEN", fake_cited.token)
    monkeypatch.setenv("CITED_TIMEOUT_MS", "5000")
    monkeypatch.delenv("CITED_DEFAULT_MODE", raising=False)
    return fake_cited


@pytest.fixture()
def hermes_home(tmp_path, monkeypatch):
    """A temporary HERMES_HOME. The real one under %LOCALAPPDATA% is never touched."""
    home = tmp_path / "hermes-home"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    return home


@pytest.fixture(autouse=True)
def audit_key_path(tmp_path, monkeypatch):
    """The checkpoint key lives outside HERMES_HOME; a test gives it a temporary home too."""
    path = tmp_path / "audit.key"
    monkeypatch.setenv("CITED_AUDIT_KEY_PATH", str(path))
    return path
