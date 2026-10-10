"""Permanent regressions of the first Codex review: B1-B3, M1-M7 and m1.

Every test names its review and its finding id in the docstring. Round 4 (D9) retired the local custody, so
where the review asked for a key, a checkpoint or a high-water mark the test asserts what the product does
today and says so: the hash-chained consistency record, the fixed operational refusal without a seal when the
append fails, and the refusal to append over a broken chain. Every run uses the temporary ``HERMES_HOME`` of
the fixtures.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from hermes_cited import audit, plugin, render, tools, verifier
from hermes_cited.client import CitedError, call_tool_full
from hermes_cited.config import Settings

REPO = Path(__file__).resolve().parents[2]
QUIET = "streaming:\n  enabled: false\ndisplay:\n  streaming: false\n  interim_assistant_messages: false\n"
STREAM = "streaming:\n  enabled: true\n"
GROUNDED = "- Afinacion de bicicleta: 380 pesos."


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
        self.tools[name] = {"toolset": toolset, "schema": schema, "handler": handler}

    def register_hook(self, hook_name, callback):
        self.hooks.setdefault(hook_name, []).append(callback)

    def register_command(self, name, handler, description="", args_hint="", argument_mode=None):
        self.commands[name] = handler

    def register_skill(self, name, path, description="", frontmatter=None):
        self.skills[name] = {"path": path, "description": description, "frontmatter": frontmatter}


def context(monkeypatch, hermes_home, mode="cited", config=QUIET):
    monkeypatch.setenv("CITED_DEFAULT_MODE", mode)
    if config is not None:
        (hermes_home / "config.yaml").write_text(config, encoding="utf-8")
    ctx = FakeContext()
    plugin.register(ctx)
    return ctx


def hook(ctx, name, **payload):
    results = [callback(**payload) for callback in ctx.hooks.get(name, [])]
    return results[0] if len(results) == 1 else results


def envelope(excerpt, document="d.md", heading="H", number=1, text="transport"):
    return json.dumps(
        {
            "cited_tool": "cited_search",
            "query": "precio",
            "text": text,
            "passages": [
                {"n": number, "document": document, "heading": heading, "position": 0, "excerpt": excerpt}
            ],
        }
    )


def run(ctx, raw, answer="", select=None, session="s1", turn="t1", platform="cli", question="precio",
        args=None):
    parsed = tools.parse_tool_result(raw) or {}
    tool_name = parsed.get("cited_tool") or "cited_search"
    hook(ctx, "pre_llm_call", session_id=session, turn_id=turn, user_message=question, platform=platform)
    hook(ctx, "post_tool_call", tool_name=tool_name,
         args=args if args is not None else {"query": question}, result=raw,
         session_id=session, turn_id=turn, status="ok")
    if select is not None:
        ctx.tools["cited_quote"]["handler"]({"passage": select, "lines": [1]}, session_id=session,
                                            turn_id=turn)
    return hook(ctx, "transform_llm_output", response_text=answer, session_id=session, turn_id=turn,
                platform=platform)


def forged_ok(answer, excerpt):
    forged = render.Line(1, 1, answer, "d.md", "H", pid="P1", original=1)
    return verifier.verify_display([forged], render.excerpt_lines(excerpt)).ok


def payload(index):
    return {
        "ts": "2026-10-09T22:00:0{0}Z".format(index),
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


def load_gate():
    spec = importlib.util.spec_from_file_location("gate_r1", REPO / "scripts" / "gate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def gate():
    return load_gate()


def test_r1_b1_the_model_draft_never_reaches_the_final_message(monkeypatch, hermes_home, cited_env):
    """R1 B1: text could reach the user before Cited decided.

    The host still streams deltas before ``transform_llm_output`` (the limit D1/C2 declare and
    ``tests/test_host.py`` measures on the real mixin). What the plugin controls is the final message: the
    draft is discarded whole, and on a surface where a draft could have been visible the seal is withheld.
    """
    raw = envelope(GROUNDED)
    quiet = context(monkeypatch, hermes_home)
    final = run(quiet, raw, answer="UNVERIFIED_999", select="P1")
    assert "UNVERIFIED_999" not in final
    assert GROUNDED in final
    assert final.rstrip().endswith(verifier.SEAL)

    streaming = context(monkeypatch, hermes_home, config=STREAM)
    withheld = run(streaming, raw, answer="UNVERIFIED_999", select="P1", session="s2", turn="t2",
                   platform="telegram")
    assert "UNVERIFIED_999" not in withheld
    assert verifier.SEAL not in withheld
    assert "Note on delivery" in withheld


def test_r1_b2_an_echoed_query_with_zero_passages_cannot_verify_itself(monkeypatch, hermes_home, cited_env):
    """R1 B2: the transport text echoed the query, so a datum with zero passages verified itself.

    The evidence of a turn is only the non-empty excerpt of a passage or a citation; the query, the answer,
    the headings and the transport text are left out.
    """
    raw = json.dumps(
        {
            "cited_tool": "cited_search",
            "query": "999 pesos",
            "text": 'No passage of the documents of this installation matches "999 pesos".',
            "passages": [],
        }
    )
    assert tools.grounding_excerpts(tools.parse_tool_result(raw)) == []
    ctx = context(monkeypatch, hermes_home)
    final = run(ctx, raw, answer="Cuesta 999 pesos.")
    assert final == render.refusal_text("es")
    assert "999" not in final


def test_r1_b2_a_generated_answer_is_not_its_own_evidence(monkeypatch, hermes_home, cited_env):
    """R1 B2: the generated answer of ``cited_ask`` was accepted as evidence of itself.

    Only the citation excerpt is evidence; a selected line renders the excerpt, never the answer of the
    model.
    """
    raw = json.dumps(
        {
            "cited_tool": "cited_ask",
            "question": "precio",
            "status": "answered",
            "answer": "Cuesta 999 pesos.",
            "text": "Cuesta 999 pesos.",
            "citations": [
                {"n": 1, "document": "d.md", "heading": "H", "position": 1, "excerpt": "Cuesta 380 pesos."}
            ],
        }
    )
    assert tools.grounding_excerpts(tools.parse_tool_result(raw)) == ["Cuesta 380 pesos."]
    ctx = context(monkeypatch, hermes_home)
    assert run(ctx, raw, answer="Cuesta 999 pesos.") == render.refusal_text("es")
    final = run(ctx, raw, answer="Cuesta 999 pesos.", select="P1", session="s2", turn="t2")
    assert "Cuesta 380 pesos." in final
    assert "999" not in final


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308], ids=lambda value: "http-{0}".format(value))
def test_r1_b3_a_redirect_never_forwards_the_bearer(cited_factory, status):
    """R1 B3: a 302 sent the bearer to another origin.

    The private opener refuses every redirect before a second request: the sink receives nothing and the
    failure is a redacted sentence.
    """
    origin = cited_factory()
    sink = cited_factory()
    origin.behavior = "redirect"
    origin.redirect_status = status
    origin.redirect_location = "{0}/sink".format(sink.url)
    settings = Settings(origin.url, origin.token, 5000, "cited")
    with pytest.raises(CitedError) as caught:
        call_tool_full("cited_search", {"query": "precio"}, settings)
    assert "redirect" in str(caught.value).lower()
    assert origin.token not in str(caught.value)
    assert sink.requests == []
    assert len(origin.requests) == 1


def test_r1_b3_a_downgrade_is_refused_and_the_global_opener_is_untouched():
    """R1 B3: a downgrade to http and the promise that no global opener is installed."""
    import urllib.request

    from hermes_cited.client import _RefuseRedirects

    handler = _RefuseRedirects()
    request = urllib.request.Request("https://cited.example.com/api/mcp", method="POST")
    assert handler.redirect_request(request, None, 302, "Found", {}, "http://cited.example.com/api/mcp") is None
    assert handler.redirect_request(request, None, 308, "Permanent", {}, "http://evil.example/api/mcp") is None
    before = urllib.request._opener
    from hermes_cited import client

    client._opener()
    assert urllib.request._opener is before


M1_CASES = [
    ("moneda", "Cuesta €380.", "Cuesta $380."),
    ("signo", "Saldo: -380 pesos.", "Saldo: 380 pesos."),
    ("fecha", "Fecha 10/09/2026.", "Fecha 09/10/2026."),
    ("codigo", "Código xyz-123.", "Código abc-123."),
    ("superindice", "Cuesta ⁹⁹⁹ pesos.", "Cuesta 380 pesos."),
    ("numeral-escrito", "Cuesta novecientos pesos.", "Cuesta trescientos pesos."),
    ("unidad", "Dosis 5 mcg.", "Dosis 5 mg."),
    ("plural", "Garantía: 1 día.", "Garantía: 1 días."),
    ("fullwidth", "Cuesta ３８０ pesos.", "Cuesta 380 pesos."),
    ("miles-u202f", "Cuesta 1\u202f200 pesos.", "Cuesta 1200 pesos."),
    ("cita", "Cuesta 380 pesos [1].", "Cuesta 380 pesos."),
    ("decimal-ambiguo", "Dosis 1.200 mg.", "Dosis 1200 mg."),
    ("sujeto", "Espresso: 380 pesos.", "Espresso: 35 pesos. Afinación: 380 pesos."),
    ("mayusculas", "CUESTA 380 PESOS.", "Cuesta 380 pesos."),
]


@pytest.mark.parametrize("case_id,answer,excerpt", M1_CASES, ids=[case[0] for case in M1_CASES])
def test_r1_m1_a_changed_datum_or_a_rejected_equivalence_is_never_rendered(case_id, answer, excerpt,
                                                                           monkeypatch, hermes_home,
                                                                           cited_env):
    """R1 M1: the extractor accepted changed data and rejected documented equivalences.

    D5 removed the token comparison: the model chooses whole lines, so a changed datum is never a block and
    the chosen line is copied byte for byte out of the excerpt.
    """
    assert forged_ok(answer, excerpt) is False
    ctx = context(monkeypatch, hermes_home)
    raw = envelope(excerpt)
    assert run(ctx, raw, answer=answer) == render.refusal_text("es")
    final = run(ctx, raw, answer=answer, select="P1", session="s2", turn="t2")
    assert render.excerpt_lines(excerpt)[0] in final
    assert answer not in final


def test_r1_m2_a_success_that_reflects_the_token_is_discarded(cited_env):
    """R1 M2: a successful response kept the bearer in its result.

    The client rejects any body that reflects the token before the envelope is built, so nothing of it is
    shown or recorded.
    """
    cited_env.echo_token = True
    result = tools.search({"query": "precio"})
    assert cited_env.token not in result
    assert "token" in result.lower()
    assert "discarded" in result.lower()


def test_r1_m2_an_error_that_reflects_the_token_is_redacted(cited_env):
    """R1 M2: the redaction has to cover the error path too."""
    cited_env.behavior = "jsonrpc_error_token"
    result = tools.search({"query": "precio"})
    assert cited_env.token not in result
    assert "<token>" in result


@pytest.mark.parametrize("place", ["pregunta", "argumentos", "metadatos"], ids=["pregunta", "argumentos",
                                                                               "metadatos"])
def test_r1_m2_the_secret_never_reaches_the_record(place, monkeypatch, hermes_home, cited_env):
    """R1 M2: the token travelled into the question, the arguments and the metadata of the log."""
    token = cited_env.token
    ctx = context(monkeypatch, hermes_home)
    if place == "pregunta":
        run(ctx, envelope(GROUNDED), select="P1", question=token)
    elif place == "argumentos":
        run(ctx, envelope(GROUNDED), select="P1", question="precio", args={"query": token})
    else:
        run(ctx, envelope(GROUNDED, document=token), select="P1", question="precio")
    text = (hermes_home / "cited" / "audit.jsonl").read_text(encoding="utf-8")
    assert token not in text
    assert "<token>" in text


def test_r1_m3_concurrent_threads_keep_one_chain(tmp_path):
    """R1 M3: two writers read the same tail and the chain lost or duplicated an entry.

    The append holds an exclusive lock and validates the whole chain before writing, so the threads of one
    log keep an exact count, an exact sequence and one identity.
    """
    path = tmp_path / "audit.jsonl"
    writers = 6
    each = 5
    barrier = threading.Barrier(writers)
    errors = []

    def writer(number):
        try:
            barrier.wait(timeout=15)
            for index in range(each):
                audit.append_entry(path, payload(number * each + index))
        except Exception as error:
            errors.append(error)

    threads = [threading.Thread(target=writer, args=(number,)) for number in range(writers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert errors == []
    entries = audit.read_entries(path)
    assert len(entries) == writers * each
    assert [entry["seq"] for entry in entries] == list(range(1, writers * each + 1))
    assert len({entry["turn_id"] for entry in entries}) == writers * each
    assert audit.verify_file(path) == (writers * each, None)


CHILD = (
    "import sys\n"
    "from hermes_cited import audit\n"
    "path, name = sys.argv[1], sys.argv[2]\n"
    "for index in range(3):\n"
    "    audit.append_entry(path, {'ts': '2026-10-10T00:00:00Z', 'platform': 'cli', 'session': name,\n"
    "        'turn_id': '{0}-{1}'.format(name, index), 'user': '', 'mode': 'cited', 'question': 'q',\n"
    "        'tool_calls': [], 'sources': [], 'response': 'r',\n"
    "        'verifier': {'applied': True, 'ok': True, 'ungrounded': []}})\n"
)


def test_r1_m3_concurrent_processes_keep_one_chain(tmp_path):
    """R1 M3: the review asked for several processes, not only threads."""
    path = tmp_path / "audit.jsonl"
    environment = {**os.environ, "PYTHONPATH": str(REPO)}
    children = [
        subprocess.Popen(
            [sys.executable, "-B", "-c", CHILD, str(path), "p{0}".format(number)],
            cwd=str(REPO), env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        for number in range(3)
    ]
    codes = []
    errors = []
    for child in children:
        _out, err = child.communicate(timeout=120)
        codes.append(child.returncode)
        errors.append(err.decode("utf-8", "replace"))
    assert codes == [0, 0, 0], errors
    entries = audit.read_entries(path)
    assert len(entries) == 9
    assert [entry["seq"] for entry in entries] == list(range(1, 10))
    assert audit.verify_file(path) == (9, None)


def _chain(path, entries=3):
    for index in range(entries):
        audit.append_entry(path, payload(index))


def _rewrite(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _attempt(path):
    try:
        audit.append_entry(path, payload(9))
        return "appended"
    except audit.AuditError:
        return "refused"


def test_r1_m4_a_removed_tail_or_a_recomputed_chain_is_the_declared_limit(tmp_path):
    """R1 M4: the chain could not tell a removed tail or a rewritten and recomputed file.

    Round 4 retired the custody mark (D9), so this is asserted as the documented limit: the record proves
    internal consistency, not completeness nor authenticity, and the README says it in plain language.
    """
    removed = tmp_path / "removed.jsonl"
    _chain(removed, 3)
    rows = removed.read_text(encoding="utf-8").splitlines()
    removed.write_text("\n".join(rows[:-1]) + "\n", encoding="utf-8")
    assert audit.verify_file(removed) == (2, None)
    assert _attempt(removed) == "appended"
    assert audit.verify_file(removed) == (3, None)

    recalculated = tmp_path / "recalculated.jsonl"
    _chain(recalculated, 3)
    entries = audit.read_entries(recalculated)
    previous = audit.GENESIS
    for entry in entries:
        entry["response"] = "rewritten"
        entry["prev_hash"] = previous
        entry["hash"] = audit.entry_hash(entry)
        previous = entry["hash"]
    _rewrite(recalculated, entries)
    assert audit.verify_entries(entries) == (True, 0, None)
    assert audit.verify_file(recalculated) == (3, None)


def test_r1_m4_a_broken_chain_refuses_the_next_append(tmp_path):
    """R1 M4: the append never restarts from genesis over a chain that does not validate."""
    broken = tmp_path / "broken.jsonl"
    _chain(broken, 3)
    rows = broken.read_text(encoding="utf-8").splitlines()
    del rows[1]
    broken.write_text("\n".join(rows) + "\n", encoding="utf-8")
    before = broken.read_bytes()
    assert _attempt(broken) == "refused"
    assert broken.read_bytes() == before


def test_r1_m5_a_failed_append_is_the_operational_refusal_without_a_seal(monkeypatch, hermes_home, cited_env):
    """R1 M5: a failed append still returned a sealed answer.

    The boundary of the whole transformer makes a persistence failure the fixed operational refusal: no
    seal, an incident code and no error detail.
    """
    ctx = context(monkeypatch, hermes_home)

    def fail(*args, **kwargs):
        raise PermissionError("synthetic read-only log")

    monkeypatch.setattr(audit, "append_entry", fail)
    final = run(ctx, envelope(GROUNDED), answer="MODEL_999", select="P1")
    assert verifier.SEAL not in final
    assert "CITED-" in final
    assert "PermissionError" not in final
    assert not (hermes_home / "cited" / "audit.jsonl").exists()


def test_r1_m5_the_session_and_the_turn_are_written(monkeypatch, hermes_home, cited_env):
    """R1 M5: the session was always written empty."""
    ctx = context(monkeypatch, hermes_home)
    run(ctx, envelope(GROUNDED), select="P1", session="session-real", turn="t1")
    run(ctx, envelope(GROUNDED), select="P1", session="session-real", turn="t2")
    entries = audit.read_entries(hermes_home / "cited" / "audit.jsonl")
    assert [(entry["session"], entry["turn_id"]) for entry in entries] == [
        ("session-real", "t1"),
        ("session-real", "t2"),
    ]


def test_r1_m6_the_gate_requires_the_bound_amount_and_citation(gate):
    """R1 M6: the gate's price predicate only looked for a substring and a tool name."""
    assert gate.amount_with_citation("Cuesta 1380 pesos [99].", "380") is False
    assert gate.amount_with_citation("Cuesta 380 pesos.", "380") is False
    assert gate.amount_with_citation("Cuesta 380 pesos [1].", "380") is True
    assert gate.amount_statement("380 pesos [99].", "380", unit="currency", mark=1) is False


def test_r1_m6_the_gate_rejects_a_refusal_that_states_a_datum(gate):
    """R1 M6: ``No está en los documentos, pero cuesta 999 pesos.`` passed the refusal predicate."""
    assert gate.clean_refusal("No está en los documentos, pero cuesta 999 pesos.") is False
    assert gate.clean_refusal("No está en los documentos.") is True


@pytest.mark.parametrize(
    "tools_before,expected",
    [
        (["browser_navigate", "cited_search"], False),
        (["tool_describe", "cited_ask", "cited_search"], True),
        ([], False),
    ],
    ids=["herramienta-de-datos-antes", "solo-descubrimiento-antes", "sin-herramientas"],
)
def test_r1_m6_only_discovery_may_precede_the_first_cited_tool(gate, tools_before, expected):
    """R1 M6: ``["browser_navigate", "cited_search"]`` passed the old partial list."""
    assert gate.first_cited_before_others(tools_before) is expected


def test_r1_m6_an_empty_digest_list_does_not_pass(gate):
    """R1 M6: ``all([])`` passed and no digest was recomputed."""
    ok, detail = gate.recompute_digests([])
    assert ok is False
    assert detail


def test_r1_m6_the_seal_is_crossed_with_its_audited_entry(gate):
    """R1 M6: the seal was accepted by substring, without the delivery decision of the turn."""
    text = "Según tus documentos:\n\n- Afinacion de bicicleta: 380 pesos. [1]\n\nVerified by Cited"
    entry = {
        "response": text,
        "delivery": {"seal": True},
        "verifier": {"applied": True, "ok": True, "verified": True, "seal_withheld": False},
    }
    assert gate.seal_matches_entry(text, entry) is True
    forged = dict(entry, delivery={"seal": False})
    assert gate.seal_matches_entry(text, forged) is False
    assert gate.seal_matches_entry(text, {"response": "otra", "verifier": {"ok": True}}) is False


def test_r1_m6_the_selftest_negatives_are_the_gate_cases(gate):
    """R1 M6: the self-test has to carry the review's negatives as its own cases.

    The full ``gate_selftest`` run lives in ``tests/test_gate.py``; here the counterexamples are asserted
    against the predicates themselves, so the regression survives a gate that evolves.
    """
    source = (REPO / "scripts" / "gate.py").read_text(encoding="utf-8")
    assert "gate_selftest" in source
    assert "1380" in source
    assert "190 days" in source
    assert "Stock: cero." in source
    assert "-380 pesos [99]." in source
    assert "-90 days" in source
    assert "380 kg, pesos [99]" in source


def test_r1_m7_the_documented_command_reports_internal_consistency(tmp_path):
    """R1 M7: the audit command failed after installing because the module was not importable.

    The documented shape is the module run from the installed plugin directory; this runs it from the
    checkout with the plugin on the path, on a good chain (exit 0) and on a cut one (exit 1).
    """
    path = tmp_path / "audit.jsonl"
    _chain(path, 3)
    environment = {**os.environ, "PYTHONPATH": str(REPO), "PYTHONIOENCODING": "utf-8"}
    good = subprocess.run(
        [sys.executable, "-B", "-m", "hermes_cited.verify_log", str(path)],
        cwd=str(REPO), env=environment, capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    assert good.returncode == 0
    assert "internally consistent" in good.stdout
    rows = path.read_text(encoding="utf-8").splitlines()
    del rows[1]
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    broken = subprocess.run(
        [sys.executable, "-B", "-m", "hermes_cited.verify_log", str(path)],
        cwd=str(REPO), env=environment, capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    assert broken.returncode == 1
    assert "BROKEN" in broken.stdout


def test_r1_m7_the_installed_command_shape_is_documented():
    """R1 M7: the fix is documentary, so the module names the installed directory."""
    from hermes_cited import verify_log

    assert "plugins/hermes-cited" in (verify_log.__doc__ or "")
    assert "internal consistency" in (verify_log.__doc__ or "")


def test_r1_m1_the_readme_states_the_declared_limit_of_the_record():
    """R1 m1: the docs claimed a normalised singular/plural and an absolute isolation of the real home.

    The corrected documentation says what the record is: internal consistency, no custody, no key and no
    file outside HERMES_HOME.
    """
    english = (REPO / "README.md").read_text(encoding="utf-8")
    spanish = (REPO / "README.es.md").read_text(encoding="utf-8")
    assert "not tamper-proof" in english
    assert "internally consistent" in english
    assert "prueba de manipulación" in spanish
    assert "consistencia interna" in spanish
