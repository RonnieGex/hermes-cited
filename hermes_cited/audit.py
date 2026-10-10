"""The auditable hash-chained log of ``$HERMES_HOME/cited/audit.jsonl`` (H5).

One entry per response, in both modes. Every entry carries a monotonic ``seq``, the identity of the
log, ``prev_hash`` and ``hash``, where ``hash = sha256(prev_hash + canonical_json(entry without
hash))``. The append takes an exclusive inter-process lock over a lock file of the log, reads and
validates the tail, computes the hash, appends and flushes to disk, and then rewrites an
HMAC-authenticated checkpoint of the count, the final hash and the log identity. The key of that
checkpoint lives outside ``HERMES_HOME`` (``%APPDATA%\\Katalis\\hermes-cited\\audit.key`` by default)
and is never the bearer of Cited. The token is never written here.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from contextlib import contextmanager
from pathlib import Path

GENESIS = ""
CHECKPOINT_SUFFIX = ".checkpoint"
LOCK_SUFFIX = ".lock"
KEY_ENV = "CITED_AUDIT_KEY_PATH"
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


def key_path(key_path=None) -> Path:
    if key_path:
        return Path(key_path)
    configured = os.environ.get(KEY_ENV, "").strip()
    if configured:
        return Path(configured)
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(base) / "Katalis" / "hermes-cited" / "audit.key"


def audit_key(key_path_override=None) -> str:
    """The HMAC key of the checkpoint: outside ``HERMES_HOME``, created on the first write."""
    path = key_path(key_path_override)
    key = ""
    if path.exists():
        key = path.read_text(encoding="utf-8").strip()
    if not key:
        path.parent.mkdir(parents=True, exist_ok=True)
        candidate = secrets.token_hex(32)
        try:
            descriptor = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            key = path.read_text(encoding="utf-8").strip()
        except OSError as error:
            raise AuditError("the audit key at {0} could not be created: {1}".format(path, error))
        else:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(candidate)
            key = candidate
    if not key:
        raise AuditError("the audit key at {0} is empty".format(path))
    bearer = os.environ.get("CITED_MCP_TOKEN", "").strip()
    if bearer and key == bearer:
        raise AuditError("the audit key must not be the Cited bearer token")
    return key


def checkpoint_path(path) -> Path:
    return Path("{0}{1}".format(path, CHECKPOINT_SUFFIX))


def checkpoint_mac(checkpoint: dict, key: str) -> str:
    material = canonical_json(
        {
            "count": int(checkpoint.get("count", 0)),
            "final_hash": str(checkpoint.get("final_hash", "")),
            "log_id": str(checkpoint.get("log_id", "")),
        }
    )
    return hmac.new(key.encode("utf-8"), material.encode("utf-8"), hashlib.sha256).hexdigest()


def read_checkpoint(path):
    target = checkpoint_path(path)
    if not target.exists():
        return None
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    return data if isinstance(data, dict) else None


def write_checkpoint(path, count: int, final_hash: str, log_id: str, key_path_override=None) -> dict:
    key = audit_key(key_path_override)
    checkpoint = {"count": int(count), "final_hash": str(final_hash), "log_id": str(log_id)}
    checkpoint["mac"] = checkpoint_mac(checkpoint, key)
    target = checkpoint_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(checkpoint, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(str(temporary), str(target))
    return checkpoint


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
        handle.close()


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


def tail_of(entries) -> tuple:
    """``(count, prev_hash, log_id)`` of a validated tail, or an ``AuditError``."""
    if not entries:
        return 0, GENESIS, ""
    for index, entry in enumerate(entries, start=1):
        validate_entry(entry)
        if entry["seq"] != index:
            raise AuditError(
                "entry {0} has seq {1} instead of {0}: the chain was cut or reordered".format(
                    index, entry["seq"]
                )
            )
        if entry["log_id"] != entries[0]["log_id"]:
            raise AuditError("entry {0} belongs to another log identity".format(index))
    last = entries[-1]
    if entry_hash(last) != last["hash"]:
        raise AuditError("entry {0} was altered: its hash does not match its content".format(len(entries)))
    previous = entries[-2]["hash"] if len(entries) > 1 else GENESIS
    if last["prev_hash"] != previous:
        raise AuditError("entry {0} does not continue the chain: its prev_hash is not the hash of entry {1}".format(
            len(entries), len(entries) - 1
        ))
    return len(entries), last["hash"], entries[0]["log_id"]


def append_entry(path, payload: dict, key_path_override=None) -> dict:
    """Append one entry to the chain and return it, with its ``prev_hash``, ``seq`` and ``hash``."""
    log = Path(path)
    log.parent.mkdir(parents=True, exist_ok=True)
    lock_file = Path("{0}{1}".format(log, LOCK_SUFFIX))
    with _locked(lock_file):
        count, previous, log_id = tail_of(read_entries(log))
        entry = dict(payload)
        entry.pop("hash", None)
        entry["seq"] = count + 1
        entry["log_id"] = log_id or secrets.token_hex(16)
        entry["prev_hash"] = previous
        entry["hash"] = ""
        validate_entry(entry)
        entry["hash"] = entry_hash(entry)
        with open(log, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        write_checkpoint(log, entry["seq"], entry["hash"], entry["log_id"], key_path_override)
    return entry


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


def verify_file(path, key_path_override=None) -> tuple:
    """Return ``(count, error)`` for one log file; ``error`` is ``None`` when everything verifies.

    The chain alone only proves internal consistency. The verdict also requires the authenticated
    checkpoint, so a removed entry, a cut suffix, a rewritten and recomputed chain or a log that
    does not match its checkpoint are all detected.
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
    checkpoint = read_checkpoint(log)
    if checkpoint is None:
        return len(entries), (
            "the audit log has no authenticated checkpoint at {0}: without it, an entry removed "
            "from the end cannot be told apart from a log that never had it".format(checkpoint_path(log))
        )
    try:
        key = audit_key(key_path_override)
    except AuditError as error:
        return len(entries), str(error)
    if checkpoint.get("mac") != checkpoint_mac(checkpoint, key):
        return len(entries), "the checkpoint of {0} is not authentic".format(log)
    if checkpoint.get("log_id") != entries[0]["log_id"]:
        return len(entries), "the checkpoint names another log identity than the entries"
    if checkpoint.get("count") != len(entries) or checkpoint.get("final_hash") != entries[-1]["hash"]:
        return len(entries), (
            "the log does not match its checkpoint: the checkpoint holds {0} entries ending at {1}, "
            "the log holds {2} ending at {3}".format(
                checkpoint.get("count"),
                str(checkpoint.get("final_hash"))[:12],
                len(entries),
                str(entries[-1]["hash"])[:12],
            )
        )
    return len(entries), None


def last_hash(path) -> str:
    """The hash of the validated last entry, or genesis when there is none; raises when broken."""
    log = Path(path)
    if not log.exists():
        return GENESIS
    count, previous, _ = tail_of(read_entries(log))
    return previous if count else GENESIS
