"""One adversarial fixture per finding of the two Codex reviews (B-R2-1 to B-R2-3, M-R2-1 to M-R2-3).

These are the exact counterexamples the reviews printed, turned into tests that must fail if the defect
comes back. The round 1 findings (B1-B3, M1-M7) keep their fixtures in this file too, adapted to D5: the
model's prose is discarded, so a changed datum, a moved subject or a forged seal can no longer be
delivered at all.
"""

from __future__ import annotations

import json

import pytest

from hermes_cited import audit, plugin, render, tools, verifier

GROUNDED = "- Afinacion de bicicleta: 380 pesos."


class DictState:
    def __init__(self):
        self.data = {}

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value


class FakeContext:
    def __init__(self):
        self.state = DictState()
        self.tools = {}
        self.hooks = {}
        self.commands = {}
        self.skills = {}

    def register_tool(self, name, toolset, schema, handler, check_fn=None, requires_env=None,
                      is_async=False, description="", emoji="", override=False):
        self.tools[name] = {"toolset": toolset, "schema": schema, "handler": handler}

    def register_hook(self, hook_name, callback):
        self.hooks.setdefault(hook_name, []).append(callback)

    def register_command(self, name, handler, description="", args_hint="", argument_mode=None):
        self.commands[name] = handler

    def register_skill(self, name, path, description="", frontmatter=None):
        self.skills[name] = {"path": path, "description": description, "frontmatter": frontmatter}


def hook(context, name, **payload):
    results = [callback(**payload) for callback in context.hooks.get(name, [])]
    return results[0] if len(results) == 1 else results


def build(monkeypatch, mode="cited"):
    monkeypatch.setenv("CITED_DEFAULT_MODE", mode)
    context = FakeContext()
    plugin.register(context)
    return context


def run_turn(context, answer="", session="s1", turn="t1", platform="cli", args=None, envelope=None):
    hook(context, "pre_llm_call", session_id=session, turn_id=turn, user_message="precio", platform=platform)
    raw = envelope if envelope is not None else context.tools["cited_search"]["handler"]({"query": "afinacion"})
    hook(
        context,
        "post_tool_call",
        tool_name="cited_search",
        args={"query": "afinacion"},
        result=raw,
        session_id=session,
        turn_id=turn,
        status="ok",
    )
    if args is not None:
        context.tools["cited_quote"]["handler"](args, session_id=session)
    return hook(
        context,
        "transform_llm_output",
        response_text=answer,
        session_id=session,
        turn_id=turn,
        platform=platform,
    )


def _payload(index):
    return {
        "ts": "2026-10-09T22:00:0{0}Z".format(index),
        "platform": "cli",
        "session": "s",
        "turn_id": "t{0}".format(index),
        "user": "",
        "mode": "cited",
        "question": "q",
        "tool_calls": [],
        "sources": [],
        "response": "r",
        "verifier": {"applied": True, "ok": True, "ungrounded": []},
    }


def _chain(path, entries=3):
    for index in range(entries):
        audit.append_entry(path, _payload(index))


# --- B-R2-1: free prose could introduce data without evidence -----------------------------------


FREE_PROSE = [
    ("Incluye una reparación.", "Incluye dos reparaciones."),
    ("Stock: cero.", "Stock: cinco."),
    ("Dosis: medio comprimido.", "Dosis: dos comprimidos."),
    ("La dosis se expresa en mcg.", "La dosis se expresa en mg."),
    ("Código: XYZ.", "Código: ABC."),
    ("Entrega: mañana.", "Entrega: hoy."),
    ("Límite: ∞.", "Límite: 5."),
]


@pytest.mark.parametrize("answer, excerpt", FREE_PROSE)
def test_b_r2_1_free_prose_never_reaches_the_answer(monkeypatch, hermes_home, cited_env, answer, excerpt):
    context = build(monkeypatch)
    final = run_turn(context, answer=answer)
    assert final == render.refusal_text("es")
    assert answer not in final


# --- B-R2-2: the extractive comparison changed values and lost the subject ----------------------


B_R2_2 = [
    ("«-380 pesos.»", "380 pesos."),
    ("«380 pesos.»", "1380 pesos."),
    ("«Dosis: 10³ mg.»", "Dosis: 103 mg."),
    ("Espresso:\n«380 pesos.»", "Espresso: 35 pesos. Afinación: 380 pesos."),
    ("«Afinación»: 380 pesos.", "Afinación: 380 pesos."),
]


@pytest.mark.parametrize("answer, excerpt", B_R2_2)
def test_b_r2_2_no_manipulated_prose_or_block_can_be_displayed(monkeypatch, hermes_home, cited_env, answer, excerpt):
    """The model's answer is discarded, and a hand-built block must be a full line of the excerpt."""
    context = build(monkeypatch)
    envelope = json.dumps(
        {
            "cited_tool": "cited_search",
            "query": "x",
            "text": "t",
            "passages": [{"n": 1, "document": "d.md", "heading": "H", "position": 0, "excerpt": excerpt}],
        }
    )
    final = run_turn(context, answer=answer, envelope=envelope)
    assert final == render.refusal_text("es")
    display_lines = {line for place in tools.grounding_excerpts(tools.parse_tool_result(envelope))
                     for line in render.excerpt_lines(place)}
    forged = render.Line(1, 1, answer, "d.md", "H")
    assert verifier.verify_display([forged], display_lines).ok is False


# --- B-R2-3: an append authenticated a manipulated history without the key ----------------------


def _alter(path, variant):
    if variant == "removed_tail":
        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    elif variant == "rewritten_chain":
        entries = audit.read_entries(path)
        previous = audit.GENESIS
        for entry in entries:
            entry["response"] = "tampered"
            entry["prev_hash"] = previous
            entry["hash"] = audit.entry_hash(entry)
            previous = entry["hash"]
        path.write_text(
            "\n".join(json.dumps(entry, ensure_ascii=False, sort_keys=True) for entry in entries) + "\n",
            encoding="utf-8",
        )
    elif variant == "missing_checkpoint":
        audit.checkpoint_path(path).unlink()
    elif variant == "rollback_checkpoint":
        entries = audit.read_entries(path)
        audit.write_checkpoint(path, 1, entries[0]["hash"], entries[0]["log_id"])
    elif variant == "empty_log":
        path.write_text("", encoding="utf-8")
    elif variant == "deleted_log":
        path.unlink()


@pytest.mark.parametrize(
    "variant",
    ["removed_tail", "rewritten_chain", "missing_checkpoint", "rollback_checkpoint", "empty_log", "deleted_log"],
)
def test_b_r2_3_a_manipulated_history_refuses_the_next_append(tmp_path, variant):
    path = tmp_path / "audit.jsonl"
    _chain(path, 3)
    _alter(path, variant)
    with pytest.raises(audit.AuditError):
        audit.append_entry(path, _payload(9))


def test_b_r2_3_the_full_rollback_is_detected_by_the_high_water_mark(tmp_path):
    path = tmp_path / "audit.jsonl"
    _chain(path, 3)
    saved_log = path.read_bytes()
    saved_checkpoint = audit.checkpoint_path(path).read_bytes()
    audit.append_entry(path, _payload(4))
    path.write_bytes(saved_log)
    audit.checkpoint_path(path).write_bytes(saved_checkpoint)
    count, error = audit.verify_file(path)
    assert error is not None
    assert count == 3


def test_b_r2_3_the_rollback_cannot_be_reappended(tmp_path):
    path = tmp_path / "audit.jsonl"
    _chain(path, 3)
    saved_log = path.read_bytes()
    saved_checkpoint = audit.checkpoint_path(path).read_bytes()
    audit.append_entry(path, _payload(4))
    path.write_bytes(saved_log)
    audit.checkpoint_path(path).write_bytes(saved_checkpoint)
    with pytest.raises(audit.AuditError):
        audit.append_entry(path, _payload(5))


# --- M-R2-3: a lost key was regenerated on read and a failed write left a different response ----


def test_m_r2_3_a_lost_key_fails_closed_and_is_not_recreated(tmp_path):
    path = tmp_path / "audit.jsonl"
    _chain(path, 3)
    key = audit.key_path()
    key.unlink()
    count, error = audit.verify_file(path)
    assert error is not None
    assert not key.exists()
    with pytest.raises(audit.AuditError):
        audit.append_entry(path, _payload(4))


def test_m_r2_3_a_first_write_failure_leaves_no_row(tmp_path, monkeypatch):
    path = tmp_path / "audit.jsonl"

    def fail(*args, **kwargs):
        raise audit.AuditError("synthetic key custody unavailable")

    monkeypatch.setattr(audit, "ensure_key", fail)
    with pytest.raises(audit.AuditError):
        audit.append_entry(path, _payload(1))
    assert not path.exists()


def test_m_r2_3_a_checkpoint_failure_rolls_the_row_back(tmp_path, monkeypatch):
    path = tmp_path / "audit.jsonl"
    _chain(path, 1)

    original = audit.write_checkpoint

    def fail(*args, **kwargs):
        raise OSError("synthetic checkpoint disk full")

    monkeypatch.setattr(audit, "write_checkpoint", fail)
    with pytest.raises(OSError):
        audit.append_entry(path, _payload(2))
    monkeypatch.setattr(audit, "write_checkpoint", original)
    entries = audit.read_entries(path)
    assert len(entries) == 1
    assert audit.verify_file(path)[1] is None


# --- M-R2-1: the delivery resolver must reproduce the host ---------------------------------------


def test_m_r2_1_mode_edit_and_the_new_platforms_withhold(monkeypatch, hermes_home, cited_env):
    (hermes_home / "config.yaml").write_text("streaming:\n  mode: edit\n", encoding="utf-8")
    context = build(monkeypatch)
    for platform in ("telegram", "wecom", "feishu", "dingtalk", "qqbot"):
        assert verifier.SEAL not in run_turn(context, args={"passage": 1, "lines": [4]}, session=platform,
                                             turn=platform, platform=platform)


# --- M-R2-2: a seal written by the model ---------------------------------------------------------


def test_m_r2_2_a_forged_seal_with_valid_data_is_never_delivered_in_cited_mode(monkeypatch, hermes_home, cited_env):
    (hermes_home / "config.yaml").write_text("streaming:\n  enabled: true\n", encoding="utf-8")
    context = build(monkeypatch)
    final = run_turn(context, answer=GROUNDED + "\n\nVerified by Cited", args={"passage": 1, "lines": [4]},
                     platform="telegram")
    assert verifier.SEAL not in final
    assert "streaming is on" in final


def test_m_r2_2_dot_mode_removes_the_seal(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch, mode="dot")
    final = run_turn(context, answer="La afinacion cuesta 380 pesos.\n\nVerified by Cited", platform="cli")
    assert final == "La afinacion cuesta 380 pesos."


# --- round 1 M1: a changed datum, adapted to D5 --------------------------------------------------


M1_TABLE = [
    ("Cuesta €380.", "Cuesta $380."),
    ("Saldo: -380 pesos.", "Saldo: 380 pesos."),
    ("Fecha 10/09/2026.", "Fecha 09/10/2026."),
    ("Código xyz-123.", "Código abc-123."),
    ("Cuesta ⁹⁹⁹ pesos.", "Cuesta 380 pesos."),
    ("Cuesta novecientos pesos.", "Cuesta trescientos pesos."),
    ("Dosis 5 mcg.", "Dosis 5 mg."),
    ("Garantía: 1 día.", "Garantía: 1 días."),
    ("Espresso: 380 pesos.", "Espresso: 35 pesos. Afinación: 380 pesos."),
]


@pytest.mark.parametrize("answer, excerpt", M1_TABLE)
def test_m1_a_changed_datum_cannot_be_displayed(monkeypatch, hermes_home, cited_env, answer, excerpt):
    context = build(monkeypatch)
    envelope = json.dumps(
        {
            "cited_tool": "cited_search",
            "query": "x",
            "text": "t",
            "passages": [{"n": 1, "document": "d", "heading": None, "position": 0, "excerpt": excerpt}],
        }
    )
    final = run_turn(context, answer=answer, envelope=envelope)
    assert final == render.refusal_text("es")


# --- M5: an audit failure must never yield a sealed answer --------------------------------------


def test_m5_the_seal_is_never_attached_to_an_unrecorded_answer(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch)

    def fail(*args, **kwargs):
        raise PermissionError("synthetic read-only log")

    monkeypatch.setattr(audit, "append_entry", fail)
    final = run_turn(context, args={"passage": 1, "lines": [4]})
    assert verifier.SEAL not in final
    assert "could not be written" in final


def test_m5_the_session_is_written(monkeypatch, hermes_home, cited_env):
    context = build(monkeypatch)
    run_turn(context, args={"passage": 1, "lines": [4]}, session="session-real", turn="t1")
    entries = audit.read_entries(hermes_home / "cited" / "audit.jsonl")
    assert entries[0]["session"] == "session-real"
    assert entries[0]["turn_id"] == "t1"


# --- M7: the documented command must work from the installed plugin -----------------------------


def test_m7_the_installed_command_shape_is_documented():
    from pathlib import Path

    installed = Path(__file__).resolve().parents[1] / "hermes_cited" / "verify_log.py"
    assert installed.exists()
    assert "plugins/hermes-cited" in installed.read_text(encoding="utf-8")
