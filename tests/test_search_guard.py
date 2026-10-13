"""The isolation guard of the bridge (task 1.1): RED before the guard module exists, GREEN after it.

The guard is what makes every other run of this change safe: a temporary ``HERMES_HOME``, the personal
installation read-only and the ports 3240/3241 forbidden in every spelling. These tests exercise the
predicates themselves, so a future edit that weakens them turns red here.
"""

from __future__ import annotations

import os
import socket
from pathlib import Path

import pytest

import search_guard as guard


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:3240/api/mcp",
        "http://localhost:3241/api/chassis/mcp",
        "http://127.0.0.1:3240/api/mcp",
        "http://127.0.0.2:3241/",
        "http://[::1]:3240/api/chassis/mcp",
        "http://[::ffff:127.0.0.1]:3241/",
        "http://0.0.0.0:3240/",
        "https://cited.example.com:3240/",
        "http://localhost.localdomain:3241/",
    ],
)
def test_the_guard_rejects_every_spelling_of_the_personal_ports(url):
    with pytest.raises(guard.GuardError):
        guard.guard_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:60123/api/chassis/mcp",
        "http://localhost:80/",
        "https://cited.example.com/api/chassis/mcp",
        "https://cited.example.com:443/",
    ],
)
def test_the_guard_allows_a_free_loopback_port_and_a_public_origin(url):
    guard.guard_url(url)


def test_the_guard_names_every_alias_of_loopback():
    for host in ("localhost", "LOCALHOST.", "127.0.0.1", "127.0.0.2", "0.0.0.0", "::1", "[::1]", "::ffff:127.0.0.1"):
        assert guard.canonical_host(host) == "loopback", host
    assert guard.canonical_host("cited.example.com") == "cited.example.com"
    assert guard.canonical_host("10.0.0.5") == "10.0.0.5"


def test_the_guard_rejects_the_socket_tuple_and_the_ipv6_tuple():
    with pytest.raises(guard.GuardError):
        guard.guard_socket_address(("127.0.0.1", 3240))
    with pytest.raises(guard.GuardError):
        guard.guard_socket_address(("::1", 3241, 0, 0))
    with pytest.raises(guard.GuardError):
        guard.guard_socket_address("localhost:3240")
    guard.guard_socket_address(("127.0.0.1", 60123))


def test_the_guard_rejects_a_port_outside_the_range():
    with pytest.raises(guard.GuardError):
        guard.guard_target("127.0.0.1", 0)
    with pytest.raises(guard.GuardError):
        guard.guard_target("127.0.0.1", "not-a-port")


def test_the_guard_rejects_the_personal_installation(tmp_path):
    personal = guard.personal_home()
    guard.register_workspace(tmp_path)
    with pytest.raises(guard.GuardError) as caught:
        guard.guard_path(personal / "profiles" / "default", kind="HERMES_HOME")
    assert "personal installation" in str(caught.value)


def test_the_guard_rejects_a_path_outside_the_registered_workspace(tmp_path):
    guard.register_workspace(tmp_path / "workspace")
    outside = Path.home() / "hermes-cited-guard-probe" / "home"
    with pytest.raises(guard.GuardError) as caught:
        guard.guard_path(outside, kind="HERMES_HOME")
    assert "outside every registered temporary workspace" in str(caught.value)


def test_the_guard_rejects_a_link_or_junction_that_escapes(tmp_path, monkeypatch):
    workspace = guard.register_workspace(tmp_path / "workspace")
    escaping = workspace / "link"
    escaping.mkdir(parents=True)
    monkeypatch.setattr(guard, "_is_link", lambda path: str(path) == str(escaping))
    with pytest.raises(guard.GuardError) as caught:
        guard.guard_path(escaping / "home", kind="HERMES_HOME")
    assert "link or junction" in str(caught.value)


def test_the_guard_accepts_the_temporary_workspace_of_a_test(tmp_path):
    workspace = guard.register_workspace(tmp_path)
    assert guard.guard_path(workspace / "hermes-home", kind="HERMES_HOME") == (workspace / "hermes-home").resolve()


def test_missing_overrides_fail_before_any_effect():
    effects = []

    def start(env):
        guard.require_names(env, ("HERMES_HOME", "CITED_URL"))
        effects.append("started")

    with pytest.raises(guard.GuardError) as caught:
        start({"HERMES_HOME": "C:/tmp/home"})
    assert "CITED_URL" in str(caught.value)
    assert effects == []


def test_the_guard_environment_rejects_a_forbidden_url(tmp_path):
    home = tmp_path / "hermes-home"
    home.mkdir()
    guard.register_workspace(tmp_path)
    with pytest.raises(guard.GuardError):
        guard.guard_environment({"HERMES_HOME": str(home), "CITED_URL": "http://127.0.0.1:3240"})
    guard.guard_environment({"HERMES_HOME": str(home), "CITED_URL": "http://127.0.0.1:60123"})


def test_the_socket_guard_is_installed_for_every_test():
    """The autouse fixture of conftest replaces connect, so 3240 cannot be reached from a test."""
    with pytest.raises(guard.GuardError):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("127.0.0.1", 3240))


def test_the_guard_knows_the_real_run_uses_a_temporary_home():
    """A guard that cannot see the personal path would be decoration: prove it resolves on this box."""
    assert guard.personal_home().name == "hermes"
    assert str(guard.personal_home()).lower().endswith(os.path.join("local", "hermes"))
