"""H22 and D4/D5: the per-profile installation command and the canonical distribution pin.

The real installation of a fresh disposable profile needs the pinned Hermes CLI, a local Git mirror,
a ``bridge.lock`` with the canonical archive digest and an isolated home; that run belongs to step 5.3
and is skipped here with an explicit reason instead of being faked. The skipped runner is complete on
purpose (round 3, M01): it keeps the **host** pin and the **bridge** ref separate, verifies that the
provided CLI really is the checkout of the pinned host, validates the canonical
``git archive --format=tar`` against the lock's SHA-256 and byte size, writes the search configuration
before discovery, installs with design D4's exact flags, asks the **real** host loader for the effective
catalog of the new profile, and dispatches ``cited_search`` inside that profile's secret scope.

What always runs is the contract of design D4 and D5 and the mechanics of that verification: the exact
CLI flags, the exact archive form, the lock parser, the digest comparison and the catalog parser. The
checks are exercised offline against temporary Git repositories; no personal service or port is used.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
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
_VM_NAMES = (
    "HERMES_TEST_HOST_ROOT",
    "HERMES_TEST_MIRROR",
    "HERMES_TEST_BRIDGE_REF",
    "HERMES_TEST_BRIDGE_LOCK",
)

OMITTED_REASON = (
    "the disposable VM is not available in this run: "
    + ", ".join(_VM_NAMES)
    + " are not all set"
)

FULL_HOOKS = ("pre_llm_call", "post_tool_call", "transform_llm_output")


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


def _isolated_git_env(work: Path) -> dict:
    """D5: no global, system or info attribute override and no ``tar.umask`` override of the producer."""
    env = dict(os.environ)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = str(Path(work) / "no-global-gitconfig")
    env["GIT_ATTR_NOSYSTEM"] = "1"
    env["HOME"] = str(work)
    env["USERPROFILE"] = str(work)
    env["XDG_CONFIG_HOME"] = str(Path(work) / "xdg")
    return env


def _info_attributes(git_dir: Path) -> Path:
    nested = Path(git_dir) / ".git" / "info" / "attributes"
    if (Path(git_dir) / ".git").exists():
        return nested
    return Path(git_dir) / "info" / "attributes"


def _check_bridge_ref(bridge_ref, host_pin=HOST_PIN) -> str:
    """The bridge ref is the full lowercase commit of this repository and never the host pin (M01)."""
    text = str(bridge_ref or "").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", text):
        raise ValueError("the bridge ref must be the full 40-hex commit of the bridge")
    if text == host_pin:
        raise ValueError("the bridge ref must never be the host pin")
    return text


def _host_cli(host_root) -> Path:
    """The pinned chassis CLI of design D4: ``<chassis>/.venv/bin/hermes`` (or its Windows spelling)."""
    root = Path(host_root)
    for candidate in (root / ".venv" / "bin" / "hermes", root / ".venv" / "Scripts" / "hermes.exe"):
        if candidate.exists():
            return candidate
    raise FileNotFoundError("the pinned host has no .venv CLI: {0}".format(root))


def _host_python(host_root) -> Path:
    root = Path(host_root)
    for candidate in (root / ".venv" / "bin" / "python", root / ".venv" / "Scripts" / "python.exe"):
        if candidate.exists():
            return candidate
    raise FileNotFoundError("the pinned host has no .venv python: {0}".format(root))


def _check_host_pin(host_root, expected=HOST_PIN) -> str:
    """M01: the CLI is the checkout of the pinned host, proved by its own Git HEAD, never assumed."""
    head = _git(Path(host_root), "rev-parse", "HEAD").strip()
    if head != expected:
        raise ValueError(
            "the host checkout is {0}, not the pinned host {1}".format(head or "<unknown>", expected)
        )
    return head


@dataclass(frozen=True)
class BridgeLock:
    """The canonical distribution pin of D5: full SHA, SHA-256 of the tar and its byte size."""

    sha: str
    sha256: str
    size: int


def _read_bridge_lock(path) -> BridgeLock:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("bridge.lock must be a JSON object")
    sha = str(data.get("sha") or "").strip()
    digest = str(data.get("sha256") or "").strip().lower()
    try:
        size = int(data.get("size"))
    except (TypeError, ValueError):
        raise ValueError("bridge.lock must carry the byte size of the canonical archive") from None
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("bridge.lock must carry the full 40-hex commit")
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("bridge.lock must carry the SHA-256 of the canonical archive")
    if size <= 0:
        raise ValueError("bridge.lock must carry a positive byte size")
    return BridgeLock(sha=sha, sha256=digest, size=size)


def _canonical_archive(git_dir, sha: str, out) -> tuple:
    """``git archive --format=tar <sha>`` with D5's isolated Git configuration (M01)."""
    destination = Path(out)
    destination.parent.mkdir(parents=True, exist_ok=True)
    override = _info_attributes(Path(git_dir))
    if override.exists():
        raise ValueError("the mirror carries an untracked info/attributes override: {0}".format(override))
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(git_dir),
            "-c",
            "core.attributesFile=",
            "archive",
            "--format=tar",
            "--output=" + str(destination),
            str(sha),
        ],
        capture_output=True,
        text=True,
        timeout=300,
        env=_isolated_git_env(destination.parent),
    )
    if completed.returncode != 0:
        raise RuntimeError("git archive failed: {0}".format(completed.stderr.strip()))
    data = destination.read_bytes()
    return hashlib.sha256(data).hexdigest(), len(data)


def _verify_bridge_lock(git_dir, lock: BridgeLock, work) -> dict:
    """The canonical bytes must match the lock's SHA-256 and size; a Git SHA alone is not enough (M01)."""
    destination = Path(work) / "hermes-cited.tar"
    digest, size = _canonical_archive(git_dir, lock.sha, destination)
    if digest != lock.sha256 or size != lock.size:
        raise ValueError(
            "the canonical archive is sha256={0} size={1}, not the locked {2}/{3}".format(
                digest, size, lock.sha256, lock.size
            )
        )
    return {"sha": lock.sha, "sha256": digest, "size": size}


#: The probe runs inside the pinned host's own venv: it binds the profile scope the way the host does,
#: discovers plugins with the real loader and dispatches the tool through the real registry.
CATALOG_PROBE = """
import json
import sys
from pathlib import Path

home = Path(sys.argv[1])
values = {}
env_file = home / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()

from agent import secret_scope

token = secret_scope.set_secret_scope(values, profile_home=str(home))
try:
    from hermes_cli.plugins import (
        discover_plugins,
        get_plugin_commands,
        get_plugin_manager,
        iter_hook_callbacks,
    )
    from tools.registry import registry

    discover_plugins()
    manager = get_plugin_manager()
    catalog = {
        "plugins": manager.list_plugins(),
        "hooks": {
            name: len(iter_hook_callbacks(name))
            for name in ("pre_llm_call", "post_tool_call", "transform_llm_output")
        },
        "commands": sorted(get_plugin_commands()),
        "call": registry.dispatch("cited_search", {"query": "hours", "limit": 1}),
    }
finally:
    secret_scope.reset_secret_scope(token)

print(json.dumps(catalog, default=str))
"""


def _effective_catalog(python, profile_home) -> dict:
    """Ask the pinned host's real loader for the effective catalog of one profile (M01)."""
    completed = subprocess.run(
        [str(python), "-c", CATALOG_PROBE, str(profile_home)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if completed.returncode != 0:
        raise RuntimeError("the host loader probe failed: {0}".format(completed.stderr.strip()))
    return _parse_catalog(completed.stdout)


def _parse_catalog(raw: str) -> dict:
    """The JSON object the loader probe prints, validated into its effective fields."""
    lines = [line for line in str(raw or "").splitlines() if line.strip()]
    if not lines:
        raise ValueError("the host loader probe printed nothing")
    data = json.loads(lines[-1])
    if not isinstance(data, dict):
        raise ValueError("the host loader probe must print one JSON object")
    plugins = data.get("plugins")
    hooks = data.get("hooks")
    commands = data.get("commands")
    if not isinstance(plugins, list) or not isinstance(hooks, dict) or not isinstance(commands, list):
        raise ValueError("the catalog needs plugins, hooks and commands")
    return {"plugins": plugins, "hooks": hooks, "commands": commands, "call": data.get("call")}


def _assert_search_catalog(catalog: dict) -> dict:
    """H22/D4: the effective catalog of the search profile holds one tool and no full surface."""
    entries = [entry for entry in catalog["plugins"] if entry.get("name") == "hermes-cited"]
    assert len(entries) == 1, "the loaded catalog must hold exactly one hermes-cited plugin"
    entry = entries[0]
    assert entry.get("enabled") is True, "the installed bridge must be enabled"
    assert not entry.get("error"), "the loader must report no error for the bridge"
    assert entry.get("tools") == 1, "search registers exactly one tool"
    assert entry.get("hooks") == 0, "search registers no hook"
    assert entry.get("commands") == 0, "search registers no command"
    for name in FULL_HOOKS:
        assert catalog["hooks"].get(name, 0) == 0, "the full hook {0} must be absent".format(name)
    assert not {"cited", "dot"} & set(catalog["commands"]), "the full commands must be absent"
    call = catalog.get("call")
    assert isinstance(call, str), "the scoped dispatch must answer a string"
    envelope = json.loads(call)
    assert envelope.get("cited_tool") == "cited_search"
    return entry


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
    return importlib.import_module(name + ".hermes_cited.plugin")


def _activate_profile_scope(agent_secret_scope, values, profile_home: Path):
    return agent_secret_scope.set_secret_scope(values, profile_home=str(profile_home))


def _make_git_repo(path: Path) -> Path:
    """One temporary Git repository with a single commit, for the offline archive and pin checks."""
    path.mkdir(parents=True, exist_ok=True)
    env = _isolated_git_env(path)

    def run(*args):
        completed = subprocess.run(
            ["git", "-C", str(path), *args], capture_output=True, text=True, timeout=120, env=env
        )
        assert completed.returncode == 0, "git {0} failed: {1}".format(" ".join(args), completed.stderr)
        return completed.stdout

    run("init", "-q")
    run("config", "user.email", "bridge-probe@example.invalid")
    run("config", "user.name", "bridge probe")
    (path / "README.md").write_text("canonical archive probe\n", encoding="utf-8")
    run("add", "README.md")
    run("commit", "-q", "-m", "canonical archive probe")
    return path


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
    """The VM variables name the host checkout, the mirror, the bridge commit and its lock."""
    assert "HERMES_TEST_HOST_ROOT" in _VM_NAMES
    assert "HERMES_TEST_MIRROR" in _VM_NAMES
    assert "HERMES_TEST_BRIDGE_REF" in _VM_NAMES
    assert "HERMES_TEST_BRIDGE_LOCK" in _VM_NAMES
    assert len(_VM_NAMES) == 4


def test_the_host_pin_is_verified_against_the_host_checkout(tmp_path):
    """M01: the CLI is accepted only when its checkout is the pinned host."""
    host_root = _make_git_repo(tmp_path / "host")
    head = _git(host_root, "rev-parse", "HEAD").strip()
    assert _check_host_pin(host_root, expected=head) == head
    with pytest.raises(ValueError):
        _check_host_pin(host_root, expected="c" * 40)


def test_the_canonical_archive_matches_the_lock_source_bytes(tmp_path):
    """M01: the digest check is the SHA-256 and size of ``git archive --format=tar``, not a Git SHA."""
    source = _make_git_repo(tmp_path / "source")
    sha = _git(source, "rev-parse", "HEAD").strip()
    digest, size = _canonical_archive(source, sha, tmp_path / "archive.tar")
    assert len(digest) == 64 and size > 0
    lock_path = tmp_path / "bridge.lock"
    lock_path.write_text(json.dumps({"sha": sha, "sha256": digest, "size": size}), encoding="utf-8")
    verified = _verify_bridge_lock(source, _read_bridge_lock(lock_path), tmp_path / "work")
    assert verified == {"sha": sha, "sha256": digest, "size": size}


def test_a_tampered_lock_is_rejected(tmp_path):
    source = _make_git_repo(tmp_path / "source")
    sha = _git(source, "rev-parse", "HEAD").strip()
    digest, size = _canonical_archive(source, sha, tmp_path / "archive.tar")
    lock_path = tmp_path / "tampered.lock"
    lock_path.write_text(json.dumps({"sha": sha, "sha256": "0" * 64, "size": size}), encoding="utf-8")
    with pytest.raises(ValueError):
        _verify_bridge_lock(source, _read_bridge_lock(lock_path), tmp_path / "work")
    lock_path.write_text(json.dumps({"sha": sha, "sha256": digest, "size": size + 1}), encoding="utf-8")
    with pytest.raises(ValueError):
        _verify_bridge_lock(source, _read_bridge_lock(lock_path), tmp_path / "work2")


@pytest.mark.parametrize(
    "payload",
    [
        {"sha": "a" * 12, "sha256": "0" * 64, "size": 1},
        {"sha": "a" * 40, "sha256": "0" * 12, "size": 1},
        {"sha": "a" * 40, "sha256": "0" * 64, "size": 0},
        {"sha": "a" * 40, "sha256": "0" * 64},
    ],
)
def test_a_lock_without_a_full_sha_digest_and_size_is_rejected(tmp_path, payload):
    lock_path = tmp_path / "bridge.lock"
    lock_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        _read_bridge_lock(lock_path)


def test_the_catalog_parser_requires_the_loader_shape():
    with pytest.raises(ValueError):
        _parse_catalog("")
    with pytest.raises(ValueError):
        _parse_catalog('{"plugins": []}')
    catalog = _parse_catalog('noise\n{"plugins": [], "hooks": {}, "commands": [], "call": "{}"}\n')
    assert catalog["plugins"] == [] and catalog["hooks"] == {}


def _loader_catalog(**overrides):
    entry = {
        "name": "hermes-cited",
        "key": "hermes-cited",
        "kind": "user",
        "version": "0.2.0",
        "description": "",
        "source": "user",
        "enabled": True,
        "tools": 1,
        "hooks": 0,
        "commands": 0,
        "error": None,
    }
    entry.update(overrides)
    return {
        "plugins": [entry],
        "hooks": {"pre_llm_call": 0, "post_tool_call": 0, "transform_llm_output": 0},
        "commands": [],
        "call": json.dumps({"cited_tool": "cited_search", "query": "hours", "text": "", "passages": []}),
    }


def test_the_search_catalog_accepts_one_tool_and_no_full_surface():
    entry = _assert_search_catalog(_loader_catalog())
    assert entry["version"] == "0.2.0"


@pytest.mark.parametrize(
    "overrides",
    [
        {"tools": 3},
        {"hooks": 3},
        {"commands": 2},
        {"enabled": False},
        {"error": "synthetic load error"},
    ],
)
def test_the_search_catalog_rejects_a_full_surface(overrides):
    with pytest.raises(AssertionError):
        _assert_search_catalog(_loader_catalog(**overrides))


def test_the_search_catalog_rejects_a_full_hook_or_command():
    catalog = _loader_catalog()
    catalog["hooks"]["pre_llm_call"] = 1
    with pytest.raises(AssertionError):
        _assert_search_catalog(catalog)
    catalog = _loader_catalog()
    catalog["commands"] = ["cited", "dot"]
    with pytest.raises(AssertionError):
        _assert_search_catalog(catalog)


@pytest.mark.skipif(not _vm_ready(), reason=OMITTED_REASON)
def test_a_fresh_real_profile_installs_the_search_bridge(tmp_path):
    """Step 5.3: the real CLI, a pinned Hermes, the local mirror and an isolated home.

    Without the disposable VM this body never runs; the skip reason above is the recorded blocker. When
    the harness provides the four variables the run verifies the pinned **host** checkout, the canonical
    archive against ``bridge.lock``, installs the pinned **bridge** commit into a new profile, writes the
    search configuration before discovery, asks the real loader for the effective catalog and dispatches
    the tool in that profile's secret scope.
    """
    sys.path.insert(0, str(REPO / "tests"))
    import bridge_support
    from fakes.chassis_surface import start_chassis

    host_root = Path(os.environ["HERMES_TEST_HOST_ROOT"]).resolve()
    cli = _host_cli(host_root)
    python = _host_python(host_root)
    _check_host_pin(host_root)
    bridge_ref = _check_bridge_ref(os.environ["HERMES_TEST_BRIDGE_REF"])
    mirror = Path(os.environ["HERMES_TEST_MIRROR"]).resolve()
    git_dir = mirror / "hermes-cited.git"
    lock = _read_bridge_lock(os.environ["HERMES_TEST_BRIDGE_LOCK"])
    assert lock.sha == bridge_ref, "the lock must pin the bridge ref under test"
    assert _git(git_dir, "cat-file", "-t", bridge_ref).strip() == "commit"
    assert not os.access(str(mirror), os.W_OK), "the local mirror must be read-only"
    assert str(os.environ.get("HERMES_TEST_NETWORK_BLOCKED") or "") == "1", "the network must be blocked"
    verified = _verify_bridge_lock(git_dir, lock, tmp_path / "lock-work")

    root = tmp_path / "hermes-root"
    profile_home = root / "profiles" / _PROFILE
    profile_home.mkdir(parents=True)

    running = start_chassis()
    try:
        _write_profile_env(profile_home, running.url, running.token)
        completed = subprocess.run(
            _install_argv(cli, git_dir, _PROFILE, bridge_ref),
            env=dict(os.environ, HERMES_HOME=str(root), PYTHONDONTWRITEBYTECODE="1"),
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

        catalog = _effective_catalog(python, profile_home)
        _assert_search_catalog(catalog)
        request = running.fake.last_call()
        assert request["path"] == "/api/chassis/mcp"
        assert request["headers"]["authorization"] == "Bearer {0}".format(running.token)

        assert not (profile_home / "cited").exists(), "search must write nothing under the profile home"
        print(
            json.dumps(
                {
                    "host_pin": HOST_PIN,
                    "bridge_ref": bridge_ref,
                    "archive": verified,
                    "profile_inventory": bridge_support.inventory(profile_home),
                    "catalog": catalog,
                },
                indent=2,
            )
        )
    finally:
        running.stop()
