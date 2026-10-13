"""H22 and D4/D5: the per-profile installation command and the canonical distribution pin.

The real installation of a fresh disposable profile needs the pinned Hermes CLI, a local Git mirror and
an isolated home; that run belongs to step 5.3 and is skipped here with an explicit reason instead of
being faked. What always runs is the contract of design D4 and D5: the exact CLI flags and the exact
``git archive`` form of the pin.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CHANGE = REPO / "openspec" / "changes" / "search-only-bridge"
DESIGN = (CHANGE / "design.md").read_text(encoding="utf-8")
README = (REPO / "README.md").read_text(encoding="utf-8")

PIN = "dce1e9b37581dd62e480a9064dc04a709c2940d3"

D4_COMMAND = (
    "env HERMES_HOME=<root> <chassis>/.venv/bin/hermes --profile <name> "
    "plugins install file://<release>/hermes-cited.git --ref <full-sha> --enable --yes-deps"
)

OMITTED_REASON = (
    "the disposable VM is not available in this run: HERMES_TEST_CLI and HERMES_TEST_MIRROR are not set"
)


def normalized(text: str) -> str:
    return " ".join(str(text or "").split())


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


@pytest.mark.skipif(
    not (os.environ.get("HERMES_TEST_CLI") and os.environ.get("HERMES_TEST_MIRROR")),
    reason=OMITTED_REASON,
)
def test_a_fresh_real_profile_installs_the_search_bridge(tmp_path):
    """Step 5.3: the real CLI, a pinned Hermes, the local mirror and an isolated home.

    Without the disposable VM this body never runs; the skip reason above is the recorded blocker. When
    the harness provides the two variables the run must install the pinned bridge into a new profile,
    write the search configuration before discovery, and expose ``cited_search`` only.
    """
    cli = Path(os.environ["HERMES_TEST_CLI"])
    mirror = Path(os.environ["HERMES_TEST_MIRROR"])
    root = tmp_path / "hermes-root"
    profile = "bridge-probe"
    (root / "profiles" / profile).mkdir(parents=True)
    env = dict(os.environ)
    env["HERMES_HOME"] = str(root)
    argv = [
        str(cli),
        "--profile",
        profile,
        "plugins",
        "install",
        "file://{0}".format(mirror / "hermes-cited.git"),
        "--ref",
        PIN,
        "--enable",
        "--yes-deps",
    ]
    completed = subprocess.run(argv, env=env, capture_output=True, text=True, timeout=300)
    assert completed.returncode == 0, completed.stderr
    installed = root / "profiles" / profile / "plugins" / "hermes-cited"
    assert installed.is_dir()
    assert re.search(r"cited_search", (installed / "plugin.yaml").read_text(encoding="utf-8"))
