"""H22 and D4/D5: the per-profile installation command and the canonical distribution pin.

The real installation of a fresh disposable profile needs the pinned Hermes CLI, a local Git mirror and
an isolated home; that run belongs to step 5.3 and is skipped here with an explicit reason instead of
being faked. The skipped runner is complete on purpose: it keeps the **host** pin and the **bridge** ref
separate, writes the search configuration before discovery, installs with design D4's exact flags,
verifies the installed commit and its effective catalog, and calls the handler inside that profile's
secret scope.

What always runs is the contract of design D4 and D5: the exact CLI flags and the exact ``git archive``
form of the pin.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CHANGE = REPO / "openspec" / "changes" / "search-only-bridge"
DESIGN = (CHANGE / "design.md").read_text(encoding="utf-8")
README = (REPO / "README.md").read_text(encoding="utf-8")
MANIFEST = (REPO / "plugin.yaml").read_text(encoding="utf-8")

#: The pinned **host**. It is the Hermes Agent commit, never the ref of the bridge.
HOST_PIN = "dce1e9b37581dd62e480a9064dc04a709c2940d3"
PIN = HOST_PIN

D4_COMMAND = (
    "env HERMES_HOME=<root> <chassis>/.venv/bin/hermes --profile <name> "
    "plugins install file://<release>/hermes-cited.git --ref <full-sha> --enable --yes-deps"
)

_PROFILE = "bridge-probe"
_VM_NAMES = ("HERMES_TEST_CLI", "HERMES_TEST_MIRROR", "HERMES_TEST_BRIDGE_REF")

OMITTED_REASON = (
    "the disposable VM is not available in this run: "
    + ", ".join(_VM_NAMES)
    + " are not all set"
)


def normalized(text: str) -> str:
    return " ".join(str(text or "").split())


def _vm_ready() -> bool:
    return all(str(os.environ.get(name) or "").strip() for name in _VM_NAMES)


def _git(cwd, *args) -> str:
    completed = subprocess.run(
        ["git", "-C", str(cwd), *args], capture_output=True, text=True, timeout=120
    )
    assert completed.returncode == 0, "git {0} failed: {1}".format(" ".join(args), completed.stderr)
    return completed.stdout


def _check_bridge_ref(bridge_ref, host_pin=HOST_PIN) -> str:
    """The bridge ref is the full lowercase commit of this repository and never the host pin (M01)."""
    text = str(bridge_ref or "").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", text):
        raise ValueError("the bridge ref must be the full 40-hex commit of the bridge")
    if text == host_pin:
        raise ValueError("the bridge ref must never be the host pin")
    return text


def _install_argv(cli, git_dir, profile, bridge_ref):
    """Design D4's exact per-profile install argv, with the bridge commit in a separate ``--ref``."""
    return [
        str(cli),
        "--profile",
        str(profile),
        "plugins",
        "install",
        "file://{0}".format(git_dir),
        "--ref",
        str(bridge_ref),
        "--enable",
        "--yes-deps",
    ]


def _load_yaml(path: Path) -> dict:
    try:
        import yaml
    except ModuleNotFoundError:  # pragma: no cover - the VM carries the host venv
        pytest.skip("PyYAML is required in the VM to read the installed manifest")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _write_profile_env(profile_home: Path, url: str, token: str) -> None:
    """The search configuration must exist before discovery (D4): URL, closed mode and search token."""
    (profile_home / ".env").write_text(
        "CITED_URL={0}\nCITED_BRIDGE_TOOLS=search\nCITED_SEARCH_TOKEN={1}\n".format(url, token),
        encoding="utf-8",
    )


def _load_installed_plugin(installed: Path):
    """Import the installed copy under its own name so the running checkout is never loaded twice."""
    import importlib
    import importlib.util

    name = "hermes_cited_installed"
    spec = importlib.util.spec_from_file_location(
        name, installed / "__init__.py", submodule_search_locations=[str(installed)]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return importlib.import_module(name + ".plugin")


def _activate_profile_scope(agent_secret_scope, values, profile_home: Path):
    return agent_secret_scope.set_secret_scope(values, profile_home=str(profile_home))


def test_the_d4_install_command_is_the_documented_one():
    assert D4_COMMAND in normalized(DESIGN)


def test_the_public_install_never_pins_through_repo_at_sha():
    command = normalized(DESIGN)
    assert "repo@sha" in command, "the design must forbid the ambiguous form"
    assert "--ref <full-sha>" in command
    assert "@" not in D4_COMMAND.split("plugins install", 1)[1]


def test_the_pin_is_a_plain_tar_of_the_full_sha():
    command = normalized(DESIGN)
    assert "git archive --format=tar <sha>" in command
    assert "no prefix or gzip" in command
    assert "--output" in command, "Windows must capture the bytes with git's binary --output option"


def test_the_readme_documents_the_per_profile_install():
    command = normalized(README)
    assert "--profile" in command
    assert "--ref" in command
    assert "plugins install" in command
    assert "git archive --format=tar" in command
    assert PIN in command or "full archived merge SHA" in command


def test_the_wire_fixture_hashes_to_the_pin_in_the_contract():
    import hashlib

    schema = (CHANGE / "fixtures" / "search-wire-v1.schema.json").read_bytes()
    assert hashlib.sha256(schema).hexdigest() in (CHANGE / "wire-contract.md").read_text(encoding="utf-8")


def test_the_delivered_manifest_is_search_compatible():
    """H22: only CITED_URL is universally required and both tokens are conditional secrets."""
    assert "version: 0.2.0" in MANIFEST
    assert "  - name: CITED_SEARCH_TOKEN" in MANIFEST
    assert "  - name: CITED_MCP_TOKEN" in MANIFEST
    assert MANIFEST.count("secret: true") == 2
    requires = MANIFEST.split("requires_env:", 1)[1].split("optional_env:", 1)[0]
    assert requires.count("- name:") == 1 and "CITED_URL" in requires


def test_the_install_argv_passes_the_bridge_ref_and_never_the_host_pin():
    """M01: the ``--ref`` of the install is the bridge commit, never the host pin."""
    bridge_ref = "b" * 40
    argv = _install_argv("hermes", Path("mirror") / "hermes-cited.git", _PROFILE, bridge_ref)
    assert argv[argv.index("--ref") + 1] == bridge_ref
    assert HOST_PIN not in argv
    assert argv[argv.index("plugins") + 1] == "install"


def test_the_host_pin_is_never_accepted_as_the_bridge_ref():
    with pytest.raises(ValueError):
        _check_bridge_ref(HOST_PIN)


@pytest.mark.parametrize("value", ["", "a" * 12, "B" * 40, "a" * 41, "a" * 39])
def test_a_bridge_ref_that_is_not_a_full_lowercase_sha_is_rejected(value):
    with pytest.raises(ValueError):
        _check_bridge_ref(value)


def test_the_isolated_runner_keeps_both_pins_separate():
    """The VM variables name the host CLI and the bridge commit independently."""
    assert "HERMES_TEST_CLI" in _VM_NAMES
    assert "HERMES_TEST_MIRROR" in _VM_NAMES
    assert "HERMES_TEST_BRIDGE_REF" in _VM_NAMES
    assert len(_VM_NAMES) == 3


@pytest.mark.skipif(not _vm_ready(), reason=OMITTED_REASON)
def test_a_fresh_real_profile_installs_the_search_bridge(tmp_path):
    """Step 5.3: the real CLI, a pinned Hermes, the local mirror and an isolated home.

    Without the disposable VM this body never runs; the skip reason above is the recorded blocker. When
    the harness provides the three variables the run must install the pinned **bridge** commit into a new
    profile, write the search configuration before discovery, and expose ``cited_search`` only.
    """
    cli = Path(os.environ["HERMES_TEST_CLI"]).resolve()
    mirror = Path(os.environ["HERMES_TEST_MIRROR"]).resolve()
    bridge_ref = _check_bridge_ref(os.environ["HERMES_TEST_BRIDGE_REF"])
    git_dir = mirror / "hermes-cited.git"
    assert _git(git_dir, "cat-file", "-t", bridge_ref).strip() == "commit"

    root = tmp_path / "hermes-root"
    profile_home = root / "profiles" / _PROFILE
    profile_home.mkdir(parents=True)

    sys.path.insert(0, str(REPO / "tests"))
    from fakes.chassis_surface import start_chassis

    running = start_chassis()
    try:
        _write_profile_env(profile_home, running.url, running.token)
        argv = _install_argv(cli, git_dir, _PROFILE, bridge_ref)
        completed = subprocess.run(
            argv,
            env=dict(os.environ, HERMES_HOME=str(root)),
            capture_output=True,
            text=True,
            timeout=600,
        )
        assert completed.returncode == 0, completed.stderr

        installed = profile_home / "plugins" / "hermes-cited"
        assert installed.is_dir()
        assert _git(installed, "rev-parse", "HEAD").strip() == bridge_ref
        assert _git(installed, "status", "--porcelain").strip() == ""

        manifest = _load_yaml(installed / "plugin.yaml")
        assert str(manifest["version"]) == "0.2.0"
        assert "cited_search" in manifest["provides_tools"]
        assert [item["name"] for item in manifest["requires_env"]] == ["CITED_URL"]

        from agent import secret_scope

        plugin = _load_installed_plugin(installed)
        sys.path.insert(0, str(REPO / "tests"))
        import bridge_support

        values = {
            "CITED_URL": running.url,
            "CITED_BRIDGE_TOOLS": "search",
            "CITED_SEARCH_TOKEN": running.token,
        }
        token = _activate_profile_scope(secret_scope, values, profile_home)
        try:
            context = bridge_support.FakeContext()
            plugin.register(context)
            assert set(context.tools) == {"cited_search"}
            assert context.hooks == {}
            assert context.commands == {}
            assert context.skills == {}
            answer = json.loads(context.tools["cited_search"]["handler"]({"query": "hours", "limit": 1}))
            assert answer["cited_tool"] == "cited_search"
            request = running.fake.last_call()
            assert request["path"] == "/api/chassis/mcp"
            assert request["headers"]["authorization"] == "Bearer {0}".format(running.token)
            assert "CITED_MCP_TOKEN" not in (profile_home / ".env").read_text(encoding="utf-8")
        finally:
            secret_scope.reset_secret_scope(token)
    finally:
        running.stop()
