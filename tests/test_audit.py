"""The local consistency record: the chained log, its append and its verifier (H5, M3, D9).

Round 4 (D9) retired the local custody, so these tests assert what the module really does: it chains every
delivered answer, it locks between processes, it validates the whole chain before writing one byte, and it
detects every change that breaks the chain. A chain rewritten and recomputed is consistent, and the tests
say so instead of pretending otherwise: the README states that limit in plain language.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap

import pytest

from hermes_cited import audit

REPO = __import__("pathlib").Path(__file__).resolve().parents[1]


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


def test_a_fresh_chain_is_consistent(tmp_path):
    path = tmp_path / "audit.jsonl"
    _chain(path, 3)
    count, error = audit.verify_file(path)
    assert error is None
    assert count == 3


def test_the_key_override_of_round_three_is_ignored(tmp_path):
    """D9: ``CITED_AUDIT_KEY_PATH`` has no effect any more and no file is created."""
    path = tmp_path / "audit.jsonl"
    key = tmp_path / "audit.key"
    audit.append_entry(path, _payload(1), key_path_override=str(key))
    assert audit.verify_file(path, key_path_override=str(key)) == (1, None)
    assert not key.exists()


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


def test_a_removed_middle_entry_is_detected(tmp_path):
    path = tmp_path / "audit.jsonl"
    _chain(path, 3)
    lines = path.read_text(encoding="utf-8").splitlines()
    del lines[1]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    count, error = audit.verify_file(path)
    assert error is not None
    assert "seq" in error


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


def test_a_removed_tail_is_consistent_and_the_limit_is_named(tmp_path):
    """D9: without a custody mark, a cut suffix leaves a shorter, internally consistent chain.

    The record says exactly that; it does not claim to detect it. This is the documented limit.
    """
    path = tmp_path / "audit.jsonl"
    _chain(path, 3)
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    assert audit.verify_file(path) == (2, None)


def test_a_cut_suffix_leaves_a_consistent_shorter_chain(tmp_path):
    path = tmp_path / "audit.jsonl"
    _chain(path, 5)
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(lines[:2]) + "\n", encoding="utf-8")
    assert audit.verify_file(path) == (2, None)


def test_a_rewritten_and_recomputed_chain_is_consistent_and_the_limit_is_named(tmp_path):
    """Whoever can rewrite the file can recompute its hashes: that is what D9 declares."""
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
    assert audit.verify_file(path) == (3, None)


def test_a_broken_chain_refuses_the_next_append(tmp_path):
    path = tmp_path / "audit.jsonl"
    _chain(path, 3)
    lines = path.read_text(encoding="utf-8").splitlines()
    del lines[1]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(audit.AuditError):
        audit.append_entry(path, _payload(9))
    assert path.read_bytes() == before


def test_an_invalid_tail_refuses_the_append(tmp_path):
    path = tmp_path / "audit.jsonl"
    _chain(path, 2)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("{not json\n")
    with pytest.raises(audit.AuditError):
        audit.append_entry(path, _payload(3))
    assert audit.verify_file(path)[1] is not None


def test_an_append_never_restarts_from_genesis(tmp_path):
    """B-R2-3: a chain that lost its tail is not adopted as a new one."""
    path = tmp_path / "audit.jsonl"
    _chain(path, 3)
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(lines[:1]) + "\n", encoding="utf-8")
    entry = audit.append_entry(path, _payload(9))
    assert entry["seq"] == 2


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


def test_no_custody_file_is_created_anywhere(tmp_path, monkeypatch):
    """D9: the append writes the log and its lock, and no key, checkpoint or custody record."""
    home = tmp_path / "hermes-home"
    (home / "cited").mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    path = home / "cited" / "audit.jsonl"
    audit.append_entry(path, _payload(1))
    names = sorted(item.name for item in path.parent.iterdir())
    assert names == ["audit.jsonl", "audit.jsonl.lock"]


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


def test_a_second_append_reuses_the_same_identity(tmp_path):
    path = tmp_path / "audit.jsonl"
    first = audit.append_entry(path, _payload(1))
    second = audit.append_entry(path, _payload(2))
    assert first["log_id"] == second["log_id"]


def test_last_hash_of_a_sound_chain_is_its_tail(tmp_path):
    path = tmp_path / "audit.jsonl"
    _chain(path, 3)
    assert audit.last_hash(path) == audit.read_entries(path)[-1]["hash"]


def test_last_hash_refuses_a_broken_chain(tmp_path):
    path = tmp_path / "audit.jsonl"
    _chain(path, 3)
    lines = path.read_text(encoding="utf-8").splitlines()
    del lines[1]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(audit.AuditError):
        audit.last_hash(path)
