"""The hash-chained audit log, its checkpoint and its verifier (H5, M3, M4, D3)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from hermes_cited import audit

REPO = Path(__file__).resolve().parents[1]


def _payload(index):
    return {
        "ts": "2026-10-09T22:00:0{0}Z".format(index),
        "platform": "cli",
        "session": "session-1",
        "turn_id": "turn-{0}".format(index),
        "user": "",
        "mode": "cited",
        "question": "cuanto cuesta la afinacion",
        "tool_calls": [
            {
                "tool": "cited_search",
                "args": {"query": "precio"},
                "status": "ok",
                "excerpt_sha256": ["a" * 64],
                "excerpt_texts": ["Afinacion de bicicleta: 380 pesos."],
            }
        ],
        "sources": ["cafe-la-horquilla.md - Precios"],
        "response": "380 pesos [1].",
        "verifier": {"applied": True, "ok": True, "ungrounded": []},
    }


def _chain(path, entries=3):
    for index in range(entries):
        audit.append_entry(path, _payload(index))


def test_the_first_entry_links_to_the_genesis(tmp_path):
    path = tmp_path / "audit.jsonl"
    entry = audit.append_entry(path, _payload(1))
    assert entry["prev_hash"] == audit.GENESIS
    assert entry["seq"] == 1
    assert len(entry["hash"]) == 64
    assert entry["log_id"]


def test_each_entry_links_to_the_previous_one_and_counts(tmp_path):
    path = tmp_path / "audit.jsonl"
    first = audit.append_entry(path, _payload(1))
    second = audit.append_entry(path, _payload(2))
    assert second["prev_hash"] == first["hash"]
    assert second["seq"] == 2
    assert second["log_id"] == first["log_id"]


def test_a_fresh_chain_and_its_checkpoint_verify(tmp_path):
    path = tmp_path / "audit.jsonl"
    _chain(path, 3)
    count, error = audit.verify_file(path)
    assert error is None
    assert count == 3
    checkpoint = audit.read_checkpoint(path)
    assert checkpoint["count"] == 3


def test_every_required_field_is_written(tmp_path):
    path = tmp_path / "audit.jsonl"
    entry = audit.append_entry(path, _payload(1))
    for field in audit.REQUIRED_FIELDS:
        assert field in entry
    assert entry["tool_calls"][0]["args"] == {"query": "precio"}
    assert entry["tool_calls"][0]["excerpt_sha256"][0] == "a" * 64
    assert entry["session"] == "session-1"
    assert entry["turn_id"] == "turn-1"


def test_an_entry_without_the_schema_is_refused(tmp_path):
    path = tmp_path / "audit.jsonl"
    incomplete = _payload(1)
    del incomplete["response"]
    with pytest.raises(audit.AuditError):
        audit.append_entry(path, incomplete)
    assert not path.exists()


def test_an_altered_entry_is_detected(tmp_path):
    path = tmp_path / "audit.jsonl"
    _chain(path, 3)
    lines = path.read_text(encoding="utf-8").splitlines()
    entry = json.loads(lines[1])
    entry["response"] = "450 pesos [1]."
    lines[1] = json.dumps(entry, ensure_ascii=False)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    count, error = audit.verify_file(path)
    assert error is not None
    assert "2" in error


def test_a_removed_entry_is_detected(tmp_path):
    path = tmp_path / "audit.jsonl"
    _chain(path, 3)
    lines = path.read_text(encoding="utf-8").splitlines()
    del lines[1]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    count, error = audit.verify_file(path)
    assert error is not None


def test_a_reordered_entry_is_detected(tmp_path):
    path = tmp_path / "audit.jsonl"
    _chain(path, 3)
    lines = path.read_text(encoding="utf-8").splitlines()
    lines[1], lines[2] = lines[2], lines[1]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    count, error = audit.verify_file(path)
    assert error is not None


def test_a_truncated_line_is_detected(tmp_path):
    path = tmp_path / "audit.jsonl"
    _chain(path, 3)
    lines = path.read_text(encoding="utf-8").splitlines()
    lines[-1] = lines[-1][: len(lines[-1]) // 2]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    count, error = audit.verify_file(path)
    assert error is not None


def test_an_empty_or_missing_file_is_not_a_chain(tmp_path):
    path = tmp_path / "audit.jsonl"
    count, error = audit.verify_file(path)
    assert count == 0
    assert error is not None


def test_a_removed_last_entry_is_detected(tmp_path):
    """M4: the chain alone cannot see this; the checkpoint can."""
    path = tmp_path / "audit.jsonl"
    _chain(path, 3)
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    count, error = audit.verify_file(path)
    assert error is not None
    assert "checkpoint" in error


def test_a_cut_suffix_is_detected(tmp_path):
    path = tmp_path / "audit.jsonl"
    _chain(path, 5)
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(lines[:2]) + "\n", encoding="utf-8")
    count, error = audit.verify_file(path)
    assert error is not None


def test_a_rewritten_and_recomputed_chain_is_detected(tmp_path):
    path = tmp_path / "audit.jsonl"
    _chain(path, 3)
    entries = audit.read_entries(path)
    previous = audit.GENESIS
    for entry in entries:
        entry["response"] = "rewritten"
        entry["prev_hash"] = previous
        entry["hash"] = audit.entry_hash(entry)
        previous = entry["hash"]
    path.write_text(
        "\n".join(json.dumps(entry, ensure_ascii=False, sort_keys=True) for entry in entries) + "\n",
        encoding="utf-8",
    )
    assert audit.verify_entries(entries) == (True, 0, None)
    count, error = audit.verify_file(path)
    assert error is not None
    assert "checkpoint" in error


def test_a_rolled_back_checkpoint_is_detected(tmp_path):
    path = tmp_path / "audit.jsonl"
    _chain(path, 2)
    old = audit.checkpoint_path(path).read_text(encoding="utf-8")
    _chain(path, 1)
    assert audit.verify_file(path)[1] is None
    audit.checkpoint_path(path).write_text(old, encoding="utf-8")
    count, error = audit.verify_file(path)
    assert error is not None
    assert "checkpoint" in error


def test_a_missing_checkpoint_is_an_error(tmp_path):
    path = tmp_path / "audit.jsonl"
    _chain(path, 2)
    audit.checkpoint_path(path).unlink()
    count, error = audit.verify_file(path)
    assert error is not None
    assert "checkpoint" in error


def test_an_invalid_tail_refuses_the_append(tmp_path):
    path = tmp_path / "audit.jsonl"
    _chain(path, 2)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("{not json\n")
    with pytest.raises(audit.AuditError):
        audit.append_entry(path, _payload(3))
    assert audit.verify_file(path)[1] is not None


def test_a_foreign_log_identity_is_detected(tmp_path):
    path = tmp_path / "audit.jsonl"
    _chain(path, 3)
    lines = path.read_text(encoding="utf-8").splitlines()
    entry = json.loads(lines[2])
    entry["log_id"] = "another-log"
    entry["hash"] = audit.entry_hash(entry)
    lines[2] = json.dumps(entry, ensure_ascii=False, sort_keys=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert audit.verify_file(path)[1] is not None


def test_excerpt_digests_are_sha256_of_the_excerpt():
    digest = audit.excerpt_digest("Afinacion de bicicleta: 380 pesos.")
    assert len(digest) == 64
    assert digest == audit.excerpt_digest("Afinacion de bicicleta: 380 pesos.")


def test_redact_removes_the_secret_from_every_field():
    value = {
        "question": "el token es secret-1",
        "args": {"q": ["secret-1", {"deep": "secret-1 tail"}]},
        "other": 3,
    }
    redacted = audit.redact(value, "secret-1")
    assert "secret-1" not in json.dumps(redacted)
    assert redacted["other"] == 3


def test_the_audit_key_is_not_the_bearer(tmp_path, monkeypatch):
    key_path = tmp_path / "same.key"
    monkeypatch.setenv("CITED_MCP_TOKEN", "shared-secret")
    key_path.write_text("shared-secret", encoding="utf-8")
    with pytest.raises(audit.AuditError):
        audit.audit_key(str(key_path))


CHILD = textwrap.dedent(
    """
    import sys
    from hermes_cited import audit
    path = sys.argv[1]
    name = sys.argv[2]
    for index in range(5):
        payload = {
            "ts": "2026-10-10T00:00:00Z",
            "platform": "cli",
            "session": name,
            "turn_id": "{0}-{1}".format(name, index),
            "user": "",
            "mode": "cited",
            "question": "q",
            "tool_calls": [],
            "sources": [],
            "response": "r",
            "verifier": {"applied": True, "ok": True, "ungrounded": []},
        }
        audit.append_entry(path, payload)
    """
)


def test_concurrent_processes_keep_one_chain(tmp_path):
    """M3: several processes, an exclusive lock, an exact count and unique turns."""
    path = tmp_path / "audit.jsonl"
    environment = {**os.environ, "PYTHONPATH": str(REPO)}
    children = [
        subprocess.Popen(
            [sys.executable, "-c", CHILD, str(path), "p{0}".format(number)],
            cwd=str(REPO),
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for number in range(4)
    ]
    codes = []
    errors = []
    for child in children:
        out, err = child.communicate(timeout=120)
        codes.append(child.returncode)
        errors.append(err.decode("utf-8", "replace"))
    assert codes == [0, 0, 0, 0], errors
    entries = audit.read_entries(path)
    assert len(entries) == 20
    assert [entry["seq"] for entry in entries] == list(range(1, 21))
    assert len({entry["turn_id"] for entry in entries}) == 20
    count, error = audit.verify_file(path)
    assert error is None
    assert count == 20
