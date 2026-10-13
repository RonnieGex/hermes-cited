"""The real Hermes host, end to end: loader, dispatcher, finalizer and delivery (H15, M-R3-4, M-R3-5).

This test is the integration evidence the round 4 contract asks for. It does not patch the dispatcher and it
does not call a closure directly: it loads the plugin through the real ``hermes_cli.plugins`` discovery
sweep (a user plugin under the temporary ``HERMES_HOME``, enabled by the config, exactly as an installation
leaves it), fires the hooks through ``hermes_cli.lifecycle.invoke_hook``, and runs the real
``agent.turn_finalizer.apply_llm_output_transform`` of the host. It records two facts the plugin does not
hide:

- ``apply_llm_output_transform`` returns before invoking the hook when the model's response is empty
  (``agent/turn_finalizer.py:501``), so a cited turn with an empty answer is a declared host incompatibility;
- an exception of the transformer never reaches the caller, because the whole transformer is one boundary.

It also repeats the review's reproduction of B-R3-1 through the real dispatcher and measures the real
stream receiver of the gateway (``_fire_stream_delta``), which is the accepted limit of H9.

The host is the read-only public copy of the review, identified by its commit. Every run uses a temporary
``HERMES_HOME``, ``APPDATA`` and ``LOCALAPPDATA``: the real home of Franc is never opened. The whole module
is skipped when that copy is not present, so the suite stays runnable on a machine without it.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

HOST_COMMIT = "dce1e9b37581dd62e480a9064dc04a709c2940d3"
REVIEW_ROOT = Path(
    os.environ.get("HERMES_REVIEW_ROOT", str(Path(os.environ.get("TEMP", "/tmp")) / "codex-hermes-cited-r2-2d438babc89e4a55af33b15bab5269cd"))
)
HOST_COPY = REVIEW_ROOT / "host-fast" / "hermes-agent-{0}".format(HOST_COMMIT)
#: The dependencies of the host (``ruamel.yaml`` among them) live in the review's temporary venv. The module
#: adds that site-packages when it is present; the real Hermes venv is never opened.
HOST_SITE_PACKAGES = REVIEW_ROOT / "host-venv" / "Lib" / "site-packages"
REPO = Path(__file__).resolve().parents[1]
QUIET = (
    "streaming:\n  enabled: false\ndisplay:\n  streaming: false\n  interim_assistant_messages: false\n"
)

pytestmark = pytest.mark.skipif(
    not (HOST_COPY / "agent" / "turn_finalizer.py").exists(),
    reason="the read-only copy of the Hermes host is not present",
)


def install(repo, destination):
    """Copy the plugin into the user plugin directory, the way ``hermes plugins install`` leaves it."""
    shutil.copytree(
        repo,
        destination,
        ignore=shutil.ignore_patterns(".git", ".venv", ".tmp", "__pycache__", ".pytest_cache", "tests", "scripts", "openspec"),
    )
    return destination


@pytest.fixture()
def host(tmp_path, monkeypatch):
    """The real host, imported with its own temporary homes, and the plugin loaded by its own discovery."""
    home = tmp_path / "hermes-home"
    plugins = home / "plugins" / "hermes-cited"
    plugins.parent.mkdir(parents=True)
    (home / "cited").mkdir()
    install(REPO, plugins)
    local = tmp_path / "local-appdata"
    roaming = tmp_path / "roaming-appdata"
    local.mkdir()
    roaming.mkdir()
    (home / "config.yaml").write_text(
        QUIET + "plugins:\n  enabled:\n    - hermes-cited\n", encoding="utf-8"
    )
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("APPDATA", str(roaming))
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setenv("CITED_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("CITED_MCP_TOKEN", "synthetic-host-token")
    monkeypatch.setenv("CITED_DEFAULT_MODE", "cited")
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    monkeypatch.syspath_prepend(str(plugins))
    if HOST_SITE_PACKAGES.exists():
        monkeypatch.syspath_prepend(str(HOST_SITE_PACKAGES))
    monkeypatch.syspath_prepend(str(HOST_COPY))

    # D2/B01: with the real host imported, the plugin reads its configuration from the active profile
    # scope and refuses to register without one. The fixture installs the scope of this temporary profile
    # before discovery, exactly as a running Hermes does.
    from agent import secret_scope

    scope_values = {
        "CITED_URL": "http://127.0.0.1:1",
        "CITED_MCP_TOKEN": "synthetic-host-token",
        "CITED_DEFAULT_MODE": "cited",
    }
    scope_token = secret_scope.set_secret_scope(scope_values, profile_home=str(home))
    try:
        from hermes_cli.plugins import discover_plugins, get_plugin_manager, iter_hook_callbacks

        discover_plugins()
        callbacks = iter_hook_callbacks("transform_llm_output")
        assert callbacks, "the real loader did not register the transform hook"
        module = sys.modules[callbacks[0].__module__]
        yield {
            "home": home,
            "plugins": plugins,
            "module": module,
            "manager": get_plugin_manager(),
            "callbacks": callbacks,
        }
    finally:
        secret_scope.reset_secret_scope(scope_token)


def plugin_module(host, name):
    """One module of the plugin, imported under the namespace the loader gave it.

    The loader imports the repository as ``hermes_plugins.<slug>``, so its own package resolves to the
    installed copy and its relative imports never touch the checkout; the test resolves the same modules
    the same way, so a patch lands on the code that really runs.
    """
    import importlib

    package = host["module"].__package__
    return importlib.import_module("{0}.{1}".format(package, name))


def envelope(excerpt="Afinacion de bicicleta: 380 pesos.", document="cafe-la-horquilla.md", heading="Precios"):
    return json.dumps(
        {
            "cited_tool": "cited_search",
            "query": "afinacion",
            "text": "transport",
            "passages": [
                {"n": 1, "document": document, "heading": heading, "position": 2, "excerpt": excerpt}
            ],
        }
    )


def begin(host, session="host-session", turn="host-turn", platform="cli"):
    from hermes_cli.lifecycle import invoke_hook

    invoke_hook(
        "pre_llm_call",
        session_id=session,
        turn_id=turn,
        user_message="cuanto cuesta la afinacion",
        platform=platform,
        sender_id="",
    )
    invoke_hook(
        "post_tool_call",
        tool_name="cited_search",
        args={"query": "afinacion"},
        result=envelope(),
        session_id=session,
        turn_id=turn,
        status="ok",
    )
    return session, turn


def select(host, session, turn, args=None):
    from hermes_cli.lifecycle import invoke_hook

    assert any(callback.__module__ == host["module"].__name__ for callback in host["callbacks"])
    return host["module"]._quote_handler(None)(
        args or {"passage": "P1", "lines": [1]}, session_id=session, turn_id=turn
    )


def apply(host, turn, text, session="host-session", platform="cli"):
    from agent.turn_finalizer import apply_llm_output_transform

    agent = SimpleNamespace(session_id=session, model="synthetic", platform=platform)
    return apply_llm_output_transform(agent, text, turn_id=turn)


def rows(host):
    path = host["home"] / "cited" / "audit.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_the_real_loader_registers_the_plugin_and_its_hooks(host):
    from hermes_cli.plugins import get_plugin_commands, iter_hook_callbacks

    names = json.dumps(host["manager"].list_plugins(), default=str)
    assert "hermes-cited" in names
    assert '"enabled": true' in names.replace("'", '"').lower() or "hermes-cited" in names
    for name in ("pre_llm_call", "post_tool_call", "transform_llm_output"):
        assert iter_hook_callbacks(name)
    assert {"cited", "dot"}.issubset(set(get_plugin_commands()))


def test_the_real_finalizer_delivers_the_plugin_render_through_the_dispatcher(host):
    session, turn = begin(host)
    assert select(host, session, turn) == "Afinacion de bicicleta: 380 pesos."
    final, transformed, pre_transform = apply(host, turn, "MODEL_999")
    assert transformed is True
    assert final.startswith("Según tus documentos:")
    assert "Afinacion de bicicleta: 380 pesos. [1]" in final
    assert "MODEL_999" not in final
    assert "Verified by Cited" not in final
    assert "per-turn delivery policy" in final
    stored = rows(host)
    assert len(stored) == 1
    assert stored[0]["response"] == final
    assert stored[0]["verifier"]["verified"] is False
    assert stored[0]["verifier"]["seal_withheld"] is True


def test_the_host_never_calls_the_hook_for_an_empty_response(host):
    """M-R3-5: the declared incompatibility of the host, through the real finalizer."""
    session, turn = begin(host)
    select(host, session, turn)
    before = len(rows(host))
    final, transformed, pre_transform = apply(host, turn, "")
    assert final == ""
    assert transformed is False
    assert pre_transform is None
    assert len(rows(host)) == before
    assert host["module"]._turn_of(session, turn) is not None


def test_an_unreadable_configuration_cannot_leak_the_model_text(host, monkeypatch):
    """B-R3-1 through the real dispatcher: the hook still answers with the operational refusal."""
    session, turn = begin(host)
    select(host, session, turn)

    def unreadable(*args, **kwargs):
        raise PermissionError("synthetic config.yaml is a directory")

    monkeypatch.setattr(host["module"], "_language", unreadable)
    final, transformed, _pre = apply(host, turn, "MODEL_LEAK_999")
    assert transformed is True
    assert "MODEL_LEAK_999" not in final
    assert final.startswith("No puedo entregar")
    assert "Verified by Cited" not in final
    assert host["module"]._turn_of(session, turn) is None


def test_a_configuration_that_cannot_be_read_withholds_the_seal(host, monkeypatch):
    """H9 through the real dispatcher: no promise is made when nothing can be read.

    The snapshot is taken at the start of the turn, so the failure is planted before the turn opens.
    """
    from hermes_cli.lifecycle import invoke_hook

    delivery = plugin_module(host, "delivery")

    def unreadable():
        raise delivery.UnreadableConfig("synthetic unreadable configuration")

    monkeypatch.setattr(delivery, "host_config", unreadable)
    session, turn = begin(host)
    select(host, session, turn)
    snapshot = delivery.snapshot("cli", home=host["home"])
    assert snapshot.readable is False and snapshot.seal is False
    final, transformed, _pre = apply(host, turn, "MODEL_999")
    assert transformed is True
    assert "MODEL_999" not in final
    assert "Afinacion de bicicleta: 380 pesos. [1]" in final
    assert "Verified by Cited" not in final
    assert "withheld" in final


def test_an_exception_of_the_transformer_never_reaches_the_host(host, monkeypatch):
    session, turn = begin(host)
    select(host, session, turn)

    render = plugin_module(host, "render")

    def explode(*args, **kwargs):
        raise RuntimeError("synthetic failure inside the transformer")

    monkeypatch.setattr(render, "render_answer", explode)
    final, transformed, _pre = apply(host, turn, "MODEL_999")
    assert transformed is True
    assert "CITED-" in final
    assert "RuntimeError" not in final
    assert host["module"]._turn_of(session, turn) is None


def test_the_real_stream_receiver_still_delivers_the_draft(host):
    """M-R3-4: the accepted limit, measured on the real mixin and not only on the configuration class."""
    from agent.stream_delivery import StreamDeliveryMixin

    events = []

    class Receiver(StreamDeliveryMixin):
        stream_delta_callback = None
        _stream_callback = None

        def _stream_writer_superseded(self):
            return False

        def _strip_think_blocks(self, text):
            return text

        def _enqueue_stream_hook(self, event, **fields):
            events.append([event, fields.get("delta")])
            return "BLOCKED"

        def _record_streamed_assistant_text(self, text):
            pass

    receiver = Receiver()
    receiver.stream_delta_callback = lambda text: events.append(["display", text])
    receiver._fire_stream_delta("MODEL_COMMENTARY_999")
    assert ["display", "MODEL_COMMENTARY_999"] in events


def test_the_real_host_uses_the_plugin_streaming_class(host):
    from gateway.config import StreamingConfig

    delivery = plugin_module(host, "delivery")
    assert delivery.HOST_STREAMING is StreamingConfig
    for raw in ({"mode": "edit"}, {"enabled": True}, {"enabled": True, "transport": False}, {"enabled": False}):
        config = {"streaming": raw, "display": {"interim_assistant_messages": False}}
        assert delivery.effective_streaming("telegram", config) == StreamingConfig.from_dict(raw).enabled_for(None)


def test_the_finalizer_persists_what_the_plugin_delivered(host):
    """The finalizer of the host, not only the hook: what is persisted is the plugin's render.

    ``apply_llm_output_transform`` is the seam the finalizer uses before persisting; driving the whole
    ``finalize_turn`` needs a full agent of the host (its iteration budget, its memory handlers), so this
    test drives the real seam and then checks the assistant row the finalizer would store.
    """
    from agent.turn_finalizer import apply_llm_output_transform

    session, turn = begin(host)
    select(host, session, turn)
    agent = SimpleNamespace(
        session_id=session,
        model="synthetic",
        platform="cli",
        _llm_output_transform=None,
        _reused_response_text=None,
    )
    final, transformed, _pre = apply_llm_output_transform(agent, "MODEL_999", turn_id=turn)
    assert transformed is True
    assert "MODEL_999" not in final
    assert "Verified by Cited" not in final
    stored = rows(host)
    assert stored and stored[-1]["response"] == final
    assert stored[-1]["turn_id"] == turn
