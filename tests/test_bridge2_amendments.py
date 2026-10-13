"""Ported independent probes of the bridge review rounds (in-repo regressions).

The adversarial reviews of this change keep their behavioural probes outside the repository; these are
the same probes ported back so the suite itself guards the findings. Two sources are covered:

* ``tasks/revision-bridge2-r1.md`` (round 1 of this cycle): the command and transformer diagnostics of
  a failing profile, the real ``PluginState`` alternating two homes, a same-home mode change, the new
  Unicode and whitespace search queries and the native non-string argument edge.
* ``tasks/revision-bridge-r3.md`` (round 3 of the previous cycle): the tracked-modification host pin,
  the ``tar.umask`` override, the fractional lock size, the real loader catalog of a profile and the
  empty-retrieval home inventory.

The two turn-ownership counterexamples of the bridge2 round (M01-B2R1 and M02-B2R1) live in
``tests/test_round4_amendments.py`` beside the D6/H14 cases. Every host-coupled case below uses the real
``agent.secret_scope`` and the real ``hermes_cli.plugins_state.PluginState`` of the pinned host over a
temporary ``HERMES_HOME``; the module is skipped with an explicit reason when the read-only copy of the
pinned host is absent, so the ordinary suite stays runnable.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import json
import logging
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

import search_guard
from bridge_support import FakeContext, inventory
from hermes_cited import client, config, plugin

REPO = Path(__file__).resolve().parents[1]
CHANGE = REPO / "openspec" / "changes" / "search-only-bridge"
TASKS = CHANGE / "tasks.md"
REPORTS = CHANGE / "reports"

HOST_COMMIT = "dce1e9b37581dd62e480a9064dc04a709c2940d3"
REVIEW_ROOT = Path(
    os.environ.get(
        "HERMES_REVIEW_ROOT",
        str(Path(os.environ.get("TEMP", "/tmp")) / "codex-hermes-cited-r2-2d438babc89e4a55af33b15bab5269cd"),
    )
)
HOST_COPY = REVIEW_ROOT / "host-fast" / "hermes-agent-{0}".format(HOST_COMMIT)
HOST_SITE_PACKAGES = REVIEW_ROOT / "host-venv" / "Lib" / "site-packages"

#: Synthetic credentials only. One lives in the profile scope and a different one in the root
#: environment, which is exactly the boundary the redaction rule protects; neither is a real secret.
PROFILE_SECRET = "synthetic-bridge2-profile-value"
ROOT_SECRET = "synthetic-bridge2-root-value"

requires_host = pytest.mark.skipif(
    not (HOST_COPY / "agent" / "secret_scope.py").exists(),
    reason="the read-only copy of the Hermes host is not present",
)


@pytest.fixture()
def host(monkeypatch):
    """Put the pinned host and its review venv on ``sys.path``, ahead of the checkout."""
    if HOST_SITE_PACKAGES.exists():
        monkeypatch.syspath_prepend(str(HOST_SITE_PACKAGES))
    monkeypatch.syspath_prepend(str(HOST_COPY))
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    monkeypatch.setenv("CITED_MCP_TOKEN", ROOT_SECRET)
    from agent import secret_scope

    return secret_scope


@pytest.fixture()
def installer():
    """Load ``tests/test_profile_install.py`` by path so its private verifiers are exercised."""
    name = "bridge2_amendments_install_subject"
    spec = importlib.util.spec_from_file_location(name, REPO / "tests" / "test_profile_install.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@contextlib.contextmanager
def scoped(host, home, **overrides):
    """The real ``agent.secret_scope`` plus the host home override over one guarded profile."""
    from hermes_constants import reset_hermes_home_override, set_hermes_home_override

    search_guard.guard_path(home, kind="review profile")
    values = dict(
        CITED_BRIDGE_TOOLS="full",
        CITED_DEFAULT_MODE="dot",
        CITED_LANGUAGE="en",
        CITED_URL="http://127.0.0.1:9",
        CITED_MCP_TOKEN=PROFILE_SECRET,
    )
    values.update(overrides)
    marker = host.set_secret_scope(values, profile_home=str(home))
    home_marker = set_hermes_home_override(home)
    try:
        yield values
    finally:
        reset_hermes_home_override(home_marker)
        host.reset_secret_scope(marker)


def registered():
    context = FakeContext()
    plugin.register(context)
    return context


def evidence(context, session="review-session", turn="live"):
    """One search bound to the turn, so the profile holds a quotable passage."""
    context.hooks["pre_llm_call"][0](session_id=session, turn_id=turn)
    context.hooks["post_tool_call"][0](
        tool_name="cited_search",
        args={"query": "review"},
        result=json.dumps(
            {
                "cited_tool": "cited_search",
                "query": "review",
                "text": "",
                "passages": [
                    {
                        "n": 1,
                        "document": "review.txt",
                        "heading": None,
                        "position": 0,
                        "excerpt": "Independent review evidence.",
                        "lines": [{"line": 1, "text": "Independent review evidence."}],
                    }
                ],
            }
        ),
        session_id=session,
        turn_id=turn,
        status="ok",
    )


# --------------------------------------------------------------------------------------------------
# Ported probes of the bridge2 round 1 review (tasks/revision-bridge2-r1.md).
# --------------------------------------------------------------------------------------------------


@requires_host
def test_invalid_quote_line_does_not_echo_profile_credential(tmp_path, host):
    """H6/D8: the invalid-line sentence is redacted with the validated profile credential."""
    with scoped(host, tmp_path / "quote"):
        context = registered()
        evidence(context)
        result = context.tools["cited_quote"]["handler"](
            {"passage": "P1", "lines": [PROFILE_SECRET]}, session_id="review-session", turn_id="live"
        )
        assert PROFILE_SECRET not in result
        assert plugin._turn_of("review-session", "live", home=tmp_path / "quote").selections == []


@requires_host
def test_pre_hook_exception_is_sanitized_before_host_dispatch_logs_it(tmp_path, host, monkeypatch, caplog):
    """D8/H6: the real host dispatcher logs the contained failure, never the profile secret."""
    from hermes_cli.plugins import PluginManager

    def fail(*args, **kwargs):
        raise RuntimeError("pre-hook synthetic failure: " + PROFILE_SECRET)

    with scoped(host, tmp_path / "pre-failure", CITED_DEFAULT_MODE="cited"):
        context = registered()
        manager = PluginManager()
        manager._hooks["pre_llm_call"] = [context.hooks["pre_llm_call"][0]]
        monkeypatch.setattr(plugin.delivery, "snapshot", fail)
        with caplog.at_level(logging.WARNING):
            manager.invoke_hook("pre_llm_call", session_id="new-pre-error", turn_id="probe")
        assert "pre-hook synthetic failure" in caplog.text
        assert PROFILE_SECRET not in caplog.text


@requires_host
@pytest.mark.parametrize("callback", ["quote", "post"])
def test_new_callback_exception_chains_redact_profile_secret(tmp_path, host, monkeypatch, caplog, callback):
    """D8: an exception with a chained cause is redacted on the quote and the post-tool path."""

    def fail(*args, **kwargs):
        try:
            raise ValueError("cause " + PROFILE_SECRET)
        except ValueError as error:
            raise RuntimeError("wrapper " + PROFILE_SECRET) from error

    with scoped(host, tmp_path / callback):
        context = registered()
        evidence(context)
        with caplog.at_level(logging.ERROR):
            if callback == "quote":
                monkeypatch.setattr(plugin.Turn, "add_quote", fail)
                context.tools["cited_quote"]["handler"]({}, session_id="review-session", turn_id="live")
            else:
                monkeypatch.setattr(plugin.Turn, "note_call", fail)
                evidence(context)
        assert "wrapper" in caplog.text
        assert PROFILE_SECRET not in caplog.text


@requires_host
def test_real_state_alternating_profiles_keep_opposite_modes(tmp_path, host):
    """D7/H22: the real ``PluginState`` keeps the mode of each home independent."""
    from hermes_cli.plugins_state import PluginState

    contexts = {}
    for name, command in [("one", "cited"), ("two", "dot")]:
        with scoped(host, tmp_path / name):
            context = FakeContext()
            context.state = PluginState("hermes-cited")
            plugin.register(context)
            context.commands[command]()
            contexts[name] = context
    for name, expected in [
        ("one", {"context": plugin.CITED_RULES}),
        ("two", None),
        ("one", {"context": plugin.CITED_RULES}),
    ]:
        with scoped(host, tmp_path / name):
            assert contexts[name].hooks["pre_llm_call"][0](session_id="alternating", turn_id="same") == expected


@requires_host
def test_refused_same_home_mode_change_preserves_pending_evidence(tmp_path, host):
    """D6: a callback of the same home under a changed mode is refused without dropping the turn."""
    home = tmp_path / "mode-change"
    with scoped(host, home):
        context = registered()
        evidence(context)
    with scoped(host, home, CITED_BRIDGE_TOOLS="search"):
        context.hooks["transform_llm_output"][0](
            session_id="review-session", turn_id="live", response_text="foreign-mode"
        )
    with scoped(host, home):
        assert (
            context.tools["cited_quote"]["handler"](
                {"passage": "P1", "lines": [1]}, session_id="review-session", turn_id="live"
            )
            == "Independent review evidence."
        )


@requires_host
@pytest.mark.parametrize("query", ["\U0001f9ea" * 1000, "a\r\nb\t c", "\u00e9" * 1000])
def test_search_preserves_new_unicode_and_whitespace_queries(tmp_path, host, query):
    """H21: the newest Unicode queries and inner whitespace reach the wire unchanged, with no write."""
    from fakes.chassis_surface import start_chassis

    running = start_chassis()
    home = tmp_path / "search"
    try:
        with scoped(
            host, home, CITED_BRIDGE_TOOLS="search", CITED_URL=running.url, CITED_SEARCH_TOKEN=running.token
        ):
            before = inventory(home)
            context = registered()
            result = json.loads(context.tools["cited_search"]["handler"]({"query": query, "limit": 1}))
            assert result["query"] == query
            assert inventory(home) == before
    finally:
        running.stop()


@requires_host
def test_search_mixed_nonstring_unknown_keys_return_sentence(tmp_path, host):
    """H21: a native mapping with mixed key types answers a sentence instead of raising."""
    with scoped(
        host, tmp_path / "malformed", CITED_BRIDGE_TOOLS="search", CITED_SEARCH_TOKEN="synthetic-search"
    ):
        context = registered()
        result = context.tools["cited_search"]["handler"]({"query": "review", 1: "unexpected", "extra": 1})
        assert isinstance(result, str) and not result.startswith("{")


@requires_host
def test_new_catalog_probe_discovers_the_passed_profile_with_real_host(tmp_path, monkeypatch, installer):
    """D4/H22: the real loader discovers the installed plugin and dispatches one scoped call."""
    profile = tmp_path / "root" / "profiles" / "installed"
    destination = profile / "plugins" / "hermes-cited"
    destination.parent.mkdir(parents=True)
    shutil.copytree(
        REPO,
        destination,
        ignore=shutil.ignore_patterns(".git", ".venv", ".tmp", ".pytest_cache", "__pycache__", "tests",
                                      "scripts", "openspec"),
    )
    (profile / "config.yaml").write_text("plugins:\n  enabled:\n    - hermes-cited\n", encoding="utf-8")
    from fakes.chassis_surface import start_chassis

    running = start_chassis(token="synthetic-catalog-bridge2")
    try:
        installer._write_profile_env(profile, running.url, running.token)
        monkeypatch.setenv(
            "PYTHONPATH", os.pathsep.join([str(HOST_COPY), str(HOST_SITE_PACKAGES)])
        )
        catalog = installer._effective_catalog(sys.executable, profile)
        installer._assert_search_catalog(catalog)
        assert len(running.fake.requests) == 1
    finally:
        running.stop()


@requires_host
def test_real_scope_empty_retrieval_and_scope_rejection_preserve_every_home_file(tmp_path, host):
    """H20/H21: an empty retrieval and a later scope rejection leave every home file untouched."""
    from fakes.chassis_surface import start_chassis

    home = tmp_path / "empty-retrieval"
    home.mkdir()
    (home / "before.bin").write_bytes(bytes(reversed(range(128))))

    def snapshot():
        return {
            path.relative_to(home).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(home.rglob("*"))
            if path.is_file()
        }

    baseline = snapshot()
    running = start_chassis(token="synthetic-empty-retrieval-bridge2")
    running.fake.passages = []
    try:
        with scoped(
            host, home, CITED_BRIDGE_TOOLS="search", CITED_URL=running.url, CITED_SEARCH_TOKEN=running.token
        ):
            context = FakeContext()
            plugin.register(context)
            question = "\u2205 \U0001f9ed no-match"
            result = json.loads(context.tools["cited_search"]["handler"]({"query": question, "limit": 2}))
            assert result == {"cited_tool": "cited_search", "query": question, "text": "", "passages": []}
        with scoped(host, home, CITED_BRIDGE_TOOLS="full"):
            rejected = context.tools["cited_search"]["handler"]({"query": question})
        assert rejected == config.SCOPE_SENTENCE
        assert len(running.fake.requests) == 1
        assert not context.commands and not context.hooks and not context.skills
        assert snapshot() == baseline
    finally:
        running.stop()


# --------------------------------------------------------------------------------------------------
# Ported probes of the bridge round 3 review (tasks/revision-bridge-r3.md), offline unit mechanics.
# --------------------------------------------------------------------------------------------------


def test_host_pin_rejects_modified_tracked_runtime(tmp_path, installer):
    """D4: a tracked modification of the host checkout disqualifies it even when HEAD is the pin."""
    repo = installer._make_git_repo(tmp_path / "pinned-host")
    sha = installer._git(repo, "rev-parse", "HEAD").strip()
    (repo / "README.md").write_text("changed after the pinned commit\n", encoding="utf-8")
    with pytest.raises(ValueError):
        installer._check_host_pin(repo, expected=sha)


def test_archive_digest_is_not_changed_by_local_tar_permissions(tmp_path, installer):
    """D5: an effective ``tar.umask`` override is rejected instead of silently changing the bytes."""
    repo = installer._make_git_repo(tmp_path / "source")
    sha = installer._git(repo, "rev-parse", "HEAD").strip()
    installer._canonical_archive(repo, sha, tmp_path / "clean.tar")
    installer._git(repo, "config", "tar.umask", "0077")
    with pytest.raises(ValueError):
        installer._canonical_archive(repo, sha, tmp_path / "override.tar")


def test_lock_size_does_not_silently_truncate_fraction(tmp_path, installer):
    """D5: the lock byte size is an integer; ``10240.75`` is a defect, never ``10240``."""
    path = tmp_path / "fraction.lock"
    path.write_text(json.dumps({"sha": "e" * 40, "sha256": "2" * 64, "size": 10240.75}), encoding="utf-8")
    with pytest.raises(ValueError):
        installer._read_bridge_lock(path)


@pytest.mark.parametrize("key", ["CITED_TIMEOUT_MS", "CITED_SEARCH_TOKEN", "CITED_URL"])
def test_scope_failure_after_register_is_fixed_and_never_requests_root(tmp_path, monkeypatch, key):
    """D2/H21: a per-key scope getter failure after registration answers the fixed sentence, no request."""
    values = {
        "CITED_BRIDGE_TOOLS": "search",
        "CITED_URL": "http://127.0.0.1:9",
        "CITED_SEARCH_TOKEN": "synthetic-search-bridge2",
        "CITED_TIMEOUT_MS": "500",
    }
    home = tmp_path / "search"
    marker = config.bind_scope(values, str(home))
    try:
        context = FakeContext()
        plugin.register(context)
    finally:
        config.unbind_scope(marker)
    requests = []
    monkeypatch.setattr(client, "_open", lambda *args, **kwargs: requests.append(args))

    def getter(name, default=""):
        if name == key:
            raise RuntimeError("internal synthetic detail")
        return values.get(name, default)

    marker = config.bind_scope(values, str(home), getter=getter)
    try:
        response = context.tools["cited_search"]["handler"]({"query": "new round three query"})
    finally:
        config.unbind_scope(marker)
    assert response == config.SCOPE_SENTENCE
    assert not requests


def test_cli_record_directly_in_temp_root_never_authorizes_all_temp():
    """Task 1.1/M03: a ``--record`` directly under the process temporary root registers nothing."""
    from fakes.chassis_surface import prepare_cli_guard

    previous = list(search_guard._WORKSPACES)
    search_guard._WORKSPACES.clear()
    try:
        with pytest.raises(search_guard.GuardError):
            prepare_cli_guard(Path(tempfile.gettempdir()) / "bridge2-no-file-is-created.jsonl")
        assert Path(tempfile.gettempdir()).resolve() not in search_guard.workspaces()
    finally:
        search_guard._WORKSPACES[:] = previous


# --------------------------------------------------------------------------------------------------
# Evidence consistency: the tasks the reviews reopened close only with their measured reports.
# --------------------------------------------------------------------------------------------------


def test_reopened_rounds_close_only_with_their_measured_reports():
    """The bridge reviews reopened 11.1/11.4/11.6/13.2/13.5; each closure names a report on disk.

    This is the ported intent of the external ``test_tasks_do_not_close_the_unexecuted_real_catalog``
    probe, flipped to its final contract: the tasks are closed **and** the reports that measured them
    exist with their counts. When 13.4 was re-executed offline its probe's expectation that 11.4 stays
    open became obsolete, so the invariant is the evidence, not the permanent openness.
    """
    text = TASKS.read_text(encoding="utf-8")
    status = {number: flag for flag, number in re.findall(r"^- \[([ x])\] (\d+\.\d+)\b", text, re.M)}
    for number in ("11.1", "11.4", "11.6", "13.2", "13.5"):
        assert status[number] == "x", number + " must be closed with the measured report of this round"
    measured = {
        "2026-10-13-step-15-turn-identity-b2r1.md": ("13.2", "11.1"),
        "2026-10-13-step-15-install-b2r1.md": ("13.4", "11.4"),
        "2026-10-13-step-15-close-b2r1.md": ("13.5", "11.6"),
    }
    for name, numbers in measured.items():
        path = REPORTS / name
        assert path.is_file(), "the closure of {0} needs {1}".format(", ".join(numbers), name)
        body = path.read_text(encoding="utf-8")
        for number in numbers:
            assert number in body, "{0} must record {1}".format(name, number)
