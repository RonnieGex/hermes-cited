"""The auditable hash-chained log of ``$HERMES_HOME/cited/audit.jsonl`` (H5, D6).

One entry per response, in both modes. Every entry carries a monotonic ``seq``, the identity of the
log, ``prev_hash`` and ``hash``, where ``hash = sha256(prev_hash + canonical_json(entry without
hash))``. The append holds an exclusive inter-process lock over a lock file of the log and, before
writing one byte, reads the whole chain, validates every schema, ``seq``, link and hash, authenticates
the checkpoint and crosses the result with a high-water mark per identity kept next to the key, outside
``HERMES_HOME``. Any mismatch refuses the append and leaves the files untouched.

The append is a recoverable transaction: it records a MAC-authenticated *pending* row in custody,
appends the row, writes the checkpoint and updates custody. If a later step fails the row is rolled
back, so the recorded row is the response that was delivered; if the rollback itself cannot run, the
pending record authenticates completion on the next append. The key is created before the first row and
never by a read: a lost key fails closed and needs explicit recovery. ``CITED_AUDIT_KEY_PATH`` inside
``HERMES_HOME`` is rejected.
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
CUSTODY_SUFFIX = ".custody.json"
PENDING_SUFFIX = ".pending"
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


# --- custody: the key and the high-water mark, outside HERMES_HOME -------------------------------


def _home() -> Path:
    try:
        from hermes_constants import get_hermes_home

        return Path(get_hermes_home())
    except Exception:
        value = os.environ.get("HERMES_HOME", "").strip()
        return Path(value) if value else Path.home() / ".hermes"


def _inside(path, root) -> bool:
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except (ValueError, OSError):
        return False


def _reject_inside_home(path) -> None:
    home = _home()
    if home and _inside(path, home):
        raise AuditError(
            "the audit key must not live inside HERMES_HOME ({0} is under {1}); move "
            "{2} outside the home".format(path, home, KEY_ENV)
        )


def _reject_bearer(key: str) -> None:
    bearer = os.environ.get("CITED_MCP_TOKEN", "").strip()
    if bearer and key == bearer:
        raise AuditError("the audit key must not be the Cited bearer token")


def key_path(key_path=None) -> Path:
    if key_path:
        path = Path(key_path)
    else:
        configured = os.environ.get(KEY_ENV, "").strip()
        if configured:
            path = Path(configured)
        else:
            base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
            path = Path(base) / "Katalis" / "hermes-cited" / "audit.key"
    _reject_inside_home(path)
    return path


def load_existing_key(key_path_override=None) -> str:
    """Read the key of an existing identity. A read never creates or changes custody."""
    path = key_path(key_path_override)
    if not path.exists():
        raise AuditError(
            "the audit key at {0} is missing: restore it, or register a new identity explicitly".format(path)
        )
    key = path.read_text(encoding="utf-8").strip()
    if not key:
        raise AuditError("the audit key at {0} is empty".format(path))
    _reject_bearer(key)
    return key


def ensure_key(key_path_override=None) -> str:
    """Create the key before the first row of a new identity, or return the existing one."""
    path = key_path(key_path_override)
    if path.exists():
        return load_existing_key(key_path_override)
    path.parent.mkdir(parents=True, exist_ok=True)
    candidate = secrets.token_hex(32)
    try:
        descriptor = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return load_existing_key(key_path_override)
    except OSError as error:
        raise AuditError("the audit key at {0} could not be created: {1}".format(path, error))
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(candidate)
    return load_existing_key(key_path_override)


def audit_key(key_path_override=None) -> str:
    """Back-compat name of :func:`ensure_key` (create before the first row, never on a read)."""
    return ensure_key(key_path_override)


def registry_path(key_path_override=None) -> Path:
    key = key_path(key_path_override)
    return key.with_name(key.name + CUSTODY_SUFFIX)


def _identifier(path) -> str:
    return hashlib.sha256(str(Path(path).resolve()).encode("utf-8")).hexdigest()


def read_registry(key_path_override=None) -> dict:
    target = registry_path(key_path_override)
    if not target.exists():
        return {"paths": {}, "identities": {}}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (ValueError, OSError) as error:
        raise AuditError("the audit custody record at {0} is not readable: {1}".format(target, error))
    if not isinstance(data, dict):
        raise AuditError("the audit custody record at {0} is not an object".format(target))
    data.setdefault("paths", {})
    data.setdefault("identities", {})
    return data


def write_registry(registry: dict, key_path_override=None) -> None:
    target = registry_path(key_path_override)
    target.parent.mkdir(parents=True, exist_ok=True)
    _replace(target, json.dumps(registry, ensure_ascii=False, sort_keys=True) + "\n")


def _record_custody(log, log_id, count, final_hash, key_path_override=None) -> None:
    """The high-water mark per identity and the binding of this log path, under the custody lock."""
    lock_file = Path("{0}{1}".format(registry_path(key_path_override), LOCK_SUFFIX))
    with _locked(lock_file):
        registry = read_registry(key_path_override)
        identity = str(log_id)
        registry.setdefault("paths", {})[_identifier(log)] = {
            "log_id": identity,
            "count": int(count),
            "final_hash": str(final_hash),
            "path": str(Path(log)),
        }
        registry.setdefault("identities", {})[identity] = {
            "count": int(count),
            "final_hash": str(final_hash),
        }
        write_registry(registry, key_path_override)


# --- the pending transaction of one append --------------------------------------------------------


def pending_path(path, key_path_override=None) -> Path:
    key = key_path(key_path_override)
    return key.with_name("{0}{1}.{2}.json".format(key.name, PENDING_SUFFIX, _identifier(path)[:16]))


def pending_mac(payload: dict, key: str) -> str:
    return hmac.new(
        key.encode("utf-8"), canonical_json(payload).encode("utf-8"), hashlib.sha256
    ).hexdigest()


def write_pending(path, entry: dict, key_path_override=None) -> None:
    key = load_existing_key(key_path_override)
    payload = {"log": str(Path(path)), "entry": entry}
    record = {"payload": payload, "mac": pending_mac(payload, key)}
    _replace(pending_path(path, key_path_override), json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def read_pending(path, key_path_override=None):
    target = pending_path(path, key_path_override)
    if not target.exists():
        return None
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (ValueError, OSError) as error:
        raise AuditError("the pending audit transaction at {0} is not readable: {1}".format(target, error))
    return data if isinstance(data, dict) else None


def clear_pending(path, key_path_override=None) -> None:
    target = pending_path(path, key_path_override)
    try:
        if target.exists():
            target.unlink()
    except OSError:
        return


def _complete_pending(log, key: str, key_path_override=None) -> None:
    """Finish a transaction an earlier append left open, only with an authenticated pending row."""
    record = read_pending(log, key_path_override)
    if record is None:
        return
    payload = record.get("payload")
    mac = record.get("mac")
    if not isinstance(payload, dict) or not isinstance(mac, str) or not isinstance(payload.get("entry"), dict):
        raise AuditError("the pending audit transaction at {0} is malformed".format(pending_path(log, key_path_override)))
    if not hmac.compare_digest(mac, pending_mac(payload, key)):
        raise AuditError(
            "the pending audit transaction at {0} is not authentic".format(pending_path(log, key_path_override))
        )
    if str(payload.get("log")) != str(Path(log)):
        raise AuditError("the pending audit transaction belongs to another log")
    entry = payload["entry"]
    entries = read_entries(log)
    last = entries[-1] if entries else None
    if (
        last is not None
        and last.get("seq") == entry.get("seq")
        and last.get("hash") == entry.get("hash")
        and last.get("log_id") == entry.get("log_id")
    ):
        validate_entry(last)
        write_checkpoint(log, entry["seq"], entry["hash"], entry["log_id"], key_path_override)
        _record_custody(log, entry["log_id"], entry["seq"], entry["hash"], key_path_override)
    clear_pending(log, key_path_override)


# --- the checkpoint -------------------------------------------------------------------------------


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


def _replace(target: Path, body: str) -> None:
    temporary = target.with_name(target.name + ".tmp")
    with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(str(temporary), str(target))


def write_checkpoint(path, count: int, final_hash: str, log_id: str, key_path_override=None) -> dict:
    key = load_existing_key(key_path_override)
    checkpoint = {"count": int(count), "final_hash": str(final_hash), "log_id": str(log_id)}
    checkpoint["mac"] = checkpoint_mac(checkpoint, key)
    target = checkpoint_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    _replace(target, json.dumps(checkpoint, ensure_ascii=False, sort_keys=True) + "\n")
    return checkpoint


# --- the lock and the chain -----------------------------------------------------------------------


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


# --- the append -----------------------------------------------------------------------------------


def _preflight(log: Path, key: str, key_path_override=None) -> tuple:
    """Validate everything before a byte is written and return ``(count, prev_hash, log_id)``."""
    _complete_pending(log, key, key_path_override)
    entries = read_entries(log)
    registry = read_registry(key_path_override)
    state = (registry.get("paths") or {}).get(_identifier(log))
    if entries:
        _validate_chain(entries)
        identity = entries[0]["log_id"]
        final = entries[-1]["hash"]
        if state is None:
            raise AuditError(
                "the audit log {0} (identity {1}) is not registered in custody: refusing to adopt it".format(
                    log, identity
                )
            )
        if state.get("log_id") != identity:
            raise AuditError("the audit log identity {0} does not match its custody record".format(identity))
        checkpoint = _authenticate_checkpoint(log, entries, key)
        mark = (registry.get("identities") or {}).get(identity)
        if mark is None:
            raise AuditError("the audit identity {0} is not registered in custody".format(identity))
        mark_count = int(mark.get("count", 0))
        if len(entries) < mark_count:
            raise AuditError(
                "the audit log is below its high-water mark: the log holds {0} entries, custody holds "
                "{1}".format(len(entries), mark_count)
            )
        if len(entries) > mark_count:
            raise AuditError(
                "the audit log is ahead of its high-water mark: the log holds {0} entries, custody holds "
                "{1}".format(len(entries), mark_count)
            )
        if final != mark.get("final_hash"):
            raise AuditError("the audit log does not match its high-water mark")
        if checkpoint.get("count") != len(entries):
            raise AuditError("the checkpoint and the log disagree on the entry count")
        return len(entries), final, identity
    if state is not None:
        raise AuditError(
            "the audit log {0} disappeared while its identity {1} is registered in custody".format(
                log, state.get("log_id")
            )
        )
    return 0, GENESIS, ""


def _validate_chain(entries) -> None:
    ok, index, error = verify_entries(entries)
    if not ok:
        raise AuditError(error)


def _authenticate_checkpoint(log: Path, entries, key: str) -> dict:
    checkpoint = read_checkpoint(log)
    if checkpoint is None:
        raise AuditError(
            "the audit log has no authenticated checkpoint at {0}: refusing the append".format(
                checkpoint_path(log)
            )
        )
    if checkpoint.get("mac") != checkpoint_mac(checkpoint, key):
        raise AuditError("the checkpoint of {0} is not authentic".format(log))
    if checkpoint.get("log_id") != entries[0]["log_id"]:
        raise AuditError("the checkpoint names another log identity than the entries")
    if checkpoint.get("count") != len(entries) or checkpoint.get("final_hash") != entries[-1]["hash"]:
        raise AuditError(
            "the log does not match its checkpoint: the checkpoint holds {0} entries ending at {1}, the "
            "log holds {2} ending at {3}".format(
                checkpoint.get("count"),
                str(checkpoint.get("final_hash"))[:12],
                len(entries),
                str(entries[-1]["hash"])[:12],
            )
        )
    return checkpoint


def _append_line(log: Path, entry: dict) -> None:
    with open(log, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _truncate(log: Path, size: int) -> None:
    with open(log, "r+b") as handle:
        handle.truncate(size)
        handle.flush()
        os.fsync(handle.fileno())


def append_entry(path, payload: dict, key_path_override=None) -> dict:
    """Append one entry to the chain, or refuse without touching the log and its custody."""
    log = Path(path)
    log.parent.mkdir(parents=True, exist_ok=True)
    lock_file = Path("{0}{1}".format(log, LOCK_SUFFIX))
    with _locked(lock_file):
        entries = read_entries(log)
        registry = read_registry(key_path_override)
        state = (registry.get("paths") or {}).get(_identifier(log))
        genesis = not entries and state is None
        probe = dict(payload)
        probe.pop("hash", None)
        probe.update({"seq": 1, "log_id": secrets.token_hex(16), "prev_hash": GENESIS, "hash": ""})
        if genesis:
            validate_entry(probe)
            key = ensure_key(key_path_override)
        else:
            key = load_existing_key(key_path_override)
        count, previous, log_id = _preflight(log, key, key_path_override)
        entry = dict(payload)
        entry.pop("hash", None)
        entry["seq"] = count + 1
        entry["log_id"] = log_id or secrets.token_hex(16)
        entry["prev_hash"] = previous
        entry["hash"] = ""
        validate_entry(entry)
        entry["hash"] = entry_hash(entry)
        size_before = log.stat().st_size if log.exists() else 0
        write_pending(log, entry, key_path_override)
        appended = False
        try:
            _append_line(log, entry)
            appended = True
            write_checkpoint(log, entry["seq"], entry["hash"], entry["log_id"], key_path_override)
            _record_custody(log, entry["log_id"], entry["seq"], entry["hash"], key_path_override)
        except BaseException:
            rolled_back = True
            if appended:
                try:
                    _truncate(log, size_before)
                except OSError:
                    rolled_back = False
            if rolled_back:
                clear_pending(log, key_path_override)
            raise
        clear_pending(log, key_path_override)
    return entry


def verify_file(path, key_path_override=None) -> tuple:
    """Return ``(count, error)`` for one log file; ``error`` is ``None`` when everything verifies.

    The chain alone only proves internal consistency. The verdict also requires the authenticated
    checkpoint and the custody high-water mark, so a removed entry, a cut suffix, a rewritten and
    recomputed chain, a rolled-back checkpoint, a rollback of both files and an unregistered chain are
    all detected. A read never creates or changes the key.
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
    try:
        key = load_existing_key(key_path_override)
        registry = read_registry(key_path_override)
    except AuditError as error:
        return len(entries), str(error)
    checkpoint = read_checkpoint(log)
    if checkpoint is None:
        return len(entries), (
            "the audit log has no authenticated checkpoint at {0}: without it, an entry removed "
            "from the end cannot be told apart from a log that never had it".format(checkpoint_path(log))
        )
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
    identity = entries[0]["log_id"]
    state = (registry.get("paths") or {}).get(_identifier(log))
    mark = (registry.get("identities") or {}).get(identity)
    if state is None and mark is None:
        return len(entries), "the audit log is not registered in custody: {0}".format(log)
    if state is not None and state.get("log_id") != identity:
        return len(entries), "the audit log identity does not match its custody record"
    if mark is not None:
        mark_count = int(mark.get("count", 0))
        if len(entries) < mark_count:
            return len(entries), (
                "the audit log is below its high-water mark: the log holds {0} entries, custody holds "
                "{1}".format(len(entries), mark_count)
            )
        if len(entries) > mark_count:
            return len(entries), (
                "the audit log is ahead of its high-water mark: the log holds {0} entries, custody holds "
                "{1}".format(len(entries), mark_count)
            )
        if entries[-1]["hash"] != mark.get("final_hash"):
            return len(entries), "the audit log does not match its high-water mark"
    return len(entries), None


def last_hash(path) -> str:
    """The hash of the validated last entry, or genesis when there is none; raises when broken."""
    log = Path(path)
    if not log.exists():
        return GENESIS
    count, previous, _ = tail_of(read_entries(log))
    return previous if count else GENESIS
