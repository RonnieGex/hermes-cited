"""The local consistency record of delivered answers (H5, D9).

One JSONL line per delivered response, in both modes, at ``$HERMES_HOME/cited/audit.jsonl``. Every entry
carries a monotonic ``seq``, the identity of the log, ``prev_hash`` and ``hash``, where
``hash = sha256(prev_hash + canonical_json(entry without hash))``. The append holds an exclusive
inter-process lock over a lock file of the log and, before writing one byte, reads the whole chain and
validates every schema, ``seq``, link and hash. Any mismatch refuses the append and leaves the file
untouched: an append never restarts the chain from genesis.

Round 4 (D9) retired the local custody. There is no key, no checkpoint, no high-water mark and no file
outside ``HERMES_HOME`` any more, because whoever controls the PC can revert any of them, and each round
opened a new hole in Windows. What this module records is what was really delivered after composing; it is
for reviewing and reproducing an answer, and it is **not** tamper-proof against whoever controls the
machine. Audited custody belongs to the server side (Cited Ledger). ``git log`` keeps the custody code of
rounds 2 and 3 if it is ever wanted back.

Round 5 (M-R4-1) publishes one entry by writing the validated published text plus the new row into a
temporary file of the same directory, completing write, flush, ``fsync`` and close there, and only then
replacing the published file atomically. A failure of any earlier stage leaves the published chain
byte-identical, and the replacement is the last fallible step of publication, so its success can never be
turned into a refusal. What remains outside the record is the interruption of the process **between**
publishing the row and delivering the answer: the row exists and nothing was shown. That is declared, not
promised away.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

GENESIS = ""
LOCK_SUFFIX = ".lock"
CHAIN_FIELDS = ("seq", "log_id", "prev_hash", "hash")

REQUIRED_FIELDS = (
    "ts",
    "seq",
    "log_id",
    "platform",
    "session",
    "turn_id",
    "user",
    "mode",
    "question",
    "tool_calls",
    "response",
    "verifier",
    "prev_hash",
    "hash",
)


class AuditError(Exception):
    """The log cannot be trusted or cannot be written; the sentence says which."""


def canonical_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hashable(entry: dict) -> dict:
    return {key: value for key, value in entry.items() if key != "hash"}


def entry_hash(entry: dict) -> str:
    material = "{0}{1}".format(entry.get("prev_hash", GENESIS), canonical_json(_hashable(entry)))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def excerpt_digest(excerpt: str) -> str:
    return hashlib.sha256(str(excerpt).encode("utf-8")).hexdigest()


def redact(value, secret: str):
    """Recursively replace *secret* in every string of a value, for the audit entry (H6)."""
    if not secret:
        return value
    if isinstance(value, str):
        return value.replace(secret, "<token>")
    if isinstance(value, dict):
        return {redact(key, secret): redact(item, secret) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item, secret) for item in value]
    return value


def validate_entry(entry: dict) -> None:
    """Refuse an entry that does not carry the schema, before it is hashed or accepted."""
    if not isinstance(entry, dict):
        raise AuditError("the audit entry is not an object")
    missing = [field for field in REQUIRED_FIELDS if field not in entry]
    if missing:
        raise AuditError("the audit entry is missing: {0}".format(", ".join(missing)))
    if not isinstance(entry.get("seq"), int) or entry["seq"] < 1:
        raise AuditError("the audit entry has no positive seq")
    if not isinstance(entry.get("log_id"), str) or not entry["log_id"]:
        raise AuditError("the audit entry has no log identity")
    if not isinstance(entry.get("tool_calls"), list):
        raise AuditError("the audit entry has no tool_calls list")
    if not isinstance(entry.get("verifier"), dict):
        raise AuditError("the audit entry has no verifier object")
    if not isinstance(entry.get("prev_hash"), str) or not isinstance(entry.get("hash"), str):
        raise AuditError("the audit entry has no chain fields")


@contextmanager
def _locked(lock_file: Path):
    """An exclusive inter-process lock, so two writers never read the same tail (M3)."""
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    handle = open(lock_file, "a+b")
    try:
        if os.name == "nt":
            import msvcrt

            while True:
                try:
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                    break
                except OSError:
                    time.sleep(0.05)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        try:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        try:
            handle.close()
        except OSError:
            pass


def read_entries(path) -> list:
    """Every entry of the log. An unreadable line is an ``AuditError``, never a silent skip."""
    log = Path(path)
    if not log.exists():
        return []
    entries = []
    with open(log, "r", encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                raise AuditError("entry {0} of {1} is not JSON".format(number, log))
            entries.append(entry)
    return entries


def verify_entries(entries) -> tuple:
    """Return ``(ok, index, error)``: the first broken 1-based entry, or ``(True, 0, None)``."""
    previous = GENESIS
    log_id = None
    for index, entry in enumerate(entries, start=1):
        try:
            validate_entry(entry)
        except AuditError as error:
            return False, index, "entry {0}: {1}".format(index, error)
        if log_id is None:
            log_id = entry["log_id"]
        elif entry["log_id"] != log_id:
            return False, index, "entry {0} belongs to another log identity".format(index)
        if entry.get("seq") != index:
            return False, index, "entry {0} has seq {1}: the chain was cut or reordered".format(
                index, entry.get("seq")
            )
        if entry.get("prev_hash", GENESIS) != previous:
            return False, index, "entry {0} does not continue the chain: its prev_hash is not the hash of entry {1}".format(
                index, index - 1
            )
        if entry.get("hash") != entry_hash(entry):
            return False, index, "entry {0} was altered: its hash does not match its content".format(index)
        previous = entry.get("hash")
    return True, 0, None


def validate_chain(entries) -> None:
    """Raise the sentence of the first broken entry; the append calls this before writing."""
    ok, _index, error = verify_entries(entries)
    if not ok:
        raise AuditError(error)


def tail_of(entries) -> tuple:
    """``(count, prev_hash, log_id)`` of a validated tail, or an ``AuditError``."""
    validate_chain(entries)
    if not entries:
        return 0, GENESIS, ""
    return len(entries), entries[-1]["hash"], entries[0]["log_id"]


def _serialize(entry: dict) -> str:
    return json.dumps(entry, ensure_ascii=False, sort_keys=True)


def _published_text(log: Path) -> str:
    """The bytes of the published log, with the final line break the append needs."""
    if not log.exists():
        return ""
    text = log.read_text(encoding="utf-8")
    if text and not text.endswith("\n"):
        text += "\n"
    return text


def _create_temp(log: Path) -> Path:
    """A temporary file of the same directory, so the replacement is a rename and never a copy."""
    handle, name = tempfile.mkstemp(dir=str(log.parent), prefix=log.name + ".", suffix=".tmp")
    os.close(handle)
    return Path(name)


def _open_temp(path):
    """The write handle of a prepared temporary file; a seam for the failure fixtures of M-R4-1."""
    return open(path, "w", encoding="utf-8", newline="\n")


def _write_temp_file(path, text: str) -> None:
    """Write, flush, ``fsync`` and close the prepared file; any failure propagates (M-R4-1)."""
    handle = _open_temp(path)
    try:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    finally:
        handle.close()


def _discard(path) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


def _publish(temp, log: Path) -> None:
    """The last publishing operation: an atomic replacement of the published file (M-R4-1)."""
    os.replace(str(temp), str(log))


def _publish_replacement(log: Path, text: str) -> None:
    temp = None
    try:
        temp = _create_temp(log)
        _write_temp_file(temp, text)
        _publish(temp, log)
        temp = None
    finally:
        if temp is not None:
            _discard(temp)


def append_entry(path, payload: dict, key_path_override=None) -> dict:
    """Append one entry to the chain, or refuse without touching the log.

    Under the inter-process lock the whole chain is validated and the new file is prepared outside the
    published one; only then is it replaced atomically. ``key_path_override`` is accepted and ignored so
    that the callers and the command lines of rounds 2 and 3 keep working; round 4 has no key.
    """
    log = Path(path)
    log.parent.mkdir(parents=True, exist_ok=True)
    lock_file = Path("{0}{1}".format(log, LOCK_SUFFIX))
    with _locked(lock_file):
        entries = read_entries(log)
        validate_chain(entries)
        count = len(entries)
        previous = entries[-1]["hash"] if entries else GENESIS
        log_id = entries[0]["log_id"] if entries else secrets.token_hex(16)
        entry = dict(payload)
        entry.pop("hash", None)
        entry["seq"] = count + 1
        entry["log_id"] = log_id
        entry["prev_hash"] = previous
        entry["hash"] = ""
        validate_entry(entry)
        entry["hash"] = entry_hash(entry)
        text = "{0}{1}\n".format(_published_text(log), _serialize(entry))
        _publish_replacement(log, text)
    return entry


def verify_file(path, key_path_override=None) -> tuple:
    """Return ``(count, error)`` for one log file; ``error`` is ``None`` when the chain is consistent.

    This checks the **internal consistency** of the chain: every schema, every ``seq``, every link and
    every hash. It is not a custody check and it never claims to be one: whoever rewrites the file and
    recomputes the chain produces a consistent file, which is exactly the limit the README states.
    """
    log = Path(path)
    if not log.exists():
        return 0, "the audit log does not exist: {0}".format(log)
    try:
        entries = read_entries(log)
    except AuditError as error:
        return 0, str(error)
    if not entries:
        return 0, "the audit log is empty: {0}".format(log)
    ok, index, error = verify_entries(entries)
    if not ok:
        return index - 1, error
    return len(entries), None


def last_hash(path) -> str:
    """The hash of the validated last entry, or genesis when there is none; raises when broken."""
    log = Path(path)
    if not log.exists():
        return GENESIS
    entries = read_entries(log)
    validate_chain(entries)
    return entries[-1]["hash"] if entries else GENESIS
