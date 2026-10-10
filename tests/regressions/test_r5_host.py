"""Permanent regressions of the fifth review through the real Hermes host.

R5 B-R5-1 (the generation of the incident cannot break the boundary of C1 when the entropy dependency
fails), R5 M-R5-1 (the snapshot must reject the real ``FailedConfigRead`` and must retain the seal for the
state it cannot accredit) and R5 M-R5-2 (the real finalizer can append text after the plugin composition,
so the record is the plugin's composition and never carries the seal). The module reuses the isolated
fixture of ``tests/test_host.py`` and is skipped when the read-only copy of the host is not present.
"""

from __future__ import annotations

import copy
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

MALFORMED = "display:\n  interim_assistant_messages: false\nstreaming: [\n"


def test_b_r5_1_a_failure_of_entropy_never_returns_the_model_prose(host, monkeypatch):
    """R5 B-R5-1: the review replaced ``secrets.token_hex`` and the real dispatcher kept the prose.

    The turn has a valid selection and the log does not exist yet, so the failing entropy is reached by
    the first append and by the generation of its refusal. The boundary must return the fixed operational
    refusal with the constant reserve code, no seal, no row and no turn state.
    """
    session, turn = begin(host)
    select(host, session, turn)

    def broken(*args, **kwargs):
        raise OSError("synthetic random source unavailable")

    monkeypatch.setattr(host["module"].secrets, "token_hex", broken)
    final, transformed, _pre = apply(host, turn, "MODEL_LEAK_999")
    assert transformed is True
    assert "MODEL_LEAK_999" not in final
    assert "Verified by Cited" not in final
    assert "CITED-" in final
    assert host["module"].RESERVE_INCIDENT_CODE in final
    assert rows(host) == []
    assert host["module"]._turn_of(session, turn) is None


def test_m_r5_2_the_real_footer_lands_after_the_plugin_composition_without_a_seal(host):
    """R5 M-R5-2: the real finalizer appends the mutation footer after the plugin persisted its render.

    D11/H16: the row registers the plugin's composition and carries no seal; the final message carries
    the footer. The limit is declared, not sold as an exact equality.
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
    final = _append_file_mutation_footer(agent, final, logging.getLogger("r5-regression"))
    final, _transformed, _pre = _apply_output_hooks(
        agent, final, logging.getLogger("r5-regression"), platform="cli", effective_task_id="t",
        turn_id=turn, original_user_message="synthetic", messages=[],
    )
    stored = rows(host)[-1]["response"]
    assert "SYNTHETIC_FILE_ERROR_999" in final
    assert "SYNTHETIC_FILE_ERROR_999" not in stored
    assert "Verified by Cited" not in stored
    assert "Verified by Cited" not in final
    assert final != stored
    assert rows(host)[-1]["composition_note"]


def test_m_r5_2_the_full_finalizer_records_the_composition_and_no_seal(host):
    """R5 M-R5-2: ``finalize_turn`` complete, with the real explainers mixin and a synthetic receipt."""
    from agent import turn_finalizer as tf
    from agent.turn_explainers import TurnExplainersMixin

    session, turn = begin(host)
    select(host, session, turn)
    persisted = []

    class Agent(TurnExplainersMixin):
        pass

    agent = Agent()
    attributes = dict(
        session_id=session, model="synthetic", provider="synthetic", base_url="", platform="cli",
        _persist_disabled=True, _file_mutation_verifier_enabled_cache=True,
        _turn_completion_explainer_enabled_cache=False, max_iterations=10,
        iteration_budget=SimpleNamespace(remaining=9, used=1, max_total=10),
        _drop_trailing_empty_response_scaffolding=lambda *a: None,
        _turn_failed_file_mutations={"synthetic.txt": {"tool": "patch", "error_preview": "SYNTHETIC_FILE_ERROR_999"}},
        context_compressor=SimpleNamespace(last_prompt_tokens=0), _tool_guardrail_halt_decision=None,
        _skill_nudge_interval=0, _iters_since_skill=0, valid_tool_names=set(), skip_background_review=True,
        _save_trajectory=lambda *a: None, _cleanup_task_resources=lambda *a: None,
        _persist_session=lambda messages, history: persisted.append(copy.deepcopy(messages)),
        _drain_pending_steer=lambda: [], clear_interrupt=lambda: None,
        _sync_external_memory_for_turn=lambda **kw: None,
    )
    for key, value in attributes.items():
        setattr(agent, key, value)
    for key in tf._SESSION_TOKEN_KEYS + tf._SESSION_COST_KEYS:
        setattr(agent, "session_" + key, 0)
    result = tf.finalize_turn(
        agent, final_response="MODEL_999", api_call_count=1, interrupted=False, failed=False,
        messages=[{"role": "user", "content": "synthetic"}], conversation_history=[],
        effective_task_id="synthetic", turn_id=turn, user_message="synthetic",
        original_user_message="synthetic", _should_review_memory=False,
        _turn_exit_reason="text_response(stop)",
    )
    actual = result["final_response"]
    entry = rows(host)[-1]
    stored = entry["response"]
    assert "SYNTHETIC_FILE_ERROR_999" in actual
    assert actual != stored
    assert "Verified by Cited" not in stored
    assert "Verified by Cited" not in actual
    assert entry["composition_note"]
    assert entry["verifier"]["verified"] is False
    assert entry["verifier"]["seal_withheld"] is True
    assert result.get("cleanup_errors") is None


def test_m_r5_1_the_real_loader_read_error_is_unreadable(host):
    """R5 M-R5-1: ``load_config_readonly`` keeps the last valid state as a ``FailedConfigRead``.

    The review loaded a valid quiet configuration and then broke the YAML; the snapshot accepted the
    mapping as readable. A read error is not a configuration and the snapshot must withhold.
    """
    from hermes_cli.config import load_config_readonly

    delivery = plugin_module(host, "delivery")
    valid = load_config_readonly()
    assert valid.get("streaming", {}).get("enabled") is False
    (host["home"] / "config.yaml").write_text(MALFORMED, encoding="utf-8")
    broken = load_config_readonly()
    assert getattr(broken, "read_error", None)
    snapshot = delivery.snapshot("telegram", home=host["home"])
    assert snapshot.readable is False
    assert snapshot.seal is False
    assert "unreadable" in snapshot.reasons


def test_m_r5_1_the_real_turn_runner_receives_receivers_the_file_hides(host):
    """R5 M-R5-1: the original reproduction of the review, without any double.

    The real ``TurnRunner._setup_stream_consumer`` connects TTS and commentary of a synthetic context
    while the file says quiet; the snapshot must not accredit the delivery and the answer must not carry
    the seal. The receivers and the context are synthetic; the method that connects them is real.
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
    final, _transformed, _pre = apply(host, turn, "MODEL_FINAL_999", platform="telegram")
    snapshot = rows(host)[-1]["delivery"]
    assert events
    assert "MODEL_AUDIO_999" in json.dumps(events)
    assert "MODEL_COMMENTARY_999" in json.dumps(events)
    # The file says quiet while the receivers are connected: that disagreement is exactly why the
    # snapshot cannot accredit the delivery, so the seal is retained even though the surfaces read clean.
    assert snapshot["commentary"] is False
    assert snapshot["tts"] is False
    assert snapshot["surface_clear"] is True
    assert snapshot["accredited"] is False
    assert snapshot["seal"] is False
    assert "Verified by Cited" not in final
    assert "per-turn delivery policy" in final
