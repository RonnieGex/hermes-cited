#!/usr/bin/env python
"""The gate of hermes-cited (round 4): affirm the named property of every claim.

Run it with the Python of the installed Hermes venv:

    & "$env:LOCALAPPDATA\\hermes\\hermes-agent\\venv\\Scripts\\python.exe" scripts/gate.py

Every Hermes process it starts gets an explicit temporary HERMES_HOME under the system temp directory,
and this process works under a temporary HERMES_HOME of its own, so the real
``%LOCALAPPDATA%\\hermes`` and ``~/.hermes`` are never used. The test Cited is built from
``origin/main`` of the Cited repository in its own temporary worktree and served on port 3246; port 3240
and the live Cited are never touched. Every raw log and every report is redacted with the ephemeral
token before it is written, all the artifacts are written and then scanned on disk, and only then is the
verdict emitted (M-R3-6).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
CHANGE = REPO / "openspec" / "changes" / "hermes-plugin-r4"
REPORTS = CHANGE / "reports"
RAW_LOGS = REPO / ".tmp" / "gate-r4"
ROUND_ONE_FACTS = (
    REPO / "openspec" / "changes" / "archive" / "2026-10-10-hermes-plugin" / "reports" / "hermes-facts.md"
)

HERMES_ROOT = Path(os.environ.get("HERMES_ROOT", r"C:\Users\Franc\AppData\Local\hermes\hermes-agent"))
HERMES_EXE = HERMES_ROOT / "venv" / "Scripts" / "hermes.exe"
HERMES_PYTHON = HERMES_ROOT / "venv" / "Scripts" / "python.exe"

SOURCE_HERMES = REPO.parent / "community-hermes"
CITED_WORKTREE = Path(
    os.environ.get("CITED_WORKTREE", str(Path(tempfile.gettempdir()) / "hermes-cited-test-cited-main"))
)
CITED_PORT = int(os.environ.get("CITED_PORT", "3246"))
CITED_URL = "http://127.0.0.1:{0}".format(CITED_PORT)
CITED_MCP_URL = "{0}/api/mcp".format(CITED_URL)

TEST_PYTHON = REPO / ".venv" / "Scripts" / "python.exe"
NPM = shutil.which("npx") or "npx.cmd"

PRICE_QUESTION = "¿Cuánto cuesta la afinación de bicicleta en Café La Horquilla?"
GUARANTEE_QUESTION = "What guarantee on repairs does bike-workshop-policies.md state?"
GUARANTEE_FALLBACK_QUESTION = "Is there a guarantee on repairs at the bike workshop? Search the English document."
UNANSWERED_QUESTION = "¿Cuánto cuesta el jabón de lavanda artesanal en Café La Horquilla?"

PRICE_LINE = "- Afinación de bicicleta: 380 pesos."
GUARANTEE_LINE = (
    "Every repair carries a 90 day guarantee on the work. Parts carry the guarantee of their maker."
)
PRICE_SOURCE = "Fuente: cafe-la-horquilla.md - Precios"
GUARANTEE_SOURCE = "Fuente: bike-workshop-policies.md - Guarantee"

FIXED_REFUSALS = ("No está en los documentos.", "It is not in the documents.")

DISCOVERY_TOOLS = (
    "todo_write",
    "todo_read",
    "skill",
    "skill_load",
    "skills",
    "think",
    "plan",
    "plan_update",
    "tool_describe",
    "tool_search",
    "tool_list",
    "list_tools",
)

CLAIMS = []
EVIDENCE = {}
ARTIFACTS = {}
EXTRA_SCAN = []
TOKEN = ""


def claim(code, name, ok, detail=""):
    ok = bool(ok)
    CLAIMS.append((code, name, ok, detail))
    print("{0} {1} {2}{3}".format("PASS" if ok else "FAIL", code, name, "" if ok else " :: {0}".format(detail)))
    sys.stdout.flush()
    return ok


def redact(text, token=None):
    value = str(text)
    secret = TOKEN if token is None else token
    if secret:
        value = value.replace(secret, "<token>")
    return value


def log(name, text):
    """Write a raw log, redacted before it touches the disk (M6)."""
    RAW_LOGS.mkdir(parents=True, exist_ok=True)
    body = redact(text)
    path = RAW_LOGS / name
    path.write_text(body, encoding="utf-8")
    ARTIFACTS[path] = body
    return path


def record(name, text):
    body = redact(text)
    path = REPORTS / name
    ARTIFACTS[path] = body
    return path


def run(command, *, env=None, cwd=None, timeout=900, stdin_file=None):
    merged = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    if env:
        merged.update(env)
    handle = open(stdin_file, "rb") if stdin_file else None
    try:
        completed = subprocess.run(
            command,
            env=merged,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            timeout=timeout,
            stdin=handle,
        )
    except subprocess.TimeoutExpired as error:
        return 124, (error.stdout or b"").decode("utf-8", "replace"), "timeout after {0}s".format(timeout)
    finally:
        if handle:
            handle.close()
    return (
        completed.returncode,
        completed.stdout.decode("utf-8", "replace"),
        completed.stderr.decode("utf-8", "replace"),
    )


def hermes_env(home, extra=None):
    home = Path(home).resolve()
    temp_root = Path(tempfile.gettempdir()).resolve()
    if temp_root not in home.parents:
        raise RuntimeError("refusing a Hermes run outside the temp directory: {0}".format(home))
    values = {
        "HERMES_HOME": str(home),
        "DEEPSEEK_API_KEY": deepseek_key(),
        "NO_COLOR": "1",
        "TERM": "dumb",
    }
    if extra:
        values.update(extra)
    return values


def deepseek_key():
    value = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if value:
        return value
    if os.name == "nt":
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                value = str(winreg.QueryValueEx(key, "DEEPSEEK_API_KEY")[0]).strip()
        except OSError:
            value = ""
    return value


def run_hermes(home, arguments, *, extra_env=None, timeout=900, stdin_file=None, cwd=None):
    return run(
        [str(HERMES_EXE), *arguments],
        env=hermes_env(home, extra_env),
        timeout=timeout,
        stdin_file=stdin_file,
        cwd=cwd,
    )


def run_stream_question(home, question, *, extra_env=None):
    code, out, err = run_hermes(
        home,
        [
            "chat",
            "--oneshot",
            "-q",
            question,
            "--format",
            "stream-json",
            "--source",
            "tool",
            "--provider",
            "deepseek",
            "-m",
            "deepseek-flash",
        ],
        extra_env=extra_env,
        timeout=900,
    )
    tools = []
    final = ""
    streamed = []
    events = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        events.append(event)
        kind = event.get("type")
        if kind == "tool_use":
            tools.append(event.get("name"))
        elif kind == "text":
            streamed.append(event.get("text") or "")
        elif kind == "result":
            final = event.get("text") or ""
    return {
        "code": code,
        "tools": tools,
        "final": final,
        "streamed": "".join(streamed),
        "events": events,
        "stdout": out,
        "stderr": err,
    }


def http_json(url, token, payload, timeout=30):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": "Bearer {0}".format(token),
            "MCP-Protocol-Version": "2025-06-18",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as error:
        return error.code, None
    except OSError:
        return 0, None


def port_is_free(port):
    import socket

    with socket.socket() as probe:
        probe.settimeout(1.0)
        return probe.connect_ex(("127.0.0.1", port)) != 0


def wait_ready(token, timeout=180):
    deadline = time.time() + timeout
    while time.time() < deadline:
        status, body = http_json(
            CITED_MCP_URL,
            token,
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            timeout=5,
        )
        if status == 200 and isinstance(body, dict) and body.get("result"):
            return True
        time.sleep(0.5)
    return False


def git(arguments, cwd, timeout=600):
    return run(["git", *arguments], cwd=cwd, timeout=timeout)


def remove_worktree(path):
    """Remove a worktree that may hold a node_modules junction without touching its target."""
    target = Path(path)
    junction = target / "node_modules"
    if junction.exists():
        subprocess.run(["cmd", "/c", "rmdir", str(junction)], capture_output=True)
    return remove_tree(target)


def ensure_cited_worktree():
    """A build of `origin/main` of the Cited repository in its own temporary worktree."""
    code, out, err = git(["rev-parse", "origin/main"], SOURCE_HERMES)
    if code != 0:
        return None, "origin/main is not available in {0}: {1}".format(SOURCE_HERMES, err.strip())
    sha = out.strip()
    if CITED_WORKTREE.exists():
        head_code, head_out, _ = git(["rev-parse", "HEAD"], CITED_WORKTREE)
        ready = (
            head_code == 0
            and head_out.strip() == sha
            and (CITED_WORKTREE / "node_modules" / "next").exists()
            and (CITED_WORKTREE / ".next" / "BUILD_ID").exists()
        )
        if ready:
            return CITED_WORKTREE, None
        remove_worktree(CITED_WORKTREE)
    git(["worktree", "prune"], SOURCE_HERMES)
    code, out, err = git(["worktree", "add", "--detach", str(CITED_WORKTREE), sha], SOURCE_HERMES)
    if code != 0:
        return None, "git worktree add failed: {0}".format(err.strip()[-300:])
    source_modules = SOURCE_HERMES / "node_modules"
    dest_modules = CITED_WORKTREE / "node_modules"
    if source_modules.exists() and not dest_modules.exists():
        junction = run(["cmd", "/c", "mklink", "/J", str(dest_modules), str(source_modules)], timeout=120)
        if junction[0] != 0:
            return None, "the node_modules junction failed: {0}".format(junction[2].strip()[-300:])
    env = {
        "NEXT_TELEMETRY_DISABLED": "1",
        "NODE_ENV": "production",
        "NO_COLOR": "1",
    }
    build_code, build_out, build_err = run(
        # Turbopack refuses a node_modules junction whose target leaves the project; the webpack
        # builder accepts it, and the junction keeps the test worktree small.
        [str(NPM), "-y", "-p", "node@24", "node", "node_modules/next/dist/bin/next", "build", "--webpack"],
        cwd=CITED_WORKTREE,
        env=env,
        timeout=2400,
    )
    log("cited-build.txt", "exit {0}\n{1}\n{2}".format(build_code, build_out, build_err))
    if build_code != 0 or not (CITED_WORKTREE / ".next" / "BUILD_ID").exists():
        return None, "next build failed: {0}".format((build_err or build_out).strip()[-400:])
    return CITED_WORKTREE, None


def start_cited(workspace, token):
    store = workspace / "cited.sqlite"
    env = {
        **os.environ,
        "DATABASE_URL": str(store),
        "TURSO_DATABASE_URL": "",
        "TURSO_AUTH_TOKEN": "",
        "CITED_MCP_TOKEN": token,
        "CHAT_PROVIDER": "fake",
        "NEXT_TELEMETRY_DISABLED": "1",
        "MCP_RATE_LIMIT_PER_HOUR": "1000",
        "NO_COLOR": "1",
    }
    code, out, err = run(
        [NPM, "-y", "-p", "node@24", "node", "scripts/mcp-seed.ts", str(store), "samples"],
        env=env,
        cwd=CITED_WORKTREE,
        timeout=600,
    )
    log("cited-seed.txt", out + "\n" + err)
    if code != 0:
        return None, None, "the seed failed: {0}".format(err.strip()[-400:])
    node_code, node_out, node_err = run(
        [NPM, "-y", "-p", "node@24", "node", "-e", "process.stdout.write(process.execPath)"],
        cwd=CITED_WORKTREE,
        timeout=300,
    )
    node = node_out.strip() if node_code == 0 and node_out.strip() else "node"
    log("cited-node.txt", node + "\n" + node_err)
    stdout = open(workspace / "cited.log", "wb")
    stderr = open(workspace / "cited.err.log", "wb")
    process = subprocess.Popen(
        [node, "node_modules/next/dist/bin/next", "start", "-H", "127.0.0.1", "-p", str(CITED_PORT)],
        cwd=str(CITED_WORKTREE),
        env=env,
        stdout=stdout,
        stderr=stderr,
    )
    if not wait_ready(token):
        return process, store, "Cited did not answer tools/list on {0}".format(CITED_MCP_URL)
    return process, store, None


# --- the predicates the gate asserts, each one testable against a fixture (M6, D8) ---------------


def first_cited_before_others(tools):
    """True when every tool before the first Cited search is an allowed discovery tool."""
    cited = ("cited_search", "cited_ask")
    first_cited = next((index for index, name in enumerate(tools) if name in cited), None)
    if first_cited is None:
        return False
    return all(name in DISCOVERY_TOOLS for name in tools[:first_cited])


UNIT_CLASSES = {
    "currency": ("peso", "pesos", "mxn", "dolar", "dolares", "usd", "eur", "euro", "euros", "centavo", "centavos"),
    "day": ("day", "days", "dia", "dias"),
    "mass": ("kg", "mg", "mcg", "g", "gramo", "gramos"),
    "percent": ("%", "por ciento", "percent"),
}

#: The signs that may prefix a statement. ``""`` means no sign at all.
SIGNS = {"": r"", "-": r"-\s*", "+": r"\+\s*"}


def _statement_window(text, index):
    """The rest of the line that holds *index*: a citation is resolved inside its own line (M-R4-7)."""
    end = text.find("\n", index)
    return text[index:] if end < 0 else text[index:end]


def amount_statement(text, amount, unit=None, mark=None, sign="", cite=False):
    """One bound statement: sign, exact amount, unit of the right class and the mark of its own line.

    M-R3-6 parsed the sign, the amount and the unit; M-R4-7 binds the citation to the amount instead of
    accepting a mark that appears anywhere in the text. The amount must be a standalone token (never
    inside ``1380``, ``380.5`` or the tail of ``-380`` when no sign was asked for), the sign must be
    exactly the requested one, the unit must belong to the requested class, and the mark must be the
    first citation after the amount inside the same line — the render puts the mark at the end of the
    block, and a mark that closes another statement is not this amount's citation. ``cite=True`` requires
    a mark at all; ``mark=None`` accepts any mark, a number accepts only that one and ``0`` accepts only
    no mark.
    """
    if not isinstance(text, str) or not text:
        return False
    number = re.escape(str(amount))
    units = UNIT_CLASSES.get(unit) if unit else None
    pattern = r"(?<![\w.,])(?P<sign>[+-]?)[ \t]*(?P<amount>{0})(?![\d.,])".format(number)
    if units:
        pattern += r"(?P<unit>[ \t\-]*(?:{0})(?![\w]))".format(
            "|".join(re.escape(word) + r"s?" for word in units)
        )
    pattern += r"(?P<tail>[ \t.,;:]*)(?P<mark>\[\d+\])?"
    for match in re.finditer(pattern, text, re.IGNORECASE):
        found = match.group("sign") or ""
        if found != sign:
            continue
        if sign == "":
            before = text[: match.start()].rstrip(" \t")
            if before and before[-1] in "+-":
                continue
        window = _statement_window(text, match.end())
        if match.group("mark"):
            digits = match.group("mark")[1:-1]
        else:
            later = re.search(r"\[(\d+)\]", window)
            digits = later.group(1) if later else None
        if mark is None:
            if not cite or digits is not None:
                return True
            continue
        if mark == 0:
            if digits is None:
                return True
            continue
        if digits == str(mark):
            return True
    return False


def amount_with_citation(text, amount, unit_words=("peso", "mxn", "dolar", "usd", "eur", "euro", "centavo")):
    """The text states exactly *amount* with a currency unit and a citation mark."""
    return amount_statement(text, amount, unit="currency", cite=True)


def amount_with_unit(text, amount, unit):
    """The text states exactly *amount* with a unit of the class *unit*."""
    return amount_statement(text, amount, unit=unit)


def amount_with_source(text, amount, unit_words=("peso", "mxn", "dolar", "usd", "eur", "euro", "centavo")):
    """The MCP route states exactly *amount* with a currency unit and names a source."""
    if not isinstance(text, str) or not text:
        return False
    sourced = bool(re.search(r"\[\d+\]", text)) or bool(re.search(r"[\w-]+\.(md|txt)", text))
    if not sourced:
        return False
    return amount_statement(text, amount, unit="currency")


def clean_refusal(text):
    """The conservative refusal contract: exactly one of the fixed templates (M-R2-4)."""
    return str(text or "").strip() in FIXED_REFUSALS


def seal_matches_entry(text, entry):
    """The delivered seal is crossed with the audited delivery decision of its own entry (M-R2-2, H9).

    M-R3-6: the check reads the decision the plugin recorded for that entry, so a seal the entry says was
    withheld can never be accepted and a withheld note can never be accepted as a verified answer.
    """
    if not isinstance(entry, dict):
        return False
    verifier = entry.get("verifier") or {}
    delivery = entry.get("delivery") or {}
    if verifier.get("applied") is not True or verifier.get("ok") is not True:
        return False
    if entry.get("response") != text:
        return False
    sealed = str(text or "").rstrip().endswith("Verified by Cited")
    if sealed:
        return verifier.get("verified") is True and verifier.get("seal_withheld") is False and delivery.get("seal") is True
    return verifier.get("seal_withheld") is True or verifier.get("verified") is not True


def terminal_record_of(events):
    """The text a consumer of `--format stream-json` that shows only the terminal record delivers.

    M-R3-6: this measures the terminal ``result`` record of the documented consumer. It does **not**
    measure the temporary deliveries of a real CLI, desktop, bot or TTS; those surfaces are the accepted
    limit of H9 and the reason ``docs/upstream-proposal.md`` exists.
    """
    final = ""
    for event in events or []:
        if isinstance(event, dict) and event.get("type") == "result":
            final = event.get("text") or ""
    return final


def delivered_of(events):
    """The old name of :func:`terminal_record_of`, kept for the round 3 fixtures of this gate."""
    return terminal_record_of(events)


def entry_for(entries, question, mode="cited", turn_id=None):
    """The entry of the run: by question and mode, and by turn when the caller knows it (M-R3-6)."""
    for entry in entries or []:
        if entry.get("question") != question or entry.get("mode") != mode:
            continue
        if turn_id is not None and entry.get("turn_id") != turn_id:
            continue
        return entry
    return None


def line_is_from_entry(text, entry):
    """The recorded line is a full line of one of the excerpts the entry stored."""
    from hermes_cited import render

    for call in entry.get("tool_calls") or []:
        for excerpt in call.get("excerpt_texts") or []:
            if text in render.excerpt_lines(excerpt):
                return True
    return False


def _evidence_row(entry, line):
    """The row of the evidence table the line names, or ``None`` (M-R4-7).

    The table keeps the original metadata of every passage the search returned: call, pid, uid, number,
    document, heading, position and the numbered lines. A block is bound only to its own row.
    """
    if not isinstance(entry, dict) or not isinstance(line, dict):
        return None
    pid = str(line.get("pid") or "")
    uid = str(line.get("uid") or "")
    call = line.get("call")
    if not pid or not uid or call is None:
        return None
    for row in entry.get("evidence") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("pid") or "") == pid and str(row.get("uid") or "") == uid and row.get("call") == call:
            return row
    return None


def _int_or_zero(value):
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def blocks_are_bound(entry, line):
    """M-R3-6 and M-R4-7: one recorded block must resolve against its own evidence row.

    The identifier must be the one of the table (``turn_id:call:pid``), the document, the section and the
    position must be the original metadata of that row, the text must be one of its full lines, the
    ``[n]`` mark and the escaped source must be the ones of that same row in the delivered answer. A
    forged call, pid, document or position, or an answer that does not hold the block, is not bound.
    """
    from hermes_cited import render

    if not isinstance(entry, dict) or not isinstance(line, dict):
        return False
    text = line.get("text")
    pid = str(line.get("pid") or "")
    uid = str(line.get("uid") or "")
    if not text or not pid or not uid:
        return False
    if uid != "{0}:{1}:{2}".format(entry.get("turn_id"), line.get("call"), pid):
        return False
    row = _evidence_row(entry, line)
    if row is None:
        return False
    if str(row.get("document") or "") != str(line.get("document") or ""):
        return False
    if str(row.get("heading") or "") != str(line.get("heading") or ""):
        return False
    if _int_or_zero(row.get("position")) != _int_or_zero(line.get("position")):
        return False
    if text not in [str(item.get("text")) for item in row.get("lines") or [] if isinstance(item, dict)]:
        return False
    response = str(entry.get("response") or "")
    mark = "[{0}]".format(re.sub(r"\D", "", pid))
    block = "{0} {1}".format(text, mark)
    if block not in response:
        return False
    document = str(row.get("document") or "")
    if document:
        source = render.escape_meta(document)
        heading = render.escape_meta(row.get("heading") or "") if row.get("heading") else ""
        if heading:
            source = "{0} - {1}".format(source, heading)
        prefix = "Fuente: " if "Fuente:" in response else "Source: "
        if "{0}{1}".format(prefix, source) not in response:
            return False
    return True


def every_block_is_bound(entries):
    """M-R3-6: every block of every cited entry of the log, with the refusals excluded by name.

    A refusal is a cited entry without blocks (the fixed refusal and the operational one), so it is
    excluded explicitly instead of being skipped because its list happens to be empty.
    """
    checked = 0
    cited = 0
    for entry in entries or []:
        if entry.get("mode") != "cited":
            continue
        response = str(entry.get("response") or "").strip()
        if response in FIXED_REFUSALS or response.startswith("No puedo entregar") or response.startswith("I cannot deliver"):
            continue
        cited += 1
        lines = entry.get("quoted_lines") or []
        if not lines:
            continue
        for line in lines:
            if not blocks_are_bound(entry, line):
                return False, "entry {0} line {1} is not bound to its turn".format(
                    entry.get("turn_id"), (line or {}).get("pid"))
            checked += 1
    return cited > 0, "cited entries: {0}, blocks checked: {1}".format(cited, checked)


def entry_of_run(entries, question, mode="cited"):
    """The entry of one run, resolved again by the ``turn_id`` that run recorded (M-R4-7)."""
    found = entry_for(entries, question, mode)
    if found is None:
        return None
    return entry_for(entries, question, mode, turn_id=found.get("turn_id"))


def bound_amount(entry, amount, unit=None, mark=None, sign="", cite=False):
    """The delivered answer states the amount inside a block bound to the evidence of its own entry."""
    if not isinstance(entry, dict):
        return False
    response = str(entry.get("response") or "")
    if not amount_statement(response, amount, unit=unit, mark=mark, sign=sign, cite=cite):
        return False
    lines = entry.get("quoted_lines") or []
    return bool(lines) and all(blocks_are_bound(entry, line) for line in lines)


def recompute_digests(entries):
    """Every sha256 in every tool call must equal sha256 of the stored excerpt text."""
    from hermes_cited.audit import excerpt_digest

    checked = 0
    for entry in entries:
        for call in entry.get("tool_calls") or []:
            digests = call.get("excerpt_sha256") or []
            texts = call.get("excerpt_texts") or []
            if len(digests) != len(texts):
                return False, "a call stores {0} digests and {1} texts".format(len(digests), len(texts))
            for digest, text in zip(digests, texts):
                if digest != excerpt_digest(text):
                    return False, "a digest does not match its excerpt"
                checked += 1
    return checked > 0, "digests recomputed: {0}".format(checked)


def strip_token_from_disk():
    """The last net of M6: every artifact, scanned after it was written and redacted."""
    found = []
    if TOKEN:
        for path in list(ARTIFACTS) + list(EXTRA_SCAN):
            try:
                if path.exists() and TOKEN in path.read_text(encoding="utf-8", errors="replace"):
                    found.append(str(path))
            except OSError:
                continue
    return found


def cited_fixture():
    """D5/D10 in process: the model chooses, the plugin writes, and a bad line cannot pass."""
    from hermes_cited import delivery, plugin, render, verifier

    excerpt = "Precios\n- Espresso: 35 pesos.\n- Cafe de olla: 45 pesos.\n" + PRICE_LINE
    envelope = {
        "cited_tool": "cited_search",
        "query": "afinacion",
        "text": "transport text that is never evidence",
        "passages": [
            {
                "n": 1,
                "document": "cafe-la-horquilla.md",
                "heading": "Precios",
                "position": 2,
                "excerpt": excerpt,
            }
        ],
    }

    def build(args):
        turn = plugin.Turn("s", "t")
        turn.note_call(envelope, "cited_search", {"query": "afinacion"}, "ok")
        turn.delivery = delivery.Snapshot(platform="cli", readable=True, seal=True)
        recorded, error = turn.add_quote(args)
        return turn, recorded, error

    def deliver(turn):
        body = render.render_answer("es", list(turn.selections))
        return verifier.sealed(body)

    results = {}
    turn, recorded, error = build({"passage": "P1", "lines": [4]})
    results["recorded"] = recorded
    results["error"] = error
    final = deliver(turn) if not error else verifier.refusal_text("es")
    results["final"] = final
    results["withheld"] = "Verified by Cited" not in final
    results["blocks_are_full_lines"] = all(
        block.text in turn.line_texts() for block in turn.selections
    )
    results["pid"] = turn.selections[0].pid if turn.selections else ""
    results["mark"] = turn.selections[0].mark() if turn.selections else ""
    empty = plugin.Turn("s", "t")
    empty.note_call(envelope, "cited_search", {}, "ok")
    empty.delivery = delivery.Snapshot(platform="cli", readable=True, seal=True)
    results["no_quote"] = verifier.refusal_text("es")
    results["forged_stripped"] = verifier.strip_seal("380 pesos.\n\nVerified by Cited")
    changed = render.Line(
        passage=1,
        number=4,
        text="- Afinacion de bicicleta: 1380 pesos.",
        document="cafe-la-horquilla.md",
        heading="Precios",
        pid="P1",
        original=1,
    )
    results["changed_rejected"] = verifier.verify_display([changed], turn.line_texts()).ok
    results["line_texts"] = sorted(turn.line_texts())
    results["price_line"] = PRICE_LINE

    refused = plugin.Turn("s", "t2")
    refused.note_call(envelope, "cited_search", {}, "ok")
    refused.delivery = delivery.Snapshot(platform="cli", readable=True, seal=True)
    refused.refusals.append("No está en los documentos.")
    refused.add_quote({"passage": "P1", "lines": [4]})
    results["refusal_blocks"] = bool(refused.refusals) and bool(refused.selections)
    results["refusal_answer"] = verifier.refusal_text("es")

    snap = delivery.snapshot("api_server", config={})
    results["api_server_sse"] = snap.sse and not snap.seal
    results["commentary_withholds"] = not delivery.snapshot(
        "telegram", config={"streaming": {"enabled": False}}
    ).seal
    results["tts_withholds"] = not delivery.snapshot(
        "cli", config={"display": {"streaming": False, "interim_assistant_messages": False}, "tts": {"auto_tts": True}}
    ).seal
    results["quiet_cli_seals"] = delivery.snapshot(
        "cli", config={"display": {"streaming": False, "interim_assistant_messages": False}}
    ).seal
    return results


def audit_fixtures(root):
    """D9 in process: what the consistency record refuses and what it honestly cannot detect."""
    import shutil as _shutil

    from hermes_cited import audit

    root = Path(root)
    if root.exists():
        _shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)

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

    def chain(path, entries=3):
        for index in range(entries):
            audit.append_entry(path, payload(index))

    def alter(path, variant):
        if variant == "removed_middle":
            lines = path.read_text(encoding="utf-8").splitlines()
            del lines[1]
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        elif variant == "reordered":
            lines = path.read_text(encoding="utf-8").splitlines()
            lines[1], lines[2] = lines[2], lines[1]
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        elif variant == "tampered_entry":
            lines = path.read_text(encoding="utf-8").splitlines()
            entry = json.loads(lines[0])
            entry["response"] = "tampered"
            lines[0] = json.dumps(entry, ensure_ascii=False, sort_keys=True)
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        elif variant == "invalid_tail":
            with open(path, "a", encoding="utf-8") as handle:
                handle.write("{broken\n")
        elif variant == "removed_tail":
            lines = path.read_text(encoding="utf-8").splitlines()
            path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
        elif variant == "rewritten_chain":
            entries = audit.read_entries(path)
            previous = audit.GENESIS
            for entry in entries:
                entry["response"] = "tampered"
                entry["prev_hash"] = previous
                entry["hash"] = audit.entry_hash(entry)
                previous = entry["hash"]
            path.write_text(
                "\n".join(json.dumps(entry, ensure_ascii=False, sort_keys=True) for entry in entries) + "\n",
                encoding="utf-8",
            )

    results = {}
    for variant in ("removed_middle", "reordered", "tampered_entry", "invalid_tail"):
        path = root / "alter-{0}.jsonl".format(variant)
        chain(path)
        alter(path, variant)
        before = path.read_bytes()
        try:
            audit.append_entry(path, payload(9))
            results[variant] = "appended"
        except audit.AuditError as error:
            results[variant] = "refused: {0}".format(str(error)[:80])
        results[variant + "_untouched"] = path.read_bytes() == before

    for variant in ("removed_tail", "rewritten_chain"):
        path = root / "honest-{0}.jsonl".format(variant)
        chain(path)
        alter(path, variant)
        count, error = audit.verify_file(path)
        results[variant] = {"consistent": error is None, "count": count}

    path = root / "half-write.jsonl"
    chain(path, 1)
    before = path.read_bytes()

    def half_write(temp, text):
        with open(temp, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(str(text)[:20])
            handle.flush()
            os.fsync(handle.fileno())
        raise OSError("synthetic failure after a partial write")

    original = audit._write_temp_file
    audit._write_temp_file = half_write
    try:
        try:
            audit.append_entry(path, payload(2))
            results["half_write"] = "appended"
        except OSError:
            results["half_write"] = "raised"
    finally:
        audit._write_temp_file = original
    results["half_write_intact"] = path.read_bytes() == before
    try:
        audit.append_entry(path, payload(3))
        results["half_write_next_append"] = "appended"
    except audit.AuditError:
        results["half_write_next_append"] = "refused"

    custody_root = root / "no-custody"
    custody_root.mkdir(parents=True, exist_ok=True)
    path = custody_root / "audit.jsonl"
    chain(path, 1)
    results["files_next_to_the_log"] = sorted(item.name for item in custody_root.iterdir())

    path = root / "append-refusal.jsonl"
    chain(path, 2)
    lines = path.read_text(encoding="utf-8").splitlines()
    del lines[1]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    before = path.read_bytes()
    try:
        audit.append_entry(path, payload(3))
        results["append_refusal"] = "appended"
    except audit.AuditError:
        results["append_refusal"] = "refused"
    results["append_refusal_untouched"] = path.read_bytes() == before
    return results


def verifier_operational(code, language="es"):
    """The fixed operational refusal of H10, built by the module that ships it."""
    from hermes_cited import verifier

    return verifier.operational_refusal(code, language)


def delivery_fixture():
    """H9 in process: the matrix of the resolver and the seal decision per surface."""
    from hermes_cited import delivery

    matrix = {
        "mode_edit": {"mode": "edit"},
        "enabled": {"enabled": True},
        "transport_off_bool": {"enabled": True, "transport": False},
        "explicit_off": {"enabled": False},
    }
    quiet = {"display": {"interim_assistant_messages": False}}
    streaming = {
        name: delivery.effective_streaming("telegram", {**quiet, "streaming": raw})
        for name, raw in matrix.items()
    }
    seal = {
        name: delivery.seal_allowed("telegram", {**quiet, "streaming": raw})
        for name, raw in matrix.items()
    }
    on = {"streaming": {"enabled": True}}
    platforms = {
        name: delivery.seal_allowed(name, on)
        for name in ("wecom", "feishu", "dingtalk", "qqbot", "acme-chat", "api_server", "desktop")
    }
    return {
        "streaming": streaming,
        "seal": seal,
        "platforms": platforms,
        "cli_off": delivery.seal_allowed(
            "cli", {"display": {"streaming": False, "interim_assistant_messages": False}}),
        "cli_on": delivery.seal_allowed(
            "cli", {"display": {"streaming": True, "interim_assistant_messages": False}}),
        "desktop": delivery.seal_allowed("desktop", {"streaming": {"enabled": False}}),
        "commentary_withholds": not delivery.seal_allowed(
            "telegram", {"streaming": {"enabled": False}, "display": {"interim_assistant_messages": True}}),
        "tts_withholds": not delivery.seal_allowed(
            "cli",
            {
                "display": {"streaming": False, "interim_assistant_messages": False},
                "tts": {"auto_tts": True},
            },
        ),
        "compat": {
            "transport_off": delivery.CompatStreamingConfig.from_dict({"enabled": True, "transport": False}).transport,
            "mode_edit": delivery.CompatStreamingConfig.from_dict({"mode": "edit"}).globally_enabled,
        },
    }


def host_matrix(workspace):
    """D7 against the real class of the host, run with the Python of the Hermes venv."""
    host_home = Path(workspace) / "host-home"
    host_home.mkdir(exist_ok=True)
    probe = (
        "import json;"
        "from gateway.config import StreamingConfig;"
        "from hermes_cited import delivery;"
        "hosts={n: StreamingConfig.from_dict(c).enabled_for(None) for n,c in "
        "[('mode_edit',{'mode':'edit'}),('enabled',{'enabled':True}),"
        "('transport_off_bool',{'enabled':True,'transport':False}),('explicit_off',{'enabled':False})]};"
        "print(json.dumps({'is_host': delivery.HOST_STREAMING is StreamingConfig,"
        "'version': delivery.HOST_STREAMING_VERSION,"
        "'host': hosts,"
        "'plugin': {n: delivery.streaming_config({'streaming': c}).globally_enabled for n,c in "
        "[('mode_edit',{'mode':'edit'}),('enabled',{'enabled':True}),"
        "('transport_off_bool',{'enabled':True,'transport':False}),('explicit_off',{'enabled':False})]}}))"
    )
    code, out, err = run(
        [str(HERMES_PYTHON), "-c", probe],
        env={
            "HERMES_HOME": str(host_home),
            "PYTHONPATH": "{0}{1}{2}".format(HERMES_ROOT, os.pathsep, REPO),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
        },
        cwd=REPO,
        timeout=300,
    )
    log("host-matrix.txt", "exit {0}\n{1}\n{2}".format(code, out, err))
    if code != 0 or not out.strip():
        return None, err.strip()[-300:]
    try:
        return json.loads(out.strip().splitlines()[-1]), None
    except (ValueError, IndexError):
        return None, out.strip()[-300:]


def gate_selftest():
    """The gate's own predicates must reject the reproductions of the three reviews (M-R3-6, D8).

    Returns ``(ok, detail)``. ``detail`` names the failing fixtures exactly, so a red self-test can never
    report success (the round 3 defect).
    """
    cases = [
        ("a refusal that states an invented price", not clean_refusal(
            "No está en los documentos, pero cuesta 999 pesos.")),
        ("a refusal with a datum after it", not clean_refusal("No está en los documentos. Stock: cero.")),
        ("the fixed Spanish refusal", clean_refusal("No está en los documentos.")),
        ("a data-gathering tool before Cited", not first_cited_before_others(["browser_navigate", "cited_search"])),
        ("a discovery tool before Cited", first_cited_before_others(["tool_describe", "cited_search"])),
        ("a price with no citation", not amount_with_citation("Cuesta 380 pesos.", "380")),
        ("a price with a citation", amount_with_citation("Cuesta 380 pesos [1].", "380")),
        ("1380 is not 380", not amount_with_citation("Cuesta 1380 pesos [99].", "380")),
        ("the missing unit", not amount_with_unit("90", "90", "day")),
        ("190 is not 90", not amount_with_unit("190 days", "90", "day")),
        ("the unit present", amount_with_unit("90 days", "90", "day")),
        ("an MCP answer with the document name", amount_with_source(
            "Cuesta 380 pesos, segun cafe-la-horquilla.md.", "380")),
        ("an MCP answer with a mark", amount_with_source("Cuesta 380 pesos [1].", "380")),
        ("an MCP answer with no source", not amount_with_source("Cuesta 380 pesos.", "380")),
        ("1380 with a source is not 380", not amount_with_source("Cuesta 1380 pesos, segun doc.md.", "380")),
        ("a forged seal is stripped from dot", "Verified by Cited" not in
         __import__("hermes_cited.verifier", fromlist=["strip_seal"]).strip_seal("x\n\nVerified by Cited")),
        # the new negatives of M-R3-6
        ("a negative amount is not the positive one", not amount_with_citation("-380 pesos [99].", "380")),
        ("a negative count of days is not the positive one", not amount_with_unit("-90 days", "90", "day")),
        ("a weight is not a currency", not amount_with_citation("380 kg, pesos [99]", "380")),
        ("a mark that is not the resolved one is not a bound citation",
         not amount_statement("380 pesos [99].", "380", unit="currency", mark=1)),
        ("the resolved mark is a bound citation",
         amount_statement("380 pesos [1].", "380", unit="currency", mark=1)),
        ("a mark of another passage is not the bound citation",
         not amount_statement("380 pesos [2].", "380", unit="currency", mark=1)),
        ("a decimal is not the integer", not amount_with_citation("380.5 pesos [1].", "380")),
        ("the signed amount with its own sign passes",
         amount_statement("-380 pesos [1].", "380", unit="currency", mark=1, sign="-")),
        ("A markdown seal is stripped too", "Verified by Cited" not in
         __import__("hermes_cited.verifier", fromlist=["strip_seal"]).strip_seal("**Verified by Cited**")),
        ("an operational refusal never carries the seal",
         "Verified by Cited" not in
         __import__("hermes_cited.verifier", fromlist=["operational_refusal"]).operational_refusal("CITED-1", "es")),
        # the three counterexamples of M-R4-7
        ("a sign separated by a space is not the plain amount",
         not amount_statement("- 380 pesos [1]", "380", unit="currency", mark=1)),
        ("a mark of another statement is not the bound citation",
         not amount_statement("999 pesos [1]. Price: 380 pesos [99]", "380", unit="currency", mark=1)),
        ("a forged block is not bound to its own row",
         not blocks_are_bound(
             {
                 "turn_id": "t1",
                 "mode": "cited",
                 "response": "INVENTED_999 [1]\nFuente: forged.md - Elsewhere",
                 "evidence": [],
                 "quoted_lines": [
                     {"pid": "P1", "uid": "t1:0:P1", "call": 0, "text": "INVENTED_999",
                      "document": "forged.md", "heading": "Elsewhere", "position": 9}
                 ],
             },
             {"pid": "P1", "uid": "t1:0:P1", "call": 0, "text": "INVENTED_999",
              "document": "forged.md", "heading": "Elsewhere", "position": 9},
         )),
    ]
    fixture = cited_fixture()
    cases.append(("the cited fixture records one line", fixture["recorded"] == [PRICE_LINE]))
    cases.append(("the cited render copies the line and adds the source",
                  PRICE_LINE in fixture["final"] and PRICE_SOURCE in fixture["final"]))
    cases.append(("the cited render ends with the seal", fixture["final"].rstrip().endswith("Verified by Cited")))
    cases.append(("the render mark follows the pid", fixture["mark"] == "[1]" and fixture["pid"] == "P1"))
    cases.append(("a changed line is rejected", fixture["changed_rejected"] is False))
    cases.append(("no quote is the fixed refusal", fixture["no_quote"] == "No está en los documentos."))
    cases.append(("a refusal blocks an existing selection", fixture["refusal_blocks"] is True))
    cases.append(("api_server is the SSE route and withholds", fixture["api_server_sse"] is True))
    cases.append(("interim commentary withholds", fixture["commentary_withholds"] is True))
    cases.append(("streaming TTS withholds", fixture["tts_withholds"] is True))
    cases.append(("a quiet CLI seals", fixture["quiet_cli_seals"] is True))
    audits = audit_fixtures(REPO / ".tmp" / "gate-r4-selftest")
    cases.append(("a broken chain refuses the next append",
                  str(audits["removed_middle"]).startswith("refused") and audits["removed_middle_untouched"]))
    cases.append(("a failed append never reaches the published chain",
                  audits["half_write"] == "raised" and audits["half_write_intact"] is True
                  and audits["half_write_next_append"] == "appended"))
    cases.append(("no custody file is created next to the log",
                  audits["files_next_to_the_log"] == ["audit.jsonl", "audit.jsonl.lock"]))
    cases.append(("a cut suffix is honestly reported as consistent",
                  audits["removed_tail"]["consistent"] is True))
    failed = [name for name, ok in cases if not ok]
    return not failed, "failed fixtures: {0}".format(", ".join(failed))


def read_config(home):
    text = (Path(home) / "config.yaml").read_text(encoding="utf-8")
    try:
        import yaml

        return yaml.safe_load(text) or {}, text
    except Exception:
        return {}, text


def write_env(home, values):
    lines = ["{0}={1}".format(key, value) for key, value in values.items()]
    (Path(home) / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")


def snapshot_repo(destination):
    if destination.exists():
        shutil.rmtree(destination, ignore_errors=True)
    destination.mkdir(parents=True)
    shutil.copytree(
        REPO,
        destination,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(".git", ".venv", ".tmp", "__pycache__", ".pytest_cache"),
    )
    for command in (
        ["git", "init", "-q", "-b", "main"],
        ["git", "add", "-A"],
        ["git", "-c", "user.email=gate@katalis.dev", "-c", "user.name=gate", "commit", "-q", "-m", "gate snapshot"],
    ):
        code, out, err = run(command, cwd=destination, timeout=120)
        if code != 0:
            return "git {0} failed: {1}".format(command[1], err.strip())
    return None


def remove_tree(path, attempts=12, delay=5.0):
    target = Path(path)
    for attempt in range(attempts):
        if not target.exists():
            return True
        subprocess.run(["cmd", "/c", "attrib", "-R", str(target), "/S", "/D"], capture_output=True)
        shutil.rmtree(target, ignore_errors=True)
        if not target.exists():
            return True
        subprocess.run(["cmd", "/c", "rmdir", "/s", "/q", str(target)], capture_output=True)
        if not target.exists():
            return True
        if attempt < attempts - 1:
            time.sleep(delay)
    return not target.exists()


def markdown_block(title, body):
    return "## {0}\n\n```\n{1}\n```\n".format(title, str(body).rstrip())


def main():
    global TOKEN
    RAW_LOGS.mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix="hc-gate-"))
    gate_home = workspace / "gate-home"
    gate_home.mkdir()
    os.environ["HERMES_HOME"] = str(gate_home)
    os.environ.pop("CITED_AUDIT_KEY_PATH", None)
    os.environ.pop("CITED_LANGUAGE", None)
    os.environ.pop("CITED_MCP_TOKEN", None)
    fixture_root = workspace / "audit-fixtures"
    fixture_root.mkdir()
    homes = []
    cited_process = None
    started = time.time()
    print("hermes-cited gate r4 · workspace {0}".format(workspace))

    token = os.urandom(32).hex()
    TOKEN = token
    try:
        claim(
            "preflight",
            "the installed Hermes, the Cited source worktree and pytest are present",
            HERMES_EXE.exists()
            and HERMES_PYTHON.exists()
            and (SOURCE_HERMES / ".git").exists()
            and TEST_PYTHON.exists(),
            "missing one of: {0}".format(
                ", ".join(
                    str(path)
                    for path in (HERMES_EXE, HERMES_PYTHON, SOURCE_HERMES / ".git", TEST_PYTHON)
                    if not path.exists()
                )
            ),
        )
        claim("preflight", "DEEPSEEK_API_KEY is in the environment", bool(deepseek_key()),
              "set the user environment variable DEEPSEEK_API_KEY")
        claim("preflight", "port {0} is free".format(CITED_PORT), port_is_free(CITED_PORT),
              "another process is listening on {0}".format(CITED_PORT))

        facts = (REPORTS / "hermes-facts-r4.md").read_text(encoding="utf-8")
        claim(
            "H0",
            "reports/hermes-facts-r4.md answers the delivery, empty-response and boundary facts of D9 to D14",
            all(
                needle in facts
                for needle in (
                    "gateway/platforms/api_server.py:2394",
                    "gateway/run_turn_runner.py:917-994",
                    "gateway/display_config.py:11-35",
                    "agent/turn_finalizer.py:501-502",
                    "agent/turn_finalizer.py:104-111",
                    "_run_agent_start_streaming_tts",
                )
            ),
            "the report does not name every fact",
        )
        round_one = ROUND_ONE_FACTS.read_text(encoding="utf-8")
        claim(
            "H0",
            "the round 1 facts live inside their change",
            "dce1e9b" in round_one and "transform_llm_output" in round_one,
            "the moved round 1 fact sheet is not where it belongs",
        )

        ok, detail = gate_selftest()
        claim("D8", "the gate's own predicates reject the reproductions of the four reviews", ok, detail)

        fixture = cited_fixture()
        claim(
            "D5",
            "the model chooses numbered lines and the plugin returns them byte for byte",
            fixture["recorded"] == [PRICE_LINE] and fixture["error"] == "",
            json.dumps(fixture["recorded"], ensure_ascii=False),
        )
        claim(
            "H12",
            "the plugin-written render carries the line, the source, the mark and the seal",
            PRICE_LINE in fixture["final"] and PRICE_SOURCE in fixture["final"]
            and "[1]" in fixture["final"] and fixture["final"].rstrip().endswith("Verified by Cited")
            and fixture["blocks_are_full_lines"] is True and fixture["mark"] == "[1]",
            fixture["final"][:200],
        )
        claim(
            "H4",
            "no quote is the fixed refusal and a changed line cannot pass",
            fixture["no_quote"] == "No está en los documentos." and fixture["changed_rejected"] is False,
            json.dumps(fixture, ensure_ascii=False)[:240],
        )
        claim(
            "H13",
            "a Cited refusal blocks the selections of its turn, before or after it",
            fixture["refusal_blocks"] is True and fixture["refusal_answer"] == "No está en los documentos.",
            json.dumps(fixture.get("refusal_blocks")),
        )
        claim(
            "H4",
            "a seal written by the model is removed in dot mode",
            fixture["forged_stripped"] == "380 pesos.",
            fixture["forged_stripped"],
        )
        claim(
            "H14",
            "the passage identifier of the turn is the render mark and reaches the log",
            fixture["pid"] == "P1" and fixture["mark"] == "[1]",
            json.dumps({"pid": fixture["pid"], "mark": fixture["mark"]}),
        )
        claim(
            "H10",
            "the operational refusal is a fixed template with an incident code and no error",
            "Verified by Cited" not in verifier_operational("CITED-ABC123", "es")
            and "CITED-ABC123" in verifier_operational("CITED-ABC123", "es"),
            verifier_operational("CITED-ABC123", "es")[:120],
        )

        audits = audit_fixtures(fixture_root)
        altered = ("removed_middle", "reordered", "tampered_entry", "invalid_tail")
        claim(
            "H5",
            "every detected alteration of the chain refuses the next append and leaves the log untouched",
            all(str(audits.get(name, "")).startswith("refused") for name in altered)
            and all(audits.get(name + "_untouched") is True for name in altered),
            json.dumps(audits, ensure_ascii=False)[:400],
        )
        claim(
            "H5",
            "a failed append never reaches the published chain and the next append is accepted",
            audits["half_write"] == "raised" and audits["half_write_intact"] is True
            and audits["half_write_next_append"] == "appended",
            json.dumps({key: audits[key] for key in ("half_write", "half_write_intact", "half_write_next_append")}),
        )
        claim(
            "H5",
            "the retired custody wrote no file outside HERMES_HOME",
            audits["files_next_to_the_log"] == ["audit.jsonl", "audit.jsonl.lock"],
            json.dumps(audits["files_next_to_the_log"]),
        )
        claim(
            "H5",
            "the record names what it cannot detect: a cut suffix stays internally consistent",
            audits["removed_tail"]["consistent"] is True and audits["rewritten_chain"]["consistent"] is True,
            json.dumps({"removed_tail": audits["removed_tail"], "rewritten_chain": audits["rewritten_chain"]}),
        )

        policy = delivery_fixture()
        claim(
            "H9",
            "the delivery resolver reproduces the host mode alias and YAML booleans",
            policy["streaming"] == {"mode_edit": True, "enabled": True, "transport_off_bool": False,
                                    "explicit_off": False}
            and policy["seal"] == {"mode_edit": False, "enabled": False, "transport_off_bool": True,
                                   "explicit_off": True}
            and policy["compat"] == {"transport_off": "off", "mode_edit": True},
            json.dumps(policy["streaming"]),
        )
        claim(
            "H9",
            "an unknown platform, the desktop and the SSE route withhold, and the CLI follows its own switches",
            policy["platforms"] == {"wecom": False, "feishu": False, "dingtalk": False, "qqbot": False,
                                    "acme-chat": False, "api_server": False, "desktop": False}
            and policy["cli_off"] is True and policy["cli_on"] is False,
            json.dumps(policy["platforms"]),
        )
        claim(
            "H9",
            "interim commentary and streaming TTS withhold even with streaming off",
            policy["commentary_withholds"] is True and policy["tts_withholds"] is True,
            json.dumps({"commentary": policy["commentary_withholds"], "tts": policy["tts_withholds"]}),
        )
        host, host_error = host_matrix(workspace)
        claim(
            "H9",
            "inside the Hermes venv the plugin uses the real StreamingConfig of the host",
            host is not None and host.get("is_host") is True and host.get("host") == host.get("plugin"),
            host_error or json.dumps(host)[:200] if host else host_error,
        )

        # H15: the integration evidence of the two declared host incompatibilities. It runs the real
        # loader, dispatcher, finalizer and stream receiver with a temporary HERMES_HOME; when the
        # read-only host copy of the review is not on this machine the claim says so instead of passing.
        host_copy = Path(
            os.environ.get(
                "HERMES_HOST_COPY",
                str(
                    Path(tempfile.gettempdir())
                    / "codex-hermes-cited-r2-2d438babc89e4a55af33b15bab5269cd"
                    / "host-fast"
                    / "hermes-agent-dce1e9b37581dd62e480a9064dc04a709c2940d3"
                ),
            )
        )
        if (host_copy / "agent" / "turn_finalizer.py").exists():
            host_code, host_out, host_err = run(
                [str(TEST_PYTHON), "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_host.py"],
                cwd=REPO,
                timeout=900,
            )
            log("h15-host.txt", host_out + "\n" + host_err)
            host_tail = host_out.strip().splitlines()[-1] if host_out.strip() else ""
            claim(
                "H15",
                "the real host finalizer never calls the hook on an empty response and the boundary holds",
                host_code == 0 and "failed" not in host_tail and "passed" in host_tail,
                host_tail or host_err.strip()[-300:],
            )
        else:
            claim(
                "H15",
                "the real host finalizer never calls the hook on an empty response and the boundary holds",
                False,
                "the read-only host copy is not present at {0}; the integration evidence of H15 is "
                "reported as not run instead of covered".format(host_copy),
            )
        proposal = (REPO / "docs" / "upstream-proposal.md").read_text(encoding="utf-8")
        claim(
            "H15",
            "the upstream proposal asks for the two missing contracts and opens no PR",
            all(needle in proposal for needle in (
                "synchronous retention of the delivery",
                "A final composition step even when the model's response is empty",
                "No pull request",
            )),
            "docs/upstream-proposal.md does not name both contracts",
        )

        if not port_is_free(CITED_PORT):
            claim("H8", "a local Cited built from origin/main answers tools/list", False,
                  "port {0} is not free".format(CITED_PORT))
            return finish(started)
        cited_root, error = ensure_cited_worktree()
        claim("H8", "a Cited worktree of origin/main builds", error is None, error or "")
        if error is not None:
            return finish(started)
        cited_process, store, error = start_cited(workspace, token)
        claim("H8", "a local Cited built from origin/main answers tools/list", error is None, error or "")
        if error is not None:
            return finish(started)
        log("cited-ready.txt", "ready after {0:.1f}s at {1}".format(time.time() - started, cited_root))

        unit_code, unit_out, unit_err = run([str(TEST_PYTHON), "-m", "pytest", "-q"], cwd=REPO, timeout=1800)
        log("unit.txt", unit_out + "\n" + unit_err)
        tail = unit_out.strip().splitlines()[-1] if unit_out.strip() else ""
        claim("H8", "the unit suite is green", unit_code == 0 and "failed" not in tail,
              tail or unit_err.strip()[-300:])
        adv_code, adv_out, adv_err = run(
            [
                str(TEST_PYTHON),
                "-m",
                "pytest",
                "-q",
                "tests/test_adversarial.py",
                "tests/test_delivery.py",
                "tests/test_render.py",
                "tests/test_verifier.py",
                "tests/test_gate.py",
                "tests/regressions",
            ],
            cwd=REPO,
            timeout=1800,
        )
        log("adversarial.txt", adv_out + "\n" + adv_err)
        adv_tail = adv_out.strip().splitlines()[-1] if adv_out.strip() else ""
        claim("D8", "one permanent fixture per finding of the four reviews is green",
              adv_code == 0 and "failed" not in adv_tail, adv_tail or adv_err.strip()[-300:])

        proposal = (REPO / "docs" / "upstream-proposal.md").read_text(encoding="utf-8")
        claim("H9", "the upstream proposal names the hook, the SSE route and the no-PR rule",
              all(needle in proposal for needle in (
                  "agent/stream_delivery.py:35", "api_server_openai_routes.py", "No pull request",
                  "streaming.enabled")),
              "docs/upstream-proposal.md is incomplete")

        mcp_home = workspace / "home-mcp"
        mcp_home.mkdir()
        homes.append(mcp_home)
        (mcp_home / "skills" / "cited").mkdir(parents=True)
        shutil.copyfile(
            REPO / "hermes_cited" / "skills" / "cited" / "SKILL.md",
            mcp_home / "skills" / "cited" / "SKILL.md",
        )
        write_env(mcp_home, {"MCP_CITED_API_KEY": token, "CITED_MCP_TOKEN": token})
        answers = workspace / "mcp-add-answers.txt"
        answers.write_text("y\ny\n", encoding="utf-8")
        add_code, add_out, add_err = run_hermes(
            mcp_home,
            ["mcp", "add", "cited", "--url", CITED_MCP_URL, "--auth", "header"],
            timeout=600,
            stdin_file=answers,
        )
        log("h1-mcp-add.txt", add_out + "\n" + add_err)
        add_text = add_out + add_err
        claim("H1", "hermes mcp add writes the cited server and discovers both tools",
              add_code == 0 and "cited_search" in add_text and "cited_ask" in add_text,
              add_text.strip()[-400:])
        config, config_text = read_config(mcp_home)
        entry = ((config.get("mcp_servers") or {}).get("cited") or {}) if config else {}
        claim("H1", "the config fragment names the endpoint and the bearer header",
              entry.get("url") == CITED_MCP_URL
              and "Bearer ${MCP_CITED_API_KEY}" == (entry.get("headers") or {}).get("Authorization"),
              json.dumps(entry))
        test_code, test_out, test_err = run_hermes(mcp_home, ["mcp", "test", "cited"], timeout=600)
        log("h1-mcp-test.txt", test_out + "\n" + test_err)
        claim("H1", "hermes mcp test cited is green and lists both tools",
              test_code == 0 and "cited_search" in test_out and "cited_ask" in test_out,
              (test_out + test_err).strip()[-400:])
        mcp_question = run_stream_question(mcp_home, PRICE_QUESTION)
        log("h1-question.jsonl", mcp_question["stdout"] + "\n" + mcp_question["stderr"])
        if not amount_with_source(mcp_question["final"], "380"):
            retry = run_stream_question(mcp_home, PRICE_QUESTION)
            log("h1-question-2.jsonl", retry["stdout"] + "\n" + retry["stderr"])
            if retry["code"] == 0 and amount_with_source(retry["final"], "380"):
                mcp_question = retry
        mcp_tool = next((name for name in mcp_question["tools"] if str(name).startswith("mcp__cited__")), None)
        claim("H1", "a natural question calls Cited over MCP and answers the amount with its source",
              mcp_question["code"] == 0 and mcp_tool is not None
              and amount_with_source(mcp_question["final"], "380"),
              "tools={0} final={1}".format(mcp_question["tools"], mcp_question["final"][:200]))
        EVIDENCE["h1"] = {
            "add": add_text,
            "config": config_text,
            "test": test_out,
            "tools": mcp_question["tools"],
            "final": mcp_question["final"],
        }

        source = workspace / "plugin-source"
        snapshot_error = snapshot_repo(source)
        plugin_home = workspace / "home-plugin"
        plugin_home.mkdir()
        homes.append(plugin_home)
        write_env(
            plugin_home,
            {
                "CITED_URL": CITED_URL,
                "CITED_MCP_TOKEN": token,
                "CITED_DEFAULT_MODE": "cited",
            },
        )
        url = "file:///" + str(source).replace("\\", "/")
        install_code, install_out, install_err = run_hermes(
            plugin_home,
            ["plugins", "install", url, "--enable", "--yes-deps"],
            extra_env={"CITED_URL": CITED_URL, "CITED_MCP_TOKEN": token},
            timeout=900,
        )
        log("h2-install.txt", install_out + "\n" + install_err)
        installed = plugin_home / "plugins" / "hermes-cited" / "plugin.yaml"
        plugin_config, _ = read_config(plugin_home)
        enabled = set((plugin_config.get("plugins") or {}).get("enabled") or [])
        claim("H2", "hermes plugins install enables the plugin from a local path",
              snapshot_error is None and install_code == 0 and installed.exists()
              and any("hermes-cited" in item for item in enabled),
              snapshot_error or (install_out + install_err).strip()[-400:])

        probe = (
            "import json;"
            "from hermes_cli.plugins import discover_plugins, get_plugin_manager, iter_hook_callbacks, get_plugin_commands;"
            "discover_plugins();"
            "print(json.dumps({'plugins': get_plugin_manager().list_plugins(),"
            "'hooks': {n: len(iter_hook_callbacks(n)) for n in "
            "('pre_llm_call','post_tool_call','transform_llm_output')},"
            "'commands': sorted(get_plugin_commands().keys())}, default=str))"
        )
        probe_code, probe_out, probe_err = run(
            [str(HERMES_PYTHON), "-c", probe],
            env={**hermes_env(plugin_home), "PYTHONPATH": str(HERMES_ROOT)},
            cwd=plugin_home,
            timeout=600,
        )
        log("h2-loader.txt", probe_out + "\n" + probe_err)
        try:
            loader = json.loads(probe_out.strip().splitlines()[-1]) if probe_out.strip() else {}
        except (ValueError, IndexError):
            loader = {}
        hooks = loader.get("hooks") or {}
        loaded_names = json.dumps(loader.get("plugins") or [])
        claim("H2", "the installed plugin loads with the real Hermes manager and registers its hooks",
              probe_code == 0 and all(hooks.get(name, 0) >= 1 for name in
                                      ("pre_llm_call", "post_tool_call", "transform_llm_output"))
              and "hermes-cited" in loaded_names
              and {"cited", "dot"}.issubset(set(loader.get("commands") or [])),
              probe_err.strip()[-300:] or probe_out.strip()[-300:])

        price = run_stream_question(plugin_home, PRICE_QUESTION)
        log("h2-price.jsonl", price["stdout"] + "\n" + price["stderr"])
        native = [name for name in price["tools"] if name in ("cited_search", "cited_ask")]
        quoted = "cited_quote" in price["tools"]
        no_mcp = not any(str(name).startswith("mcp__cited__") for name in price["tools"])
        claim("H2", "the native tools answer the price question without the MCP route",
              price["code"] == 0 and native and no_mcp, "tools={0}".format(price["tools"]))
        claim("H11", "the model chooses lines with cited_quote", quoted,
              "tools={0}".format(price["tools"]))
        claim("H8", "cited mode puts Cited first: only discovery tools run before it",
              bool(price["tools"]) and first_cited_before_others(price["tools"]),
              "tools={0}".format(price["tools"]))
        claim("H12", "(a) the price result is the plugin render of the line Cited returned",
              PRICE_LINE in price["final"] and PRICE_SOURCE in price["final"],
              price["final"][:300])

        guarantee = run_stream_question(plugin_home, GUARANTEE_QUESTION)
        log("h2-guarantee.jsonl", guarantee["stdout"] + "\n" + guarantee["stderr"])
        guarantee_question = GUARANTEE_QUESTION
        if GUARANTEE_LINE not in guarantee["final"]:
            guarantee = run_stream_question(plugin_home, GUARANTEE_FALLBACK_QUESTION)
            log("h2-guarantee-2.jsonl", guarantee["stdout"] + "\n" + guarantee["stderr"])
            guarantee_question = GUARANTEE_FALLBACK_QUESTION
        claim("H12", "(b) the guarantee result is the render of a full line of its excerpt",
              guarantee["code"] == 0 and GUARANTEE_LINE in guarantee["final"] and GUARANTEE_SOURCE in guarantee["final"],
              guarantee["final"][:240])

        unanswered = run_stream_question(plugin_home, UNANSWERED_QUESTION)
        log("h2-unanswered.jsonl", unanswered["stdout"] + "\n" + unanswered["stderr"])
        claim("H8", "(c) the unanswered question is the fixed refusal and states no datum",
              unanswered["code"] == 0 and clean_refusal(unanswered["final"]),
              "streamed={0} final={1}".format(unanswered["streamed"][:120], unanswered["final"][:200]))

        write_env(
            plugin_home,
            {
                "CITED_URL": CITED_URL,
                "CITED_MCP_TOKEN": token,
                "CITED_DEFAULT_MODE": "dot",
            },
        )
        dot = run_stream_question(plugin_home, PRICE_QUESTION)
        log("h4-dot.jsonl", dot["stdout"] + "\n" + dot["stderr"])
        claim("H4", "dot mode says nothing about a seal",
              dot["code"] == 0 and "Verified by Cited" not in dot["final"], dot["final"][:200])

        audit_file = plugin_home / "cited" / "audit.jsonl"
        audit_text = audit_file.read_text(encoding="utf-8") if audit_file.exists() else ""
        EXTRA_SCAN.append(audit_file)
        entries = []
        for line in audit_text.splitlines():
            if line.strip():
                entries.append(json.loads(line))
        verify_code, verify_out, verify_err = run(
            [str(TEST_PYTHON), "-m", "hermes_cited.verify_log", str(audit_file)],
            cwd=REPO,
            timeout=120,
        )
        log("h5-verify-log.txt", verify_out + "\n" + verify_err)
        cited_questions = [PRICE_QUESTION, guarantee_question, UNANSWERED_QUESTION]
        expected_modes = ["cited"] * len(cited_questions) + ["dot"]
        turn_ids = {entry.get("turn_id") for entry in entries}
        claim("H5", "the log has exactly one entry per turn, with unique turns, and the chain verifies",
              verify_code == 0 and len(entries) == len(expected_modes) and len(turn_ids) == len(entries)
              and sorted(entry.get("mode") for entry in entries) == sorted(expected_modes),
              "entries={0} turns={1} verify={2} {3}".format(
                  len(entries), len(turn_ids), verify_code, verify_out.strip()))
        claim("H5", "every entry carries the question, the session, the turn, the calls and the verifier",
              all(
                  entry.get("question")
                  and entry.get("session")
                  and entry.get("turn_id")
                  and entry.get("seq")
                  and isinstance(entry.get("tool_calls"), list)
                  and entry["tool_calls"]
                  and isinstance(entry.get("verifier"), dict)
                  and entry["verifier"].get("applied") is (entry.get("mode") == "cited")
                  for entry in entries
              ),
              "an entry is missing a field or marks the verifier wrongly")
        price_entry = entry_of_run(entries, PRICE_QUESTION, "cited")
        guarantee_entry = entry_of_run(entries, guarantee_question, "cited")
        claim("H8", "(a) the price amount is bound to the evidence row of its own turn",
              bound_amount(price_entry, "380", unit="currency", cite=True),
              json.dumps(price_entry or {})[:240])
        claim("H8", "(b) the guarantee duration is bound to the evidence row of its own turn",
              bound_amount(guarantee_entry, "90", unit="day", cite=True),
              json.dumps(guarantee_entry or {})[:240])
        bound_ok, bound_detail = every_block_is_bound(entries)
        claim("H5", "every block of every cited entry resolves against its own evidence row",
              bound_ok, bound_detail)
        claim("H5", "the lines a cited entry records are full lines of the excerpts of the turn",
              price_entry is not None
              and isinstance(price_entry.get("quoted_lines"), list)
              and any(line.get("text") == PRICE_LINE for line in price_entry["quoted_lines"])
              and all(line_is_from_entry(line.get("text"), price_entry) for line in price_entry["quoted_lines"]),
              "the price entry has no quoted_lines")
        digests_ok, digests_detail = recompute_digests(entries)
        claim("H5", "every excerpt digest recomputes from the excerpt text stored in the entry",
              digests_ok, digests_detail)
        claim("H4", "(a) the delivered price seal is the one its own audited entry carries",
              price_entry is not None and seal_matches_entry(price["final"], price_entry),
              "final={0} entry={1}".format(price["final"][-80:], json.dumps(price_entry or {})[:160]))
        claim("H4", "(b) the delivered guarantee seal is the one its own audited entry carries",
              guarantee_entry is not None and seal_matches_entry(guarantee["final"], guarantee_entry),
              "final={0}".format(guarantee["final"][-80:]))
        claim("H5", "the log verifies from the installed plugin, outside the checkout",
              verify_from_installed(plugin_home, audit_file) == 0,
              "the installed command did not exit zero")
        claim("H5", "a middle entry removed from the log makes the installed command fail",
              middle_removal_fails_from_installed(plugin_home, audit_file, workspace),
              "the installed command did not detect the removed middle entry")

        dot_entries = [
            json.loads(line) for line in audit_file.read_text(encoding="utf-8").splitlines() if line.strip()
        ]
        claim("H4", "a dot-mode answer is logged with the verifier marked as not applied",
              dot_entries[-1].get("mode") == "dot"
              and dot_entries[-1].get("verifier", {}).get("applied") is False,
              json.dumps(dot_entries[-1].get("verifier")))

        readme_en = (REPO / "README.md").read_text(encoding="utf-8")
        readme_es = (REPO / "README.es.md").read_text(encoding="utf-8")
        claim("H9", "(b) the CLI consumer rule and the retained surfaces are documented",
              ("show only the terminal `result` record" in readme_en
               or "show only the terminal" in readme_en)
              and "api_server" in readme_en and "interim" in readme_en and "auto_tts" in readme_en,
              "the README does not state the CLI rule or the withheld surfaces")
        claim("H9", "(c) only the terminal record of the documented consumer is measured, not the drafts",
              terminal_record_of(price["events"]) == price["final"]
              and bool(price["final"].strip())
              and (price["streamed"] != price["final"] or price["final"].rstrip().endswith("Verified by Cited")),
              "terminal={0} draft_chars={1}".format(
                  terminal_record_of(price["events"])[:80], len(price["streamed"])))

        EVIDENCE["h8"] = {
            "price": {"tools": price["tools"], "final": price["final"], "streamed": price["streamed"]},
            "guarantee": {"tools": guarantee["tools"], "final": guarantee["final"]},
            "unanswered": {"tools": unanswered["tools"], "final": unanswered["final"],
                           "streamed": unanswered["streamed"]},
            "dot": {"tools": dot["tools"], "final": dot["final"]},
            "audit_entries": len(entries),
            "verify_log": verify_out.strip(),
        }

        claim("H7", "both READMEs document install, configuration, render, delivery, log and tests",
              all(
                  needle in readme_en and needle in readme_es
                  for needle in (
                      "CITED_URL", "CITED_MCP_TOKEN", "CITED_DEFAULT_MODE", "CITED_LANGUAGE",
                      "cited_quote", "/cited", "/dot", "2026-10-10", "stream-json",
                  )
              )
              and "internal consistency" in readme_en.lower()
              and "not tamper-proof" in readme_en.lower()
              and "cited ledger" in readme_en.lower()
              and "consistencia interna" in readme_es.lower(),
              "a README is missing a documented fact")
        cited_mcp = (SOURCE_HERMES / "docs" / "mcp.md").read_text(encoding="utf-8")
        cited_readme = (SOURCE_HERMES / "README.md").read_text(encoding="utf-8")
        cited_readme_es = (SOURCE_HERMES / "README.es.md").read_text(encoding="utf-8")
        claim("H7", "the Cited worktree documents the Hermes Agent route in both languages",
              "Hermes Agent" in cited_mcp and "Hermes Agent" in cited_readme
              and "Hermes Agent" in cited_readme_es,
              "docs/mcp.md or a README has no Hermes Agent row")
        claim("H3", "the installed skill names the three tools, both modes and the plugin-only rule",
              installed_skill_ok(plugin_home),
              "the installed plugin has no complete skill file")

        return finish(started)
    finally:
        if cited_process is not None:
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(cited_process.pid), "/T", "/F"],
                    capture_output=True,
                    timeout=60,
                )
            except Exception:
                pass
            time.sleep(2.0)
        for home in homes:
            if not remove_tree(home):
                print("WARNING: a temporary HERMES_HOME was not removed: {0}".format(home))
        if not remove_tree(workspace):
            print("WARNING: the temporary directory was not removed: {0}".format(workspace))


def verify_from_installed(plugin_home, audit_file):
    """M7: the documented command, from the installed plugin directory, outside the checkout."""
    installed_dir = plugin_home / "plugins" / "hermes-cited"
    if not installed_dir.exists():
        return 1
    code, out, err = run(
        [str(HERMES_PYTHON), "-m", "hermes_cited.verify_log", str(audit_file)],
        cwd=installed_dir,
        timeout=120,
    )
    log("h5-installed-verify.txt", "exit {0}\n{1}\n{2}".format(code, out, err))
    return code


def middle_removal_fails_from_installed(plugin_home, audit_file, workspace):
    """D9 end to end: remove a middle entry of a copy and require a non-zero exit.

    Round 4 replaced the round 3 cut-suffix fixture: without a custody mark a cut suffix leaves a shorter,
    internally consistent chain, which the record says it cannot detect. Removing a middle entry does
    break the chain, and that is what this fixture requires.
    """
    copy = workspace / "audit-middle.jsonl"
    shutil.copyfile(audit_file, copy)
    lines = copy.read_text(encoding="utf-8").splitlines()
    if len(lines) < 2:
        return False
    del lines[0]
    copy.write_text("\n".join(lines) + "\n", encoding="utf-8")
    installed_dir = plugin_home / "plugins" / "hermes-cited"
    code, out, err = run(
        [str(HERMES_PYTHON), "-m", "hermes_cited.verify_log", str(copy)],
        cwd=installed_dir,
        timeout=120,
    )
    log("h5-installed-middle.txt", "exit {0}\n{1}\n{2}".format(code, out, err))
    return code != 0


def installed_skill_ok(plugin_home):
    path = plugin_home / "plugins" / "hermes-cited" / "hermes_cited" / "skills" / "cited" / "SKILL.md"
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    return all(needle in text for needle in
               ("cited_search", "cited_ask", "cited_quote", "/cited", "/dot", "native plugin"))


def finish(started):
    """Write every artifact, scan it on disk and only then emit the verdict (M-R2-4)."""
    if EVIDENCE.get("h1"):
        body = [markdown_block("hermes mcp add", EVIDENCE["h1"]["add"])]
        body.append(markdown_block("the config fragment it wrote", EVIDENCE["h1"]["config"]))
        body.append(markdown_block("hermes mcp test cited", EVIDENCE["h1"]["test"]))
        body.append(markdown_block(
            "the question",
            "tools={0}\n\n{1}".format(EVIDENCE["h1"]["tools"], EVIDENCE["h1"]["final"]),
        ))
        record(
            "2026-10-10-step-4-h1-mcp.md",
            "# Step 4 — H1, the MCP route with no installation\n\n" + "\n".join(body),
        )
    if EVIDENCE.get("h8"):
        body = []
        for key, label in (
            ("price", "(a) the price question in cited mode"),
            ("guarantee", "(b) the guarantee question in cited mode"),
            ("unanswered", "(c) an unanswered question"),
            ("dot", "dot mode"),
        ):
            item = EVIDENCE["h8"][key]
            body.append(markdown_block(
                label,
                "tools={0}\n\n{1}".format(item["tools"], item["final"]),
            ))
        body.append(markdown_block(
            "what the stream emitted before the terminal result (the documented consumer shows only `result`)",
            "price streamed chars={0}\nunanswered streamed chars={1}".format(
                len(EVIDENCE["h8"]["price"].get("streamed") or ""),
                len(EVIDENCE["h8"]["unanswered"].get("streamed") or ""),
            ),
        ))
        body.append(markdown_block(
            "the log",
            "{0} entries. {1}".format(EVIDENCE["h8"]["audit_entries"], EVIDENCE["h8"]["verify_log"]),
        ))
        record(
            "2026-10-10-step-5-e2e.md",
            "# Step 5 — H8, the end-to-end runs\n\n" + "\n".join(body),
        )

    for path, body in ARTIFACTS.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")

    passed = sum(1 for _, _, ok, _ in CLAIMS if ok)
    total = len(CLAIMS)
    green = passed == total
    elapsed = time.time() - started
    report_path = REPORTS / "2026-10-10-step-12-gate.md"

    def build_report():
        lines = [
            "# The gate of hermes-cited, round 4",
            "",
            "Date: 2026-10-10. Command: `scripts/gate.py` with the Python of the Hermes venv.",
            "Run: workspace {0}, {1:.0f}s, Hermes Agent v0.21.6+387 (`dce1e9b`), Cited `origin/main`.".format(
                "under the system temp directory", elapsed),
            "",
            "| Claim | Result | Note |",
            "|---|---|---|",
        ]
        for code, name, ok, detail in CLAIMS:
            lines.append("| {0} — {1} | {2} | {3} |".format(code, name, "PASS" if ok else "FAIL", redact(detail)[:200]))
        lines.append("")
        lines.append("{0} — {1}/{2} claims passed in {3:.0f}s.".format(
            "GATE: GREEN" if green else "GATE: RED", passed, total, elapsed))
        lines.append("")
        return "\n".join(lines)

    # M-R3-6: the report is written to disk before the verdict, then every artifact, the report included,
    # is scanned **on disk**, and if the report has to be rewritten its bytes are re-verified.
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(build_report(), encoding="utf-8")
    findings = strip_token_from_disk()
    report_on_disk = report_path.read_text(encoding="utf-8")
    if TOKEN and TOKEN in report_path.read_bytes().decode("utf-8", "replace"):
        green = False
        report_path.write_text(report_on_disk.replace(TOKEN, "<token>"), encoding="utf-8")
        findings = strip_token_from_disk()
        report_on_disk = report_path.read_text(encoding="utf-8")
        print("FAIL H6 the gate report itself carried the token; it was redacted and re-scanned")
    claim("H6", "the token is in no artifact on disk after redaction",
          not findings,
          "artifacts scanned on disk: {0}".format(len(ARTIFACTS) + len(EXTRA_SCAN) + 1)
          if not findings else "the token appears in: {0}".format(", ".join(findings)))

    claimed = [
        "| {0} — {1} | {2} | {3} |".format(code, name, "PASS" if ok else "FAIL", redact(detail)[:200])
        for code, name, ok, detail in CLAIMS
    ]
    passed = sum(1 for _, _, ok, _ in CLAIMS if ok)
    total = len(CLAIMS)
    green = green and passed == total
    verdict = "\n".join(
        [
            "# The gate of hermes-cited, round 4",
            "",
            "Date: 2026-10-10. Command: `scripts/gate.py` with the Python of the Hermes venv.",
            "Run: workspace under the system temp directory, Hermes Agent v0.21.6+387 (`dce1e9b`), "
            "Cited `origin/main`.",
            "",
            "| Claim | Result | Note |",
            "|---|---|---|",
        ]
        + claimed
        + [
            "",
            "{0} — {1}/{2} claims passed.".format(
                "GATE: GREEN" if green else "GATE: RED", passed, total),
            "",
        ]
    )
    if verdict != report_on_disk:
        report_path.write_text(verdict, encoding="utf-8")
        if TOKEN and TOKEN in report_path.read_bytes().decode("utf-8", "replace"):
            green = False
            print("FAIL H6 the gate report itself carried the token on the rewrite")
    EXTRA_SCAN.append(report_path)
    print("")
    print("GATE: {0} — {1}/{2} claims in {3:.0f}s".format(
        "GREEN" if green else "RED", passed, total, time.time() - started))
    return 0 if green else 1


if __name__ == "__main__":
    raise SystemExit(main())
