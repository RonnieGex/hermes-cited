"""The chain verifier as the command the mission names: python -m hermes_cited.verify_log (H5)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from hermes_cited import audit

REPO = Path(__file__).resolve().parents[1]


def _write_chain(path, entries=3):
    payload = {
        "ts": "2026-10-09T22:00:00Z",
        "platform": "cli",
        "session": "s",
        "user": "",
        "mode": "cited",
        "question": "q",
        "tool_calls": [],
        "response": "r",
        "verifier": {"applied": True, "ok": True, "ungrounded": []},
    }
    for _ in range(entries):
        audit.append_entry(path, payload)


def _run(*arguments):
    return subprocess.run(
        [sys.executable, "-m", "hermes_cited.verify_log", *arguments],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )


def test_the_module_reports_a_sound_chain_and_exits_zero(tmp_path):
    path = tmp_path / "audit.jsonl"
    _write_chain(path)
    result = _run(str(path))
    assert result.returncode == 0
    assert "3" in result.stdout


def test_the_module_names_the_first_broken_entry_and_exits_non_zero(tmp_path):
    path = tmp_path / "audit.jsonl"
    _write_chain(path)
    lines = path.read_text(encoding="utf-8").splitlines()
    entry = json.loads(lines[1])
    entry["response"] = "tampered"
    lines[1] = json.dumps(entry, ensure_ascii=False)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = _run(str(path))
    assert result.returncode != 0
    assert "2" in result.stdout + result.stderr


def test_a_missing_file_is_an_error(tmp_path):
    result = _run(str(tmp_path / "nope.jsonl"))
    assert result.returncode != 0
