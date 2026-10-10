"""The hash-chained audit log and its verifier (H5, H6)."""

from __future__ import annotations

import json

from hermes_cited import audit


def _payload(index):
    return {
        "ts": "2026-10-09T22:00:0{0}Z".format(index),
        "platform": "cli",
        "session": "session-1",
        "user": "",
        "mode": "cited",
        "question": "cuanto cuesta la afinacion",
        "tool_calls": [
            {
                "tool": "cited_search",
                "args": {"query": "precio"},
                "status": "ok",
                "excerpt_sha256": ["a" * 64],
            }
        ],
        "response": "380 pesos [1].",
        "verifier": {"applied": True, "ok": True, "ungrounded": []},
    }


def test_the_first_entry_links_to_the_genesis(tmp_path):
    path = tmp_path / "audit.jsonl"
    entry = audit.append_entry(path, _payload(1))
    assert entry["prev_hash"] == audit.GENESIS
    assert len(entry["hash"]) == 64


def test_each_entry_links_to_the_previous_one(tmp_path):
    path = tmp_path / "audit.jsonl"
    first = audit.append_entry(path, _payload(1))
    second = audit.append_entry(path, _payload(2))
    assert second["prev_hash"] == first["hash"]


def test_a_fresh_chain_verifies(tmp_path):
    path = tmp_path / "audit.jsonl"
    for index in range(3):
        audit.append_entry(path, _payload(index))
    count, error = audit.verify_file(path)
    assert error is None
    assert count == 3


def test_every_required_field_is_written(tmp_path):
    path = tmp_path / "audit.jsonl"
    entry = audit.append_entry(path, _payload(1))
    for field in (
        "ts",
        "platform",
        "session",
        "user",
        "mode",
        "question",
        "tool_calls",
        "response",
        "verifier",
        "prev_hash",
        "hash",
    ):
        assert field in entry
    assert entry["tool_calls"][0]["args"] == {"query": "precio"}
    assert entry["tool_calls"][0]["excerpt_sha256"][0] == "a" * 64


def test_an_altered_entry_is_detected(tmp_path):
    path = tmp_path / "audit.jsonl"
    for index in range(3):
        audit.append_entry(path, _payload(index))
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
    for index in range(3):
        audit.append_entry(path, _payload(index))
    lines = path.read_text(encoding="utf-8").splitlines()
    del lines[1]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    count, error = audit.verify_file(path)
    assert error is not None


def test_a_reordered_entry_is_detected(tmp_path):
    path = tmp_path / "audit.jsonl"
    for index in range(3):
        audit.append_entry(path, _payload(index))
    lines = path.read_text(encoding="utf-8").splitlines()
    lines[1], lines[2] = lines[2], lines[1]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    count, error = audit.verify_file(path)
    assert error is not None


def test_a_truncated_chain_is_detected(tmp_path):
    path = tmp_path / "audit.jsonl"
    for index in range(3):
        audit.append_entry(path, _payload(index))
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


def test_excerpt_digests_are_sha256_of_the_excerpt():
    digest = audit.excerpt_digest("Afinacion de bicicleta: 380 pesos.")
    assert len(digest) == 64
    assert digest == audit.excerpt_digest("Afinacion de bicicleta: 380 pesos.")
