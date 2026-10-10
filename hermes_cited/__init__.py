"""Cited as a native Hermes Agent plugin.

The package holds the JSON-RPC client of Cited's ``POST /api/mcp`` endpoint, the two native
tools, the two conversation modes, the deterministic cited-mode verifier and the hash-chained
audit log. ``hermes_cited.plugin.register`` is what Hermes calls.
"""

__all__ = ["audit", "client", "config", "modes", "plugin", "tools", "verifier", "verify_log"]

__version__ = "0.1.0"
