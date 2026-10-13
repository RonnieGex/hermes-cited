"""Round 4 (D6-D8): the six independent probes of the third review as permanent regressions.

The third review (``tasks/revision-bridge-r3.md``) measured six failures against the pinned host:
two ``full`` registrations with the same session/turn identifiers collided, a refused foreign callback
destroyed the owner's live turn, the home/NUL prefix of the mode state was rejected by the real
``PluginState``, the persisted ``mode.profile`` of the previous version was ignored, and the command and
transformer diagnostics redacted with the root token instead of the profile's. Design D6-D8 fixes them.

These cases are the ported probes: they use the real ``agent.secret_scope`` and the real
``hermes_cli.plugins_state.PluginState`` of the pinned host, never a scope that accepts any key. Every run
uses a temporary ``HERMES_HOME`` and the isolation guard of task 1.1; the module is skipped when the
read-only copy of the pinned host is not present, so the ordinary suite stays runnable.
"""

from __future__ import annotations

import contextlib
import logging
import os
import sys
from pathlib import Path

import pytest

import search_guard
from hermes_cited import config, plugin

REPO = Path(__file__).resolve().parents[1]
HOST_COMMIT = "dce1e9b37581dd62e480a9064dc04a709c2940d3"
REVIEW_ROOT = Path(
    os.environ.get(
        "HERMES_REVIEW_ROOT",
        str(Path(os.environ.get("TEMP", "/tmp")) / "codex-hermes-cited-r2-2d438babc89e4a55af33b15bab5269cd"),
    )
)
HOST_COPY = REVIEW_ROOT / "host-fast" / "hermes-agent-{0}".format(HOST_COMMIT)
HOST_SITE_PACKAGES = REVIEW_ROOT / "host-venv" / "Lib" / "site-packages"

#: Synthetic credentials only: the profile carries one and the root environment a different one, which
#: is exactly the boundary D8 protects. They never reach a report or a commit.
PROFILE_SECRET = "synthetic-profile-cred-r4"
ROOT_SECRET = "synthetic-root-cred-r4"

pytestmark = pytest.mark.skipif(
    not (HOST_COPY / "agent" / "secret_scope.py").exists(),
    reason="the read-only copy of the Hermes host is not present",
)


@pytest.fixture()
def host_paths(monkeypatch):
    """Put the pinned host and its review venv on ``sys.path``, ahead of the checkout."""
    if HOST_SITE_PACKAGES.exists():
        monkeypatch.syspath_prepend(str(HOST_SITE_PACKAGES))
    monkeypatch.syspath_prepend(str(HOST_COPY))
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    monkeypatch.setenv("CITED_MCP_TOKEN", ROOT_SECRET)
    return HOST_COPY


class State:
    def __init__(self):
        self.values = {}

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value


class Context:
    """The slice of ``PluginContext`` the plugin uses, with the real registration signatures."""

    def __init__(self):
        self.state = State()
        self.tools = {}
        self.hooks = {}
        self.commands = {}
        self.skills = {}

    def register_tool(self, name, toolset, schema, handler, **kwargs):
        self.tools[name] = handler

    def register_hook(self, name, callback):
        self.hooks.setdefault(name, []).append(callback)

    def register_command(self, name, handler, **kwargs):
        self.commands[name] = handler

    def register_skill(self, name, path, **kwargs):
        self.skills[name] = path


def full_values(**updates):
    values = {
        "CITED_BRIDGE_TOOLS": "full",
        "CITED_DEFAULT_MODE": "cited",
        "CITED_LANGUAGE": "en",
        "CITED_URL": "http://127.0.0.1:9",
        "CITED_MCP_TOKEN": PROFILE_SECRET,
    }
    values.update(updates)
    return values


@contextlib.contextmanager
def scope(home, **updates):
    """The real ``agent.secret_scope`` of the pinned host, over a guarded temporary profile."""
    from agent import secret_scope

    text = str(home)
    search_guard.guard_path(text, kind="profile home")
    marker = secret_scope.set_secret_scope(full_values(**updates), profile_home=text)
    try:
        yield
    finally:
        secret_scope.reset_secret_scope(marker)


def test_two_full_profiles_can_open_identical_execution_ids(tmp_path, host_paths):
    """D6/H19: two homes with the same session and turn identifiers are two independent turns."""
    for name in ("amber", "violet"):
        with scope(tmp_path / name):
            context = Context()
            plugin.register(context)
            result = context.hooks["pre_llm_call"][0](
                session_id="same-session", turn_id="same-execution", user_message=name
            )
            assert result == {"context": plugin.CITED_RULES}
    assert len(plugin._TURNS) == 2


def test_refused_foreign_callback_does_not_destroy_owners_live_turn(tmp_path, host_paths):
    """D6/H19: a callback under another profile's scope is refused without cleanup."""
    owner = tmp_path / "owner"
    with scope(owner):
        context = Context()
        plugin.register(context)
        context.hooks["pre_llm_call"][0](session_id="pending", turn_id="pending")
    with scope(tmp_path / "visitor", CITED_BRIDGE_TOOLS="search"):
        context.hooks["transform_llm_output"][0](
            session_id="pending", turn_id="pending", response_text="unrelated"
        )
    with scope(owner):
        assert plugin._turn_of("pending", "pending", home=str(owner)) is not None


def test_full_mode_commands_accept_real_host_plugin_state_keys(tmp_path, monkeypatch, host_paths):
    """D7/H22: ``/cited`` persists through the pinned host's real ``PluginState``."""
    from hermes_cli.plugins_state import PluginState

    home = tmp_path / "real-state-owner"
    monkeypatch.setenv("HERMES_HOME", str(home))
    with scope(home, CITED_DEFAULT_MODE="dot"):
        context = Context()
        context.state = PluginState("hermes-cited")
        plugin.register(context)
        response = context.commands["cited"]("")
        assert "could not change the mode" not in response
        subsequent = context.hooks["pre_llm_call"][0](session_id="real-state", turn_id="real-state")
    assert subsequent == {"context": plugin.CITED_RULES}


def test_existing_full_profile_mode_survives_registration_upgrade(tmp_path, monkeypatch, host_paths):
    """D7/H22: a ``mode.profile`` value written by the previous version is honoured, no migration."""
    from hermes_cli.plugins_state import PluginState

    home = tmp_path / "upgraded"
    monkeypatch.setenv("HERMES_HOME", str(home))
    with scope(home, CITED_DEFAULT_MODE="dot"):
        context = Context()
        context.state = PluginState("hermes-cited")
        context.state.set("mode.profile", "cited")
        plugin.register(context)
        result = context.hooks["pre_llm_call"][0](session_id="upgraded-session", turn_id="first-after-upgrade")
    assert result == {"context": plugin.CITED_RULES}


def test_profile_state_does_not_hide_a_host_validation_error(tmp_path, monkeypatch, host_paths):
    """D7: a host key validation error is a defect, never the default value."""
    from hermes_cli.plugins_state import PluginState

    home = tmp_path / "invalid-key"
    monkeypatch.setenv("HERMES_HOME", str(home))
    state = plugin._ProfileState(PluginState("hermes-cited"), str(home))
    with pytest.raises(ValueError):
        state.get("mode profile", None)


@pytest.mark.parametrize("callback", ["command", "transform"])
def test_failure_diagnostics_keep_the_profile_redaction_context(
    tmp_path, monkeypatch, caplog, host_paths, callback
):
    """D8/H19: no log record or returned message carries the failing profile's secret."""

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic fault carries " + PROFILE_SECRET)

    home = tmp_path / "english-owner"
    with scope(home):
        context = Context()
        plugin.register(context)
        with caplog.at_level(logging.ERROR, logger=plugin.__name__):
            if callback == "command":
                monkeypatch.setattr(context.state, "set", fail)
                result = context.commands["dot"]("")
            else:
                monkeypatch.setattr(plugin.delivery, "snapshot", fail)
                result = context.hooks["transform_llm_output"][0](
                    session_id="failure", turn_id="failure"
                )
    assert PROFILE_SECRET not in result
    assert PROFILE_SECRET not in caplog.text
