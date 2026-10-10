"""Permanent regressions of the fourth review: the consistency record after a disk failure.

R4 M-R4-1. The append publishes the validated chain plus the new row by writing a temporary file of
the same directory, completing write, flush, fsync and close, and only then replacing the published
file atomically. A failure of any earlier stage leaves the published chain byte-identical and the
answer is the fixed operational refusal; a failure of the replacement is the last fallible step, so
its success can no longer be turned into a refusal.
"""

from __future__ import annotations

import json

import pytest

from hermes_cited import audit, plugin, verifier

GROUNDED = "- Afinacion de bicicleta: 380 pesos."
QUIET = (
    "streaming:\n  enabled: false\ndisplay:\n  streaming: false\n  interim_assistant_messages: false\n"
)


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
        self.tools[name] = {"handler": handler}

    def register_hook(self, hook_name, callback):
        self.hooks.setdefault(hook_name, []).append(callback)

    def register_command(self, name, handler, description="", args_hint="", argument_mode=None):
        self.commands[name] = handler

    def register_skill(self, name, path, description="", frontmatter=None):
        self.skills[name] = {"path": path}


def payload(index):
    return {
        "ts": "2026-10-10T00:00:0{0}Z".format(index),
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


def chain(path, entries=2):
    for index in range(entries):
        audit.append_entry(path, payload(index))
    return path


def failure(*args, **kwargs):
    raise OSError("synthetic disk failure")


class ExplodingHandle:
    """A handle whose named stage fails, so write, flush and close are attacked one at a time."""

    def __init__(self, handle, stage):
        self.handle = handle
        self.stage = stage

    def write(self, text):
        if self.stage == "write":
            raise OSError("synthetic write failure")
        return self.handle.write(text)

    def flush(self):
        if self.stage == "flush":
            raise OSError("synthetic flush failure")
        return self.handle.flush()

    def fileno(self):
        return self.handle.fileno()

    def close(self):
        if self.stage == "close":
            raise OSError("synthetic close failure")
        return self.handle.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def explode_at_open(stage, monkeypatch):
    original = audit._open_temp

    def opener(path):
        return ExplodingHandle(original(path), stage)

    monkeypatch.setattr(audit, "_open_temp", opener)


@pytest.mark.parametrize("stage", ["write", "flush", "fsync", "close", "replace"])
def test_m_r4_1_every_stage_of_the_append_leaves_the_published_bytes(tmp_path, monkeypatch, stage):
    """R4 M-R4-1: a failure before the replacement keeps the chain intact and the next append works."""
    path = chain(tmp_path / "audit.jsonl", 2)
    before = path.read_bytes()
    if stage == "replace":
        monkeypatch.setattr(audit.os, "replace", failure)
    elif stage == "fsync":
        monkeypatch.setattr(audit.os, "fsync", failure)
    else:
        explode_at_open(stage, monkeypatch)
    with pytest.raises(OSError):
        audit.append_entry(path, payload(9))
    assert path.read_bytes() == before
    count, error = audit.verify_file(path)
    assert error is None and count == 2
    monkeypatch.undo()
    audit.append_entry(path, payload(10))
    count, error = audit.verify_file(path)
    assert error is None and count == 3
    assert path.read_bytes().startswith(before)


def test_m_r4_1_a_successful_append_leaves_no_temporary_file(tmp_path):
    """R4 M-R4-1: the prepared file is the published one after the replacement."""
    path = chain(tmp_path / "audit.jsonl", 1)
    audit.append_entry(path, payload(2))
    assert [item.name for item in tmp_path.iterdir() if item.name.endswith(".tmp")] == []


def test_m_r4_1_the_published_bytes_are_not_re_serialized(tmp_path):
    """R4 M-R4-1: the new file is the published bytes plus the new line, byte for byte."""
    path = chain(tmp_path / "audit.jsonl", 2)
    before = path.read_bytes()
    audit.append_entry(path, payload(3))
    after = path.read_bytes()
    assert after.startswith(before)
    assert after[len(before):].endswith(b"\n")


def test_m_r4_1_a_disk_sync_failure_is_the_refusal_and_writes_no_row(
    tmp_path, monkeypatch, hermes_home, cited_env
):
    """R4 M-R4-1: the reproduction of the review, at the plugin level.

    The delivered text is the fixed operational refusal, no row was published, and the next normal
    append is accepted.
    """
    monkeypatch.setenv("CITED_DEFAULT_MODE", "cited")
    (hermes_home / "config.yaml").write_text(QUIET, encoding="utf-8")
    context = FakeContext()
    plugin.register(context)
    pre = context.hooks["pre_llm_call"][0]
    post = context.hooks["post_tool_call"][0]
    quote = context.tools["cited_quote"]["handler"]
    transform = context.hooks["transform_llm_output"][0]
    envelope = json.dumps({
        "cited_tool": "cited_search",
        "query": "afinacion",
        "text": "t",
        "passages": [{"n": 1, "document": "d.md", "heading": "H", "position": 0, "excerpt": GROUNDED}],
    })
    pre(session_id="s1", turn_id="t1", user_message="q", platform="cli")
    post(tool_name="cited_search", args={"query": "q"}, result=envelope, session_id="s1", turn_id="t1", status="ok")
    assert quote({"passage": "P1", "lines": [1]}, session_id="s1", turn_id="t1") == GROUNDED
    original = audit.os.fsync
    monkeypatch.setattr(audit.os, "fsync", failure)
    final = transform(response_text="MODEL_LEAK_999", session_id="s1", turn_id="t1", platform="cli")
    assert verifier.SEAL not in final
    assert "CITED-" in final
    assert "MODEL_LEAK_999" not in final
    assert not (hermes_home / "cited" / "audit.jsonl").exists()
    monkeypatch.setattr(audit.os, "fsync", original)
    pre(session_id="s1", turn_id="t2", user_message="q", platform="cli")
    post(tool_name="cited_search", args={"query": "q"}, result=envelope, session_id="s1", turn_id="t2", status="ok")
    quote({"passage": "P1", "lines": [1]}, session_id="s1", turn_id="t2")
    second = transform(response_text="MODEL_999", session_id="s1", turn_id="t2", platform="cli")
    assert verifier.SEAL not in second
    assert GROUNDED in second
    count, error = audit.verify_file(hermes_home / "cited" / "audit.jsonl")
    assert error is None and count == 1
