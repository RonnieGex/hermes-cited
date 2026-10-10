"""Permanent regressions of the fourth review through the real Hermes host.

R4 M-R4-6 (the host can add text after the transformer and after the append), R4 B-R4-1 (the real
dispatcher keeps no prose when the resolution fails) and R4 M-R4-2 (the loaded host policy beats the
file). The module reuses the isolated fixture of ``tests/test_host.py`` and is skipped when the
read-only copy of the host is not present.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tests"))

from test_host import HOST_COPY, apply, begin, host, plugin_module, rows, select  # noqa: E402,F401

pytestmark = pytest.mark.skipif(
    not (HOST_COPY / "agent" / "turn_finalizer.py").exists(),
    reason="the read-only copy of the Hermes host is not present",
)


def test_m_r4_6_the_host_footer_lands_after_the_render_and_the_append(host):
    """R4 M-R4-6: the real finalizer appends the mutation footer after the plugin persisted its render.

    The limit is declared, not hidden: ``stored`` is the sealed render without the footer and the final
    message carries it, so the public C1 promise is about the plugin's composition and not about the
    routes of the host that add text afterwards.
    """
    from agent.turn_explainers import TurnExplainersMixin
    from agent.turn_finalizer import _append_file_mutation_footer, _apply_output_hooks, apply_llm_output_transform

    session, turn = begin(host)
    select(host, session, turn)

    class Agent(TurnExplainersMixin):
        pass

    agent = Agent()
    agent.session_id = session
    agent.model = "synthetic"
    agent.platform = "cli"
    agent._persist_disabled = True
    agent._file_mutation_verifier_enabled_cache = True
    agent._turn_failed_file_mutations = {
        "synthetic.txt": {"tool": "patch", "error_preview": "SYNTHETIC_FILE_ERROR_999"}
    }
    final, _transformed, _pre = apply_llm_output_transform(agent, "MODEL_LEAK_999", turn_id=turn)
    final = _append_file_mutation_footer(agent, final, logging.getLogger("r4-regression"))
    final, _transformed, _pre = _apply_output_hooks(
        agent, final, logging.getLogger("r4-regression"), platform="cli", effective_task_id="t",
        turn_id=turn, original_user_message="synthetic", messages=[],
    )
    stored = rows(host)[-1]["response"]
    assert "SYNTHETIC_FILE_ERROR_999" in final
    assert "SYNTHETIC_FILE_ERROR_999" not in stored
    assert final != stored
    assert "Verified by Cited" not in stored
    assert rows(host)[-1]["composition_note"]


def test_b_r4_1_the_real_dispatcher_never_keeps_the_prose_on_a_lookup_failure(host, monkeypatch):
    """R4 B-R4-1: with the real loader and dispatcher, a failing ``_turn_of`` used to leak the prose."""
    session, turn = begin(host)
    select(host, session, turn)

    def broken(*args, **kwargs):
        raise OSError("synthetic turn lookup failure")

    monkeypatch.setattr(host["module"], "_turn_of", broken)
    actual = apply(host, turn, "MODEL_LEAK_999")
    assert "MODEL_LEAK_999" not in actual[0]
    assert "Verified by Cited" not in actual[0]
    assert "CITED-" in actual[0]


def test_b_r4_1_the_real_dispatcher_never_keeps_the_prose_on_a_mode_failure(host, monkeypatch):
    """R4 B-R4-1: ``CITED_DEFAULT_MODE=cited`` with the mode state unreadable in pre and in transform."""
    from hermes_cli.lifecycle import invoke_hook

    modes = plugin_module(host, "modes")

    def broken(*args, **kwargs):
        raise OSError("synthetic mode state read failure")

    monkeypatch.setattr(modes, "resolve_mode", broken)
    try:
        invoke_hook("pre_llm_call", session_id="broken-mode", turn_id="t", platform="cli",
                    user_message="synthetic")
    except Exception:
        pass
    actual = apply(host, "t", "MODEL_LEAK_999", session="broken-mode")
    assert "MODEL_LEAK_999" not in actual[0]
    assert "Verified by Cited" not in actual[0]
    assert "CITED-" in actual[0]


def test_m_r4_2_the_real_turn_runner_receives_receivers_the_file_hides(host):
    """R4 M-R4-2, re-run by R5 M-R5-1 with the original reproduction and no double.

    The real ``TurnRunner._setup_stream_consumer`` connects TTS and commentary of a synthetic context while
    the configuration file says quiet. The review of round 5 showed that a double of ``host_config`` proved
    nothing; what this asserts is that the snapshot does not accredit the delivery it cannot see, so the
    seal is retained and the answer carries the fixed note.
    """
    from gateway.config import StreamingConfig
    from gateway.display_config import resolve_display_setting
    from gateway.run_turn_runner import TurnRunner

    events = []

    class Voice:
        def on_delta(self, text):
            events.append(["tts", text])

    effective = {
        "streaming": {"enabled": False},
        "display": {"interim_assistant_messages": True},
        "tts": {"auto_tts": True},
    }
    ctx = SimpleNamespace(
        mute_notification_reply=False, streaming_tts_consumer_holder=[Voice()], user_config=effective,
        resolve_display_setting=resolve_display_setting, scheduled_heartbeat=False,
        interim_assistant_messages_enabled=True, source=SimpleNamespace(platform="telegram"),
        _run_still_current=lambda: True, _status_adapter=True, _status_thread_metadata={},
    )
    runner = SimpleNamespace(
        config=SimpleNamespace(streaming=StreamingConfig.from_dict(effective["streaming"])),
        _delivery_adapter_for=lambda source: None,
    )
    turn_runner = TurnRunner(runner, ctx)
    turn_runner._send_status_text = lambda text, *args: events.append(["messaging", text])
    _consumer, delta, interim, _want = turn_runner._setup_stream_consumer("telegram")

    session, turn = begin(host, platform="telegram")
    select(host, session, turn)
    delta("MODEL_AUDIO_999")
    interim("MODEL_COMMENTARY_999")
    actual = apply(host, turn, "MODEL_FINAL_999", platform="telegram")
    stored = rows(host)[-1]
    assert "MODEL_AUDIO_999" in json.dumps(events)
    assert "MODEL_COMMENTARY_999" in json.dumps(events)
    assert stored["delivery"]["surface_clear"] is True
    assert stored["delivery"]["accredited"] is False
    assert stored["delivery"]["seal"] is False
    assert "Verified by Cited" not in actual[0]
    assert "per-turn delivery policy" in actual[0]


def test_m_r4_2_the_real_loader_read_error_is_unreadable(host):
    """R4 M-R4-2, re-run by R5 M-R5-1: the real ``FailedConfigRead`` of the host loader.

    The review loaded a valid quiet configuration and broke the YAML afterwards; Hermes keeps the last
    valid state as a ``FailedConfigRead``, which is a mapping, so the round 5 snapshot accepted it. A read
    error is not a configuration and the snapshot must withhold.
    """
    from hermes_cli.config import load_config_readonly

    delivery = plugin_module(host, "delivery")
    valid = load_config_readonly()
    assert valid.get("streaming", {}).get("enabled") is False
    (host["home"] / "config.yaml").write_text(
        "display:\n  interim_assistant_messages: false\nstreaming: [\n", encoding="utf-8"
    )
    broken = load_config_readonly()
    assert getattr(broken, "read_error", None)
    snapshot = delivery.snapshot("telegram", home=host["home"])
    assert snapshot.readable is False
    assert snapshot.seal is False
    assert "unreadable" in snapshot.reasons
