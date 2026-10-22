"""H23 on the real host: the plugin under ``agent.secret_scope``, ``hermes_constants`` and
``tui_gateway.launch_profile_policy`` of Hermes Agent v0.22.4 (commit ``4d04303818b61bf3aa09278af48356315515965b``).

Opt-in evidence. ``HERMES_HOST_0_22_SOURCE`` names a checkout of that commit and ``HERMES_HOST_0_22_PYTHON`` an
interpreter that has the host's dependencies (``ruamel.yaml``); without the checkout the module is skipped with
the reason, so the suite stays runnable on a machine without it and in CI. The probe runs in a subprocess with
``-I``: no host module enters this process, the temporary ``HERMES_HOME`` is the only home the host sees, the
``APPDATA`` and ``LOCALAPPDATA`` of the probe are temporary too, and nothing opens a socket.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
HOST_COMMIT = "4d04303818b61bf3aa09278af48356315515965b"
SOURCE = Path(os.environ.get("HERMES_HOST_0_22_SOURCE", "").strip() or "/nonexistent")
PYTHON = os.environ.get("HERMES_HOST_0_22_PYTHON", "").strip() or sys.executable
PROBE_TOKEN = "probe-token-7f3a1c"  # synthetic

pytestmark = pytest.mark.skipif(
    not (SOURCE / "tui_gateway" / "launch_profile_policy.py").exists(),
    reason="HERMES_HOST_0_22_SOURCE does not name a checkout of Hermes Agent v0.22.4",
)

#: The probe, run with ``-I`` in a fresh interpreter: the host source and this repository on ``sys.path``.
DRIVER = r"""
import json, os, sys
source, repo = sys.argv[1], sys.argv[2]
sys.path.insert(0, source)
sys.path.insert(0, repo)
sys.path.insert(0, os.path.join(repo, "tests"))
out = {}
from agent.secret_scope import current_secret_scope, is_multiplex_active, set_multiplex_active
from hermes_constants import get_process_hermes_home
from tui_gateway import launch_profile_policy
out["scope_before"] = current_secret_scope()
out["multiplex_before"] = is_multiplex_active()
out["builder"] = hasattr(launch_profile_policy, "owner_secret_scope") and hasattr(launch_profile_policy, "launch_body")
out["process_home"] = str(get_process_hermes_home())
import bridge_support as support
from hermes_cited import config, plugin
scope = config.active_scope()
out["single"] = {
    "source": scope.source,
    "home": scope.home,
    "no_getter": scope.getter is None,
    "url": scope.get("CITED_URL"),
    "token_ok": scope.get("CITED_MCP_TOKEN") == os.environ.get("PROBE_TOKEN"),
}
context = support.FakeContext()
plugin.register(context)
out["single_tools"] = sorted(context.tools)
set_multiplex_active(True)
try:
    config.active_scope()
    out["multiplex"] = "no error"
except config.CitedScopeError as error:
    out["multiplex"] = "refused" if str(error) == config.SCOPE_SENTENCE else "other sentence"
context = support.FakeContext()
plugin.register(context)
out["multiplex_tools"] = sorted(context.tools)
print(json.dumps(out))
"""


def host_commit() -> str:
    """The commit of the checkout when its ``.git/HEAD`` holds one (a detached shallow clone), else empty."""
    head = SOURCE / ".git" / "HEAD"
    try:
        text = head.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    return text if len(text) == 40 and all(c in "0123456789abcdef" for c in text) else ""


def test_the_pinned_source_carries_the_single_profile_builder():
    policy = (SOURCE / "tui_gateway" / "launch_profile_policy.py").read_text(encoding="utf-8")
    assert "def owner_secret_scope(" in policy
    assert "def launch_body(" in policy
    secret_scope = (SOURCE / "agent" / "secret_scope.py").read_text(encoding="utf-8")
    assert "def is_multiplex_active(" in secret_scope
    assert "class UnscopedSecretError" in secret_scope
    commit = host_commit()
    assert commit in ("", HOST_COMMIT), commit


def test_the_plugin_registers_on_the_real_single_profile_host_and_refuses_under_multiplex(tmp_path):
    home = tmp_path / "hermes-home"
    home.mkdir()
    (home / ".env").write_text(
        "CITED_URL=http://127.0.0.1:60123\nCITED_MCP_TOKEN={0}\n".format(PROBE_TOKEN), encoding="utf-8"
    )
    env = {key: value for key, value in os.environ.items() if not key.startswith("CITED_")}
    env.update(
        {
            "HERMES_HOME": str(home),
            "APPDATA": str(tmp_path / "appdata"),
            "LOCALAPPDATA": str(tmp_path / "localappdata"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PROBE_TOKEN": PROBE_TOKEN,
            # The process environment holds a contradictory address: the launch profile's `.env` must win,
            # as the host's own `launch_secret_scope` documents (`.env` over the launch environment).
            "CITED_URL": "http://127.0.0.1:1",
        }
    )
    completed = subprocess.run(
        [PYTHON, "-I", "-c", DRIVER, str(SOURCE), str(REPO)],
        cwd=str(REPO),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert completed.returncode == 0, completed.stderr[-2000:]
    out = json.loads(completed.stdout.strip().splitlines()[-1])
    assert out["scope_before"] is None
    assert out["multiplex_before"] is False
    assert out["builder"] is True
    assert Path(out["process_home"]).resolve() == home.resolve()
    assert out["single"]["source"] == "hermes"
    assert out["single"]["no_getter"] is True
    assert Path(out["single"]["home"]).resolve() == home.resolve()
    assert out["single"]["url"] == "http://127.0.0.1:60123"
    assert out["single"]["token_ok"] is True
    assert out["single_tools"] == ["cited_ask", "cited_quote", "cited_search"]
    assert out["multiplex"] == "refused"
    assert out["multiplex_tools"] == []
    assert PROBE_TOKEN not in completed.stderr
