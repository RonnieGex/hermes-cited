"""The auditable hash-chained log of ``$HERMES_HOME/cited/audit.jsonl`` (H5).

One entry per response, in both modes. Every entry carries ``prev_hash`` and ``hash``, where
``hash = sha256(prev_hash + canonical_json(entry without hash))``: changing, removing or
reordering an entry breaks the chain and its verifier says which entry broke it. The token is
never written here.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

GENESIS = ""

REQUIRED_FIELDS = (
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
)


def canonical_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hashable(entry: dict) -> dict:
    return {key: value for key, value in entry.items() if key != "hash"}


def entry_hash(entry: dict) -> str:
    material = "{0}{1}".format(entry.get("prev_hash", GENESIS), canonical_json(_hashable(entry)))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def excerpt_digest(excerpt: str) -> str:
    return hashlib.sha256(str(excerpt).encode("utf-8")).hexdigest()


def last_hash(path) -> str:
    """The hash of the last entry of a log, or the genesis value when there is none."""
    log = Path(path)
    if not log.exists():
        return GENESIS
    last = ""
    with open(log, "r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                last = line
    if not last:
        return GENESIS
    try:
        entry = json.loads(last)
    except ValueError:
        return GENESIS
    value = entry.get("hash") if isinstance(entry, dict) else None
    return value if isinstance(value, str) and value else GENESIS


def append_entry(path, payload: dict) -> dict:
    """Append one entry to the chain and return it, with its ``prev_hash`` and ``hash``."""
    log = Path(path)
    log.parent.mkdir(parents=True, exist_ok=True)
    entry = dict(payload)
    entry["prev_hash"] = last_hash(log)
    entry["hash"] = ""
    entry["hash"] = entry_hash(entry)
    with open(log, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    return entry


def read_entries(path) -> list:
    log = Path(path)
    if not log.exists():
        return []
    entries = []
    with open(log, "r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                entries.append(json.loads(line))
    return entries


def verify_entries(entries) -> tuple:
    """Return ``(ok, index, error)``: the first broken 1-based entry, or ``(True, 0, None)``."""
    previous = GENESIS
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            return False, index, "entry {0} is not an object".format(index)
        if entry.get("prev_hash", GENESIS) != previous:
            return False, index, "entry {0} does not continue the chain: its prev_hash is not the hash of entry {1}".format(
                index, index - 1
            )
        if entry.get("hash") != entry_hash(entry):
            return False, index, "entry {0} was altered: its hash does not match its content".format(index)
        previous = entry.get("hash")
    return True, 0, None


def verify_file(path) -> tuple:
    """Return ``(count, error)`` for one log file; ``error`` is ``None`` when the chain verifies."""
    log = Path(path)
    if not log.exists():
        return 0, "the audit log does not exist: {0}".format(log)
    lines = []
    with open(log, "r", encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                return len(lines), "entry {0} is not JSON".format(number)
            lines.append(entry)
    if not lines:
        return 0, "the audit log is empty: {0}".format(log)
    ok, index, error = verify_entries(lines)
    if not ok:
        return index - 1, error
    return len(lines), None
