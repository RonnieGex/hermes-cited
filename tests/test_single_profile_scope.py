"""H23: the single-profile contract of Hermes 0.22, with a stand-in host.

Hermes 0.22 binds no secret scope while a process serves one profile (``tui_gateway/launch_profile_policy.py``
of v0.22.4, ``launch_body``: "Nothing is bound while single-profile"), and its own ``get_secret`` then reads
the launch profile; once a second profile is served, multiplexing is active and an unscoped read raises
``UnscopedSecretError``. These cases install a stand-in of the three host modules the plugin consults and
prove the branches: an installed scope is used as before, a missing scope while single-profile reads the
launch profile through the host's own builder ``owner_secret_scope(get_process_hermes_home())``, and a
missing scope while multiplexing is refused. No case reads the personal installation: the process home is a
temporary directory and every endpoint is a loopback fake.
"""

from __future__ import annotations

import sys
import types

import pytest

import bridge_support as support
from hermes_cited import config, plugin

CITED_MCP_TOKEN = "mcp-token-9c41d2"       # synthetic
CITED_SEARCH_TOKEN = "search-token-3e7b90"  # synthetic


class Host:
    """What the stand-in recorded: every home the launch-profile builder was asked for."""

    def __init__(self):
        self.owner_calls = []


def install_host(monkeypatch, *, scope=None, scope_home=None, multiplex=False, routed=False, process_home="",
                 owner=None, with_builder=True, builder_error=None):
    """Install ``agent.secret_scope``, ``hermes_constants`` and ``tui_gateway.launch_profile_policy`` stand-ins.

    ``scope`` is what ``current_secret_scope()`` answers (``None`` is the single-profile host of 0.22),
    ``multiplex`` is what ``is_multiplex_active()`` answers, ``routed`` is what ``serves_routed_profile()``
    answers (a ``HERMES_HOME`` override that names another home), ``process_home`` is what
    ``get_process_hermes_home()`` answers, and ``owner`` is the mapping ``owner_secret_scope`` returns.
    """
    host = Host()
    agent = types.ModuleType("agent")
    secret_scope = types.ModuleType("agent.secret_scope")
    secret_scope.current_secret_scope = lambda: scope
    secret_scope.current_secret_scope_home = lambda: scope_home
    # The host's accessor reads the bound mapping, as the real one does; it is never consulted for the launch profile.
    secret_scope.get_secret = lambda name, default="": (
        scope.get(name, default) if isinstance(scope, dict) else default
    )
    secret_scope.is_multiplex_active = lambda: multiplex
    secret_scope.serves_routed_profile = lambda: routed
    agent.secret_scope = secret_scope
    constants = types.ModuleType("hermes_constants")
    constants.get_process_hermes_home = lambda: process_home
    tui_gateway = types.ModuleType("tui_gateway")
    policy = types.ModuleType("tui_gateway.launch_profile_policy")

    def owner_secret_scope(home):
        host.owner_calls.append(home)
        if builder_error is not None:
            raise builder_error
        return owner if owner is not None else {}

    if with_builder:
        policy.owner_secret_scope = owner_secret_scope
    tui_gateway.launch_profile_policy = policy
    modules = (
        ("agent", agent),
        ("agent.secret_scope", secret_scope),
        ("hermes_constants", constants),
        ("tui_gateway", tui_gateway),
        ("tui_gateway.launch_profile_policy", policy),
    )
    for name, module in modules:
        monkeypatch.setitem(sys.modules, name, module)
    return host


def full_values(url, token, **extra):
    values = {"CITED_URL": url, "CITED_MCP_TOKEN": token}
    values.update(extra)
    return values


def assert_nothing_registered(context):
    assert context.tools == {}
    assert context.hooks == {}
    assert context.commands == {}
    assert context.skills == {}


def test_an_installed_scope_is_used_without_consulting_the_builder(monkeypatch, tmp_path):
    """Scenario: an installed scope is used as before."""
    installed = full_values("http://127.0.0.1:60123", CITED_MCP_TOKEN)
    host = install_host(
        monkeypatch,
        scope=installed,
        scope_home=str(tmp_path),
        process_home=tmp_path / "other-home",
        owner=full_values("http://127.0.0.1:1", "owner-token-never-read"),
    )
    scope = config.active_scope()
    assert scope.source == "hermes"
    assert scope.values is installed
    assert config.canonical_home(scope.home) == config.canonical_home(tmp_path)
    assert scope.get("CITED_URL") == "http://127.0.0.1:60123"
    assert host.owner_calls == []


def test_a_single_profile_host_without_a_scope_reads_the_launch_profile(monkeypatch, tmp_path):
    """Scenario: a single-profile host without a bound scope."""
    home = tmp_path / "launch-home"
    home.mkdir()
    owner = full_values("http://127.0.0.1:60123", CITED_MCP_TOKEN)
    host = install_host(monkeypatch, process_home=home, owner=owner)
    monkeypatch.setenv("CITED_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("CITED_MCP_TOKEN", "root-environment-token")
    scope = config.active_scope()
    assert scope.source == "hermes"
    assert scope.getter is None
    assert scope.values is owner
    assert config.canonical_home(scope.home) == config.canonical_home(home)
    assert scope.get("CITED_URL") == "http://127.0.0.1:60123"
    assert scope.get("CITED_MCP_TOKEN") == CITED_MCP_TOKEN
    assert host.owner_calls == [str(home)]


def test_a_single_profile_host_registers_full_and_calls_cited_with_the_launch_profile(
    monkeypatch, tmp_path, cited_factory
):
    """The handler of a single-profile registration sends the launch profile's bearer, never the root one."""
    full = cited_factory()
    home = tmp_path / "launch-home"
    home.mkdir()
    host = install_host(monkeypatch, process_home=home, owner=full_values(full.url, full.token))
    monkeypatch.setenv("CITED_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("CITED_MCP_TOKEN", "root-environment-token")
    context = support.FakeContext()
    plugin.register(context)
    assert set(context.tools) == {"cited_search", "cited_ask", "cited_quote"}
    answer = context.tools["cited_search"]["handler"]({"query": "precio"})
    assert isinstance(answer, str) and answer
    assert full.token not in answer
    call = full.last_call("cited_search")
    assert call is not None
    assert call["path"] == "/api/mcp"
    assert call["headers"]["authorization"] == "Bearer {0}".format(full.token)
    assert "root-environment" not in call["headers"]["authorization"]
    assert host.owner_calls and all(called == str(home) for called in host.owner_calls)


def test_a_single_profile_host_registers_search_against_the_chassis(monkeypatch, tmp_path, chassis):
    """Search mode under the single-profile contract: one tool, the search bearer, the chassis surface."""
    home = tmp_path / "launch-home"
    home.mkdir()
    install_host(monkeypatch, process_home=home, owner=support.search_values(chassis.url, chassis.token))
    monkeypatch.setenv("CITED_SEARCH_TOKEN", "root-environment-search-token")
    context = support.FakeContext()
    plugin.register(context)
    assert list(context.tools) == ["cited_search"]
    assert context.hooks == {}
    assert context.commands == {}
    assert context.skills == {}
    context.tools["cited_search"]["handler"]({"query": "hours"})
    call = chassis.fake.last_call()
    assert call is not None
    assert call["path"] == "/api/chassis/mcp"
    assert call["headers"]["authorization"] == "Bearer {0}".format(chassis.token)


def test_the_launch_profile_is_read_fresh_on_every_call(monkeypatch, tmp_path, cited_factory):
    """A rotated value in the launch profile is sent on the next call, like a rotated profile value."""
    full = cited_factory()
    home = tmp_path / "launch-home"
    home.mkdir()
    first = full.token
    owner = full_values(full.url, first)
    host = install_host(monkeypatch, process_home=home, owner=owner)
    context = support.FakeContext()
    plugin.register(context)
    handler = context.tools["cited_search"]["handler"]
    handler({"query": "precio"})
    owner["CITED_MCP_TOKEN"] = "rotated-token-5d2e"
    full.token = "rotated-token-5d2e"
    handler({"query": "precio"})
    bearers = [
        request["headers"]["authorization"]
        for request in full.requests
        if (request.get("body") or {}).get("method") == "tools/call"
    ]
    assert bearers == ["Bearer {0}".format(first), "Bearer rotated-token-5d2e"]
    assert len(host.owner_calls) >= 2


@pytest.mark.parametrize("mode", ["full", "search"])
def test_a_multiplexing_host_without_a_scope_is_refused(monkeypatch, tmp_path, mode):
    """Scenario: a multiplexing host without a bound scope, as the host's own get_secret raises there."""
    owner = {
        "CITED_BRIDGE_TOOLS": mode,
        "CITED_URL": "http://127.0.0.1:60123",
        "CITED_MCP_TOKEN": CITED_MCP_TOKEN,
        "CITED_SEARCH_TOKEN": CITED_SEARCH_TOKEN,
    }
    host = install_host(monkeypatch, multiplex=True, process_home=tmp_path, owner=owner)
    with pytest.raises(config.CitedScopeError) as caught:
        config.active_scope()
    assert str(caught.value) == config.SCOPE_SENTENCE
    context = support.FakeContext()
    plugin.register(context)
    assert_nothing_registered(context)
    assert host.owner_calls == []


@pytest.mark.parametrize("mode", ["full", "search"])
def test_a_task_routed_to_another_profile_without_a_scope_is_refused(monkeypatch, tmp_path, mode):
    """A HERMES_HOME override that names another home, multiplexing inactive: the launch profile is the wrong one."""
    owner = {
        "CITED_BRIDGE_TOOLS": mode,
        "CITED_URL": "http://127.0.0.1:60123",
        "CITED_MCP_TOKEN": CITED_MCP_TOKEN,
        "CITED_SEARCH_TOKEN": CITED_SEARCH_TOKEN,
    }
    host = install_host(monkeypatch, routed=True, process_home=tmp_path, owner=owner)
    with pytest.raises(config.CitedScopeError) as caught:
        config.active_scope()
    assert str(caught.value) == config.SCOPE_SENTENCE
    context = support.FakeContext()
    plugin.register(context)
    assert_nothing_registered(context)
    assert host.owner_calls == []


def test_a_host_without_the_builder_keeps_the_refusal(monkeypatch, tmp_path):
    """Scenario: a host without the builder (the shape of 0.21) is refused as before."""
    host = install_host(
        monkeypatch,
        process_home=tmp_path,
        owner=full_values("http://127.0.0.1:60123", CITED_MCP_TOKEN),
        with_builder=False,
    )
    with pytest.raises(config.CitedScopeError):
        config.active_scope()
    context = support.FakeContext()
    plugin.register(context)
    assert_nothing_registered(context)
    assert host.owner_calls == []


def test_a_blank_process_home_is_refused(monkeypatch):
    host = install_host(monkeypatch, process_home="", owner=full_values("http://127.0.0.1:60123", CITED_MCP_TOKEN))
    with pytest.raises(config.CitedScopeError):
        config.active_scope()
    assert host.owner_calls == []


def test_a_failing_builder_fails_closed_and_redacted(monkeypatch, tmp_path):
    install_host(
        monkeypatch,
        process_home=tmp_path,
        builder_error=RuntimeError("the profile store is unreadable: {0}".format(CITED_MCP_TOKEN)),
    )
    with pytest.raises(config.CitedScopeError) as caught:
        config.active_scope()
    assert str(caught.value) == config.SCOPE_SENTENCE
    assert CITED_MCP_TOKEN not in str(caught.value)
    context = support.FakeContext()
    plugin.register(context)
    assert_nothing_registered(context)


def test_a_builder_that_answers_no_mapping_fails_closed(monkeypatch, tmp_path):
    install_host(monkeypatch, process_home=tmp_path, owner=["not", "a", "mapping"])
    with pytest.raises(config.CitedScopeError):
        config.active_scope()


def test_an_explicit_scope_still_wins_over_the_single_profile_host(monkeypatch, tmp_path):
    """The test seam binds an explicit scope; the host is not consulted while it is bound."""
    host = install_host(monkeypatch, process_home=tmp_path / "launch", owner=full_values("http://127.0.0.1:1", "x"))
    values = support.search_values("http://127.0.0.1:60123", CITED_SEARCH_TOKEN)
    with support.bound_scope(values, home=tmp_path):
        scope = config.active_scope()
        assert scope.source == "explicit"
        assert scope.get("CITED_URL") == "http://127.0.0.1:60123"
    assert host.owner_calls == []
