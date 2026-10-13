"""Shared helpers of the bridge tests: a spy scope, a fake context and a home inventory.

Kept in its own module so the H19-H22 suites exercise the same seam and the same inventory, exactly as
``tasks.md`` asks: before/after means a sorted inventory and SHA-256 of every regular file of the isolated
``HERMES_HOME``, without excluding any plugin-created file.
"""

from __future__ import annotations

import contextlib
import hashlib
from pathlib import Path


class SpyMapping(dict):
    """An explicit profile scope that records every key read and refuses ``CITED_MCP_TOKEN``.

    Search mode must never request the MCP token, not even to redact or check it (H20). Any membership
    test or read of that key raises here, so the rule is enforced by construction.
    """

    FORBIDDEN = "CITED_MCP_TOKEN"

    def __init__(self, values=None):
        super().__init__(values or {})
        self.accessed = []
        self.violations = []

    def _note(self, key):
        self.accessed.append(key)
        if key == self.FORBIDDEN:
            self.violations.append(key)
            raise AssertionError("the search path requested the key {0}".format(self.FORBIDDEN))
        return key

    def __contains__(self, key):
        self._note(key)
        return dict.__contains__(self, key)

    def get(self, key, default=None):
        self._note(key)
        return dict.get(self, key, default)

    def __getitem__(self, key):
        self._note(key)
        return dict.__getitem__(self, key)


class DictState:
    def __init__(self):
        self.data = {}

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value


class FakeContext:
    """The slice of ``PluginContext`` this plugin uses, with the real registration signatures."""

    def __init__(self):
        self.state = DictState()
        self.tools = {}
        self.hooks = {}
        self.commands = {}
        self.skills = {}

    def register_tool(self, name, toolset, schema, handler, check_fn=None, requires_env=None,
                      is_async=False, description="", emoji="", override=False):
        self.tools[name] = {
            "toolset": toolset,
            "schema": schema,
            "handler": handler,
            "description": description,
            "emoji": emoji,
        }

    def register_hook(self, hook_name, callback):
        self.hooks.setdefault(hook_name, []).append(callback)

    def register_command(self, name, handler, description="", args_hint="", argument_mode=None):
        self.commands[name] = handler

    def register_skill(self, name, path, description="", frontmatter=None):
        self.skills[name] = {"path": path, "description": description, "frontmatter": frontmatter}


def registration(mode="search", home=""):
    from hermes_cited import config

    return config.Registration(mode=mode, home=str(home), explicit=True)


@contextlib.contextmanager
def bound_scope(values, home, getter=None):
    """Bind an explicit profile scope for the duration of one block.

    Before the scope is bound, and therefore before any registration, handler call or write, the
    isolation guard of task 1.1 checks the profile home: a home outside the registered temporary
    workspaces (for example the personal installation) raises ``GuardError`` here instead of being
    exercised by the plugin. An unsafe destination is stopped by the socket guard of the suite.
    """
    from hermes_cited import config

    import search_guard

    text_home = str(home or "").strip()
    if text_home:
        search_guard.guard_path(text_home, kind="profile home")
    token = config.bind_scope(values, home, getter=getter)
    try:
        yield values
    finally:
        config.unbind_scope(token)


def search_values(url, token, **extra):
    values = {"CITED_BRIDGE_TOOLS": "search", "CITED_URL": url, "CITED_SEARCH_TOKEN": token}
    values.update(extra)
    return values


def inventory(root):
    """The sorted ``(relative path, size, sha256)`` of every regular file under *root*."""
    base = Path(root)
    rows = []
    if not base.exists():
        return rows
    for path in sorted(base.rglob("*")):
        if path.is_file():
            relative = str(path.relative_to(base)).replace("\\", "/")
            rows.append((relative, path.stat().st_size, hashlib.sha256(path.read_bytes()).hexdigest()))
    return rows
