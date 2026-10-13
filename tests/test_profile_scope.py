"""H19 and D2: the closed mode and the profile-scoped configuration, fail closed.

Each case runs with a temporary ``HERMES_HOME`` and an explicit scope mapping, so no case reads the
process environment of the personal installation and no personal service is reachable (the guard of task
1.1 rejects 3240/3241 for the whole suite).
"""

from __future__ import annotations

import sys
import threading
import types

import pytest

import bridge_support as support
from hermes_cited import config, plugin, tools

CITED_MCP_TOKEN = "mcp-token-5e1c0a"       # synthetic
CITED_SEARCH_TOKEN = "search-token-9ab34f"  # synthetic


@pytest.mark.parametrize(
    "value, expected",
    [(None, "full"), ("", "full"), ("full", "full"), ("search", "search")],
)
def test_the_mode_is_closed_and_defaults_to_full(value, expected):
    assert config.bridge_mode_of(value) == expected


@pytest.mark.parametrize("value", ["bridge", "FULL", " Search ", "full ", "   "])
def test_an_unknown_mode_is_refused_without_echoing_a_secret(value):
    with pytest.raises(config.CitedConfigError) as caught:
        config.bridge_mode_of(value)
    message = str(caught.value)
    assert config.BRIDGE_TOOLS_ENV in message
    assert "bridge" not in message


def test_an_explicit_scope_is_used_and_released(tmp_path):
    values = support.search_values("http://127.0.0.1:60123", CITED_SEARCH_TOKEN)
    with support.bound_scope(values, home=tmp_path):
        scope = config.active_scope()
        assert scope.source == "explicit"
        assert scope.get("CITED_URL") == "http://127.0.0.1:60123"
    with pytest.raises(config.CitedScopeError):
        config.search_settings_for(support.registration(home=tmp_path))


def test_the_search_path_never_reads_the_mcp_token(chassis, tmp_path):
    home = tmp_path / "search-home"
    home.mkdir()
    values = support.SpyMapping(
        support.search_values(chassis.url, chassis.token, CITED_MCP_TOKEN=CITED_MCP_TOKEN)
    )
    with support.bound_scope(values, home=home):
        settings = config.search_settings_for(support.registration(home=home))
        assert settings.token == chassis.token
        assert settings.url == chassis.url
    assert values.violations == []
    assert "CITED_MCP_TOKEN" not in values.accessed


def test_a_missing_home_refuses_before_any_request(chassis):
    values = support.search_values(chassis.url, chassis.token)
    with support.bound_scope(values, home=""):
        answer = tools.search_only({"query": "hours"}, support.registration(home=""))
    assert "Cited" in answer
    assert chassis.fake.requests == []


def test_a_changed_home_refuses_before_any_request(chassis, tmp_path):
    values = support.search_values(chassis.url, chassis.token)
    with support.bound_scope(values, home=tmp_path / "home-a"):
        answer = tools.search_only({"query": "hours"}, support.registration(home=tmp_path / "home-b"))
    assert "Cited" in answer
    assert chassis.fake.requests == []


def test_a_changed_mode_refuses_before_any_request(chassis, tmp_path):
    values = support.search_values(chassis.url, chassis.token)
    with support.bound_scope(values, home=tmp_path):
        answer = tools.search_only({"query": "hours"}, support.registration(mode="full", home=tmp_path))
    assert "Cited" in answer
    assert chassis.fake.requests == []


def test_the_active_scope_requires_a_mapping_when_the_agent_package_is_present(monkeypatch):
    """Present but empty is not the same as absent: it fails closed instead of reading os.environ."""
    agent = types.ModuleType("agent")
    secret_scope = types.ModuleType("agent.secret_scope")
    secret_scope.current_secret_scope = lambda: None
    secret_scope.current_secret_scope_home = lambda: None
    secret_scope.get_secret = lambda name, default="": default
    agent.secret_scope = secret_scope
    monkeypatch.setitem(sys.modules, "agent", agent)
    monkeypatch.setitem(sys.modules, "agent.secret_scope", secret_scope)
    monkeypatch.setenv("CITED_URL", "http://127.0.0.1:60123")
    with pytest.raises(config.CitedScopeError):
        config.active_scope()


def test_a_failing_accessor_fails_closed(monkeypatch):
    agent = types.ModuleType("agent")
    secret_scope = types.ModuleType("agent.secret_scope")

    def explode():
        raise RuntimeError("the profile store is unreadable")

    secret_scope.current_secret_scope = explode
    secret_scope.current_secret_scope_home = lambda: "/tmp/home"
    secret_scope.get_secret = lambda name, default="": default
    agent.secret_scope = secret_scope
    monkeypatch.setitem(sys.modules, "agent", agent)
    monkeypatch.setitem(sys.modules, "agent.secret_scope", secret_scope)
    with pytest.raises(config.CitedScopeError):
        config.active_scope()


def _install_fake_agent(monkeypatch, values, home, getter=None):
    """Install a stand-in ``agent.secret_scope`` so the host is present but its scope can be probed."""
    agent = types.ModuleType("agent")
    secret_scope = types.ModuleType("agent.secret_scope")
    secret_scope.current_secret_scope = lambda: values
    secret_scope.current_secret_scope_home = lambda: home
    secret_scope.get_secret = getter if getter is not None else (lambda name, default="": default)
    agent.secret_scope = secret_scope
    monkeypatch.setitem(sys.modules, "agent", agent)
    monkeypatch.setitem(sys.modules, "agent.secret_scope", secret_scope)
    return secret_scope


def test_a_non_mapping_scope_fails_closed(monkeypatch):
    """D2: the accessor must answer a Mapping, not merely a non-null value."""
    _install_fake_agent(monkeypatch, values=["not", "a", "mapping"], home="/tmp/home")
    with pytest.raises(config.CitedScopeError):
        config.active_scope()


def test_a_blank_home_fails_closed(monkeypatch):
    _install_fake_agent(monkeypatch, values={"CITED_URL": "http://127.0.0.1:60123"}, home="   ")
    with pytest.raises(config.CitedScopeError):
        config.active_scope()


def test_a_broken_host_dependency_is_not_an_absent_host(monkeypatch):
    """B01: ``ModuleNotFoundError`` from inside ``agent`` is a failing host, not an absent host."""
    import builtins

    original = builtins.__import__

    def failing(name, *args, **kwargs):
        if name == "agent":
            raise ModuleNotFoundError("No module named 'host_dependency'", name="host_dependency")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", failing)
    with pytest.raises(config.CitedScopeError):
        config.active_scope()


@pytest.mark.parametrize("mode", ["full", "search"])
def test_a_missing_host_scope_registers_nothing(monkeypatch, mode):
    """B01: with Hermes present and no readable scope the registration refuses every mode."""
    _install_fake_agent(monkeypatch, values=None, home=None)
    monkeypatch.setenv("CITED_URL", "http://127.0.0.1:60123")
    monkeypatch.setenv("CITED_MCP_TOKEN", CITED_MCP_TOKEN)
    monkeypatch.setenv("CITED_SEARCH_TOKEN", CITED_SEARCH_TOKEN)
    monkeypatch.setenv("CITED_BRIDGE_TOOLS", mode)
    context = support.FakeContext()
    plugin.register(context)
    assert context.tools == {}
    assert context.hooks == {}
    assert context.commands == {}
    assert context.skills == {}


def test_an_equivalent_home_spelling_keeps_the_identity(tmp_path):
    """m01: the same directory written through ``..`` is the same profile identity."""
    values = support.search_values("http://127.0.0.1:60123", CITED_SEARCH_TOKEN)
    alias = str(tmp_path / "child" / "..")
    with support.bound_scope(values, home=alias):
        settings = config.search_settings_for(support.registration(home=tmp_path))
    assert settings.token == CITED_SEARCH_TOKEN
    assert settings.url == "http://127.0.0.1:60123"


def test_a_different_home_stays_refused_after_normalization(tmp_path):
    """m01: normalization must not make two genuinely different homes look equal."""
    values = support.search_values("http://127.0.0.1:60123", CITED_SEARCH_TOKEN)
    with support.bound_scope(values, home=tmp_path / "home-a"):
        with pytest.raises(config.CitedScopeError):
            config.search_settings_for(support.registration(home=tmp_path / "home-b"))


def test_a_rotated_token_is_read_fresh_on_every_call(chassis, tmp_path):
    values = support.search_values(chassis.url, CITED_SEARCH_TOKEN)
    with support.bound_scope(values, home=tmp_path):
        registration = support.registration(home=tmp_path)
        tools.search_only({"query": "hours"}, registration)
        values["CITED_SEARCH_TOKEN"] = "rotated-search-token-77c1"
        tools.search_only({"query": "hours"}, registration)
    bearers = [request["headers"]["authorization"] for request in chassis.fake.requests]
    assert bearers == ["Bearer {0}".format(CITED_SEARCH_TOKEN), "Bearer rotated-search-token-77c1"]


def test_concurrent_profiles_stay_independent(chassis_factory, cited_factory, tmp_path, monkeypatch):
    """H19: profiles A/B with different tokens, URLs and modes, against a contradictory root env."""
    full = cited_factory()
    search = chassis_factory()
    home_a = tmp_path / "home-a"
    home_b = tmp_path / "home-b"
    home_a.mkdir()
    home_b.mkdir()
    monkeypatch.setenv("CITED_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("CITED_MCP_TOKEN", "root-environment-token")
    monkeypatch.setenv("CITED_SEARCH_TOKEN", "root-environment-search-token")
    monkeypatch.setenv("CITED_BRIDGE_TOOLS", "search")

    full_values = {"CITED_BRIDGE_TOOLS": "full", "CITED_URL": full.url, "CITED_MCP_TOKEN": full.token}
    search_values = support.search_values(search.url, search.token)
    results = {}
    barrier = threading.Barrier(2)

    def run_full():
        with support.bound_scope(full_values, home=home_a):
            context = support.FakeContext()
            plugin.register(context)
            barrier.wait(timeout=10)
            results["full"] = context.tools["cited_search"]["handler"]({"query": "precio"})

    def run_search():
        with support.bound_scope(search_values, home=home_b):
            context = support.FakeContext()
            plugin.register(context)
            barrier.wait(timeout=10)
            results["search"] = context.tools["cited_search"]["handler"]({"query": "hours"})

    threads = [threading.Thread(target=run_full), threading.Thread(target=run_search)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert all(not thread.is_alive() for thread in threads)

    full_call = full.last_call("cited_search")
    search_call = search.fake.last_call()
    assert full_call is not None and search_call is not None
    assert full_call["headers"]["authorization"] == "Bearer {0}".format(full.token)
    assert full_call["path"] == "/api/mcp"
    assert search_call["headers"]["authorization"] == "Bearer {0}".format(search.token)
    assert search_call["path"] == "/api/chassis/mcp"
    assert len(full.requests) == 1
    assert len(search.fake.requests) == 1
    assert "root-environment" not in full_call["headers"]["authorization"]


def test_the_full_mode_still_reads_its_own_token_from_the_scope(cited_factory, tmp_path):
    full = cited_factory()
    values = {"CITED_BRIDGE_TOOLS": "full", "CITED_URL": full.url, "CITED_MCP_TOKEN": full.token}
    with support.bound_scope(values, home=tmp_path):
        settings = config.settings_for(support.registration(mode="full", home=tmp_path))
    assert settings.token == full.token
    assert settings.url == full.url
