"""The isolation guard of the bridge (task 1.1): RED before the guard module exists, GREEN after it.

The guard is what makes every other run of this change safe: a temporary ``HERMES_HOME``, the personal
installation read-only and the ports 3240/3241 forbidden in every spelling. These tests exercise the
predicates themselves, so a future edit that weakens them turns red here.
"""

from __future__ import annotations

import os
import socket
import tempfile
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


def test_guard_environment_rejects_missing_overrides_before_any_effect():
    """M03: an empty run environment fails closed instead of being accepted as safe."""
    effects = []

    def run(env):
        guard.guard_environment(env)
        effects.append("started")

    with pytest.raises(guard.GuardError) as caught:
        run({})
    assert "HERMES_HOME" in str(caught.value)
    assert "CITED_URL" in str(caught.value)
    assert effects == []
    with pytest.raises(guard.GuardError):
        run({"CITED_URL": "http://127.0.0.1:60123"})
    with pytest.raises(guard.GuardError):
        run({"HERMES_HOME": ""})
    assert effects == []


def test_guard_environment_rejects_a_home_outside_every_workspace(tmp_path):
    guard.register_workspace(tmp_path / "workspace")
    with pytest.raises(guard.GuardError):
        guard.guard_environment(
            {
                "HERMES_HOME": str(Path.home() / "hermes-cited-guard-probe" / "home"),
                "CITED_URL": "http://127.0.0.1:60123",
            }
        )


def test_the_guard_does_not_authorise_all_of_the_temp_directory():
    """M03: authorising tempfile.gettempdir() would make every foreign path look registered."""
    assert Path(tempfile.gettempdir()).resolve() not in guard.workspaces()


def test_the_socket_guard_is_installed_for_every_test():
    """The autouse fixture of conftest replaces connect, so 3240 cannot be reached from a test."""
    with pytest.raises(guard.GuardError):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("127.0.0.1", 3240))


def test_the_guard_knows_the_real_run_uses_a_temporary_home():
    """A guard that cannot see the personal path would be decoration: prove it resolves on this box."""
    assert guard.personal_home().name == "hermes"
    assert str(guard.personal_home()).lower().endswith(os.path.join("local", "hermes"))


def test_the_fake_refuses_a_record_path_the_guard_rejects(tmp_path):
    """M02: el guard precede al efecto; el ``--record`` fuera del taller registrado no crea archivo."""
    import fakes.chassis_surface as fake_module

    outside = tmp_path.parent / "r3-unregistered-log.jsonl"
    with pytest.raises(guard.GuardError):
        guard.guard_path(outside, kind="fake request log")
    with pytest.raises(guard.GuardError):
        fake_module.start_chassis(log_path=outside)
    assert not outside.exists()


def test_the_fake_cli_refuses_a_record_path_before_any_effect(tmp_path):
    """M02: el entry point del script aplica el mismo guard antes de abrir el servidor.

    La ruta elegida está fuera del directorio temporal del proceso y fuera de todo taller registrado, así que
    el guard la rechaza antes de cualquier efecto (el hilo acota la espera en el estado RED).
    """
    import threading

    import fakes.chassis_surface as fake_module

    outside = Path.home() / "hermes-cited-r3-guard-probe" / "cli-log.jsonl"
    outcome = {}

    def run():
        try:
            fake_module.main(["--record", str(outside), "--port", "0", "--requests", "1"])
        except BaseException as error:  # noqa: BLE001 - the guard error is the assertion
            outcome["error"] = error

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(timeout=10)
    assert isinstance(outcome.get("error"), guard.GuardError)
    assert not outside.exists()


def test_the_fake_cli_prepares_a_guarded_record_path(tmp_path):
    """M02: un ``--record`` bajo el directorio temporal autoriza sólo su propio directorio padre."""
    import fakes.chassis_surface as fake_module

    record = tmp_path / "cli-record.jsonl"
    guarded = fake_module.prepare_cli_guard(str(record))
    assert guarded == record.resolve()
    with pytest.raises(guard.GuardError):
        fake_module.prepare_cli_guard(str(Path.home() / "hermes-cited-r3-guard-probe" / "cli.jsonl"))


def test_the_fake_writes_its_record_only_inside_the_registered_workspace(tmp_path):
    """M02: un ``--record`` registrado sí se escribe, y con el bearer redactado."""
    import json as _json

    import fakes.chassis_surface as fake_module

    log = tmp_path / "r3-record.jsonl"
    running = fake_module.start_chassis(log_path=log)
    try:
        token = running.token
        import urllib.request

        request = urllib.request.Request(
            running.url + "/api/chassis/mcp",
            data=_json.dumps({"jsonrpc": "2.0", "id": 7, "method": "tools/list", "params": {}}).encode(),
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + token},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            assert response.status == 200
    finally:
        running.stop()
    assert log.exists()
    body = log.read_text(encoding="utf-8")
    assert token not in body
    assert '"method": "tools/list"' in body or '"method":"tools/list"' in body
