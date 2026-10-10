"""Permanent regressions of the fourth review through the real Hermes host.

R4 M-R4-6 (the host can add text after the transformer and after the append), R4 B-R4-1 (the real
dispatcher keeps no prose when the resolution fails) and R4 M-R4-2 (the loaded host policy beats the
file). The module reuses the isolated fixture of ``tests/test_host.py`` and is skipped when the
read-only copy of the host is not present.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

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
    assert stored.rstrip().endswith("Verified by Cited")


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


def test_m_r4_2_the_real_host_policy_beats_the_file(host, monkeypatch):
    """R4 M-R4-2: the loaded object says TTS is on while the file says off; the answer is not sealed."""
    delivery = plugin_module(host, "delivery")
    effective = {
        "streaming": {"enabled": False},
        "display": {"streaming": False, "interim_assistant_messages": False},
        "tts": {"auto_tts": True},
    }
    monkeypatch.setattr(delivery, "host_config", lambda home=None: effective)
    session, turn = begin(host)
    select(host, session, turn)
    actual = apply(host, turn, "MODEL_999")
    stored = rows(host)[-1]
    assert "Verified by Cited" not in actual[0]
    assert "text to speech" in actual[0]
    assert stored["delivery"]["tts"] is True
    assert stored["delivery"]["source"] == "host"


def test_m_r4_2_a_host_that_cannot_answer_withholds_the_seal(host, monkeypatch):
    """R4 M-R4-2: the host is present and does not answer; the seal is withheld, not assumed."""
    delivery = plugin_module(host, "delivery")

    def broken(home=None):
        raise delivery.UnreadableConfig("the host configuration did not answer")

    monkeypatch.setattr(delivery, "host_config", broken)
    session, turn = begin(host)
    select(host, session, turn)
    actual = apply(host, turn, "MODEL_999")
    stored = rows(host)[-1]
    assert "Verified by Cited" not in actual[0]
    assert "withheld" in actual[0]
    assert stored["delivery"]["readable"] is False
    assert stored["verifier"]["seal_withheld"] is True
