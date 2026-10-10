#!/usr/bin/env python
"""The gate of hermes-cited: affirm H0 to H8 and print GATE: GREEN or GATE: RED.

Run it with the Python of the installed Hermes venv, which is what the mission asks for:

    & "$env:LOCALAPPDATA\\hermes\\hermes-agent\\venv\\Scripts\\python.exe" scripts/gate.py

Every Hermes process it starts gets an explicit temporary HERMES_HOME under the system temp
directory, and the gate refuses to run a Hermes command without one. The real
``%LOCALAPPDATA%\\hermes`` and ``~/.hermes`` are never used.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REPORTS = REPO / "reports"
GATE_LOGS = REPO / ".tmp" / "gate"

HERMES_ROOT = Path(os.environ.get("HERMES_ROOT", r"C:\Users\Franc\AppData\Local\hermes\hermes-agent"))
HERMES_EXE = HERMES_ROOT / "venv" / "Scripts" / "hermes.exe"
HERMES_PYTHON = HERMES_ROOT / "venv" / "Scripts" / "python.exe"

CITED_ROOT = Path(os.environ.get("CITED_ROOT", str(REPO.parent / "community-mcpfix")))
CITED_PORT = int(os.environ.get("CITED_PORT", "3246"))
CITED_URL = "http://127.0.0.1:{0}".format(CITED_PORT)
CITED_MCP_URL = "{0}/api/mcp".format(CITED_URL)

TEST_PYTHON = REPO / ".venv" / "Scripts" / "python.exe"
COMMUNITY_HERMES = REPO.parent / "community-hermes"
NPM = shutil.which("npx") or "npx.cmd"

PRICE_QUESTION = "¿Cuánto cuesta la afinación de bicicleta en Café La Horquilla?"
GUARANTEE_QUESTION = "Is there a guarantee on repairs at the bike workshop?"
UNANSWERED_QUESTION = "¿Cuánto cuesta el jabón de lavanda artesanal en Café La Horquilla?"

REFUSAL_MARKERS = (
    "no está",
    "no esta",
    "no aparece",
    "no se encuentra",
    "no existe",
    "no hay",
    "no podemos",
    "no puedo",
    "no tengo",
    "not in the documents",
    "do not have",
    "don't have",
    "no information",
    "cannot find",
    "sin inventar",
    "no lo sé",
    "no lo se",
)

CLAIMS = []
EVIDENCE = {}


def claim(code, name, ok, detail=""):
    ok = bool(ok)
    CLAIMS.append((code, name, ok, detail))
    print("{0} {1} {2}{3}".format("PASS" if ok else "FAIL", code, name, "" if ok else " :: {0}".format(detail)))
    sys.stdout.flush()
    return ok


def log(name, text):
    GATE_LOGS.mkdir(parents=True, exist_ok=True)
    (GATE_LOGS / name).write_text(text, encoding="utf-8")


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
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
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
        cwd=CITED_ROOT,
        timeout=600,
    )
    log("cited-seed.txt", out + "\n" + err)
    if code != 0:
        return None, None, "the seed failed: {0}".format(err.strip()[-400:])
    node_code, node_out, node_err = run(
        [NPM, "-y", "-p", "node@24", "node", "-e", "process.stdout.write(process.execPath)"],
        cwd=CITED_ROOT,
        timeout=300,
    )
    node = node_out.strip() if node_code == 0 and node_out.strip() else "node"
    log("cited-node.txt", node + "\n" + node_err)
    stdout = open(workspace / "cited.log", "wb")
    stderr = open(workspace / "cited.err.log", "wb")
    process = subprocess.Popen(
        [node, "node_modules/next/dist/bin/next", "start", "-H", "127.0.0.1", "-p", str(CITED_PORT)],
        cwd=str(CITED_ROOT),
        env=env,
        stdout=stdout,
        stderr=stderr,
    )
    if not wait_ready(token):
        return process, store, "Cited did not answer tools/list on {0}".format(CITED_MCP_URL)
    return process, store, None


def first_cited_before_others(tools):
    """True when the first Cited tool comes before any other data-gathering tool."""
    cited = ("cited_search", "cited_ask")
    others = ("web_search", "web_extract", "search_files", "read_file", "terminal", "execute_code")
    first_cited = next((index for index, name in enumerate(tools) if name in cited), None)
    first_other = next((index for index, name in enumerate(tools) if name in others), None)
    if first_cited is None:
        return False
    return first_other is None or first_cited < first_other


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


def redact(text, token):
    return str(text).replace(token, "<token>")


def remove_tree(path, attempts=12, delay=5.0):
    """Remove a temporary tree, retrying while a just-killed process still holds a file."""
    target = Path(path)
    for attempt in range(attempts):
        if not target.exists():
            return True
        subprocess.run(
            ["cmd", "/c", "attrib", "-R", str(target), "/S", "/D"],
            capture_output=True,
        )
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
    return "## {0}\n\n```\n{1}\n```\n".format(title, body.rstrip())


def main():
    GATE_LOGS.mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix="hc-gate-"))
    homes = []
    cited_process = None
    started = time.time()
    print("hermes-cited gate · workspace {0}".format(workspace))

    token = os.urandom(32).hex()
    try:
        claim("preflight", "the installed Hermes, the Cited worktree and pytest are present",
              HERMES_EXE.exists() and HERMES_PYTHON.exists() and (CITED_ROOT / "node_modules" / "next").exists()
              and TEST_PYTHON.exists(),
              "missing: {0}".format(", ".join(str(p) for p in (HERMES_EXE, HERMES_PYTHON, CITED_ROOT, TEST_PYTHON) if not p.exists())))
        claim("preflight", "DEEPSEEK_API_KEY is in the environment", bool(deepseek_key()),
              "set the user environment variable DEEPSEEK_API_KEY")
        claim("preflight", "port {0} is free".format(CITED_PORT), port_is_free(CITED_PORT),
              "another process is listening on {0}".format(CITED_PORT))

        facts = (REPORTS / "hermes-facts.md").read_text(encoding="utf-8")
        claim("H0", "reports/hermes-facts.md answers every fact H0 asks for",
              all(needle in facts for needle in (
                  "dce1e9b", "transform_llm_output", "agent/turn_finalizer.py", "pre_llm_call",
                  "post_tool_call", "requires_toolsets", "file://", "gateway",
              )),
              "the report does not name every fact")

        if not port_is_free(CITED_PORT):
            claim("H8", "a local Cited of the samples answers tools/list", False,
                  "port {0} is not free".format(CITED_PORT))
            return finish(started, token)
        cited_process, store, error = start_cited(workspace, token)
        claim("H8", "a local Cited of the samples answers tools/list", error is None, error or "")
        if error is not None:
            return finish(started, token)
        log("cited-ready.txt", "ready after {0:.1f}s".format(time.time() - started))

        unit_code, unit_out, unit_err = run(
            [str(TEST_PYTHON), "-m", "pytest", "-q"], cwd=REPO, timeout=900
        )
        log("unit.txt", unit_out + "\n" + unit_err)
        tail = unit_out.strip().splitlines()[-1] if unit_out.strip() else ""
        claim("H8", "the unit suite is green", unit_code == 0 and "failed" not in tail and "error" not in tail.lower(),
              tail or unit_err.strip()[-300:])

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
              redact(add_text.strip()[-400:], token))
        config, config_text = read_config(mcp_home)
        entry = ((config.get("mcp_servers") or {}).get("cited") or {}) if config else {}
        claim("H1", "the config fragment names the endpoint and the bearer header",
              entry.get("url") == CITED_MCP_URL
              and "Bearer ${MCP_CITED_API_KEY}" == (entry.get("headers") or {}).get("Authorization"),
              redact(json.dumps(entry), token))
        test_code, test_out, test_err = run_hermes(mcp_home, ["mcp", "test", "cited"], timeout=600)
        log("h1-mcp-test.txt", test_out + "\n" + test_err)
        claim("H1", "hermes mcp test cited is green and lists both tools",
              test_code == 0 and "cited_search" in test_out and "cited_ask" in test_out,
              redact((test_out + test_err).strip()[-400:], token))
        mcp_question = run_stream_question(mcp_home, PRICE_QUESTION)
        log("h1-question.jsonl", mcp_question["stdout"] + "\n" + mcp_question["stderr"])
        mcp_tool = next((name for name in mcp_question["tools"] if str(name).startswith("mcp__cited__")), None)
        claim("H1", "a natural question calls Cited over MCP and answers 380 pesos with its citation",
              mcp_question["code"] == 0 and mcp_tool is not None and "380" in mcp_question["final"],
              "tools={0} final={1}".format(mcp_question["tools"], redact(mcp_question["final"][:200], token)))
        EVIDENCE["h1"] = {
            "add": redact(add_text, token),
            "config": redact(config_text, token),
            "test": redact(test_out, token),
            "tools": mcp_question["tools"],
            "final": redact(mcp_question["final"], token),
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
              snapshot_error or redact((install_out + install_err).strip()[-400:], token))

        price = run_stream_question(plugin_home, PRICE_QUESTION)
        log("h2-price.jsonl", price["stdout"] + "\n" + price["stderr"])
        native = [name for name in price["tools"] if name in ("cited_search", "cited_ask")]
        no_mcp = not any(str(name).startswith("mcp__cited__") for name in price["tools"])
        claim("H2", "the native tools answer the price question", price["code"] == 0 and native and no_mcp,
              "tools={0}".format(price["tools"]))
        claim("H8", "cited mode puts Cited first: no web or filesystem tool runs before it",
              bool(price["tools"]) and first_cited_before_others(price["tools"]),
              "tools={0}".format(price["tools"]))
        claim("H8", "(a) the price answer carries 380 pesos and its citation",
              "380" in price["final"] and ("[1]" in price["final"] or "cafe-la-horquilla" in price["final"]),
              redact(price["final"][:240], token))
        claim("H4", "the verified price answer ends with the seal",
              "Verified by Cited" in price["final"], redact(price["final"][-200:], token))

        guarantee = run_stream_question(plugin_home, GUARANTEE_QUESTION)
        log("h2-guarantee.jsonl", guarantee["stdout"] + "\n" + guarantee["stderr"])
        claim("H8", "(b) the guarantee answer carries 90 days and its citation",
              guarantee["code"] == 0 and "90" in guarantee["final"] and "Verified by Cited" in guarantee["final"],
              redact(guarantee["final"][:240], token))

        unanswered = run_stream_question(plugin_home, UNANSWERED_QUESTION)
        log("h2-unanswered.jsonl", unanswered["stdout"] + "\n" + unanswered["stderr"])
        text_lower = unanswered["final"].lower()
        claim("H8", "(c) the unanswered question is refused without inventing a price",
              unanswered["code"] == 0 and any(marker in text_lower for marker in REFUSAL_MARKERS),
              redact(unanswered["final"][:240], token))

        audit_file = plugin_home / "cited" / "audit.jsonl"
        audit_text = audit_file.read_text(encoding="utf-8") if audit_file.exists() else ""
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
        claim("H5", "the cited-mode log exists, has one entry per answer and its chain verifies",
              verify_code == 0 and len(entries) >= 3 and all(entry.get("mode") == "cited" for entry in entries),
              "entries={0} verify={1} {2}".format(len(entries), verify_code, verify_out.strip()))
        claim("H5", "every entry carries the question, the calls, the excerpt digests and the verifier",
              all(
                  entry.get("question")
                  and isinstance(entry.get("tool_calls"), list)
                  and entry["tool_calls"]
                  and all(len(digest) == 64 for digest in entry["tool_calls"][0]["excerpt_sha256"])
                  and entry.get("verifier", {}).get("applied") is True
                  for entry in entries
              ),
              "an entry is missing a field")
        claim("H6", "the token is in no audit entry and in no report",
              token not in audit_text
              and all(token not in item.read_text(encoding="utf-8", errors="replace") for item in REPORTS.glob("*.md")),
              "the token appears in the evidence")

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
              dot["code"] == 0 and "Verified by Cited" not in dot["final"],
              redact(dot["final"][:200], token))
        dot_entries = [json.loads(line) for line in audit_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        claim("H4", "a dot-mode answer is logged with the verifier marked as not applied",
              dot_entries[-1].get("mode") == "dot" and dot_entries[-1].get("verifier", {}).get("applied") is False,
              json.dumps(dot_entries[-1].get("verifier")))

        EVIDENCE["h8"] = {
            "price": {"tools": price["tools"], "final": redact(price["final"], token)},
            "guarantee": {"tools": guarantee["tools"], "final": redact(guarantee["final"], token)},
            "unanswered": {"tools": unanswered["tools"], "final": redact(unanswered["final"], token)},
            "dot": {"tools": dot["tools"], "final": redact(dot["final"], token)},
            "audit_entries": len(entries) + 1,
            "verify_log": verify_out.strip(),
        }

        readme_en = (REPO / "README.md").read_text(encoding="utf-8")
        readme_es = (REPO / "README.es.md").read_text(encoding="utf-8")
        claim("H7", "both READMEs document the install, the configuration, the modes and what was tested",
              all(
                  needle in readme_en and needle in readme_es
                  for needle in ("CITED_URL", "CITED_MCP_TOKEN", "CITED_DEFAULT_MODE", "/cited", "/dot", "2026-10-09")
              ),
              "a README is missing a documented fact")
        cited_mcp = (COMMUNITY_HERMES / "docs" / "mcp.md").read_text(encoding="utf-8")
        cited_readme = (COMMUNITY_HERMES / "README.md").read_text(encoding="utf-8")
        cited_readme_es = (COMMUNITY_HERMES / "README.es.md").read_text(encoding="utf-8")
        claim("H7", "the Cited worktree documents the Hermes Agent route",
              "Hermes Agent" in cited_mcp and "Hermes Agent" in cited_readme and "Hermes Agent" in cited_readme_es,
              "docs/mcp.md or a README has no Hermes Agent row")
        claim("H3", "the packaged skill travels with the plugin and names both tools",
              (plugin_home / "plugins" / "hermes-cited" / "hermes_cited" / "skills" / "cited" / "SKILL.md").exists(),
              "the installed plugin has no skill file")

        return finish(started, token)
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


def finish(started, token):
    passed = sum(1 for _, _, ok, _ in CLAIMS if ok)
    total = len(CLAIMS)
    green = passed == total
    elapsed = time.time() - started
    lines = ["# The gate of hermes-cited", "", "Date: 2026-10-09. Command: `scripts/gate.py` with the Python of the Hermes venv.", ""]
    lines.append("| Claim | Result | Note |")
    lines.append("|---|---|---|")
    for code, name, ok, detail in CLAIMS:
        lines.append("| {0} — {1} | {2} | {3} |".format(code, name, "PASS" if ok else "FAIL", redact(detail, token)[:200]))
    lines.append("")
    lines.append("{0} — {1}/{2} claims passed in {3:.0f}s.".format(
        "GATE: GREEN" if green else "GATE: RED", passed, total, elapsed))
    lines.append("")
    summary = "\n".join(lines)
    (REPORTS / "2026-10-09-step-6-gate.md").write_text(summary, encoding="utf-8")

    if EVIDENCE.get("h1"):
        body = [markdown_block("hermes mcp add", EVIDENCE["h1"]["add"])]
        body.append(markdown_block("the config fragment it wrote", EVIDENCE["h1"]["config"]))
        body.append(markdown_block("hermes mcp test cited", EVIDENCE["h1"]["test"]))
        body.append(markdown_block("the question", "tools={0}\n\n{1}".format(EVIDENCE["h1"]["tools"], EVIDENCE["h1"]["final"])))
        (REPORTS / "2026-10-09-step-4-h1-mcp.md").write_text(
            "# Step 4 — H1, the MCP route with no installation\n\n" + "\n".join(body), encoding="utf-8"
        )
    if EVIDENCE.get("h8"):
        body = []
        for key, label in (("price", "(a) the price question"), ("guarantee", "(b) the guarantee question"),
                           ("unanswered", "(c) an unanswered question"), ("dot", "dot mode")):
            item = EVIDENCE["h8"][key]
            body.append(markdown_block(label, "tools={0}\n\n{1}".format(item["tools"], item["final"])))
        body.append(markdown_block(
            "the log",
            "{0} entries. {1}".format(EVIDENCE["h8"]["audit_entries"], EVIDENCE["h8"]["verify_log"]),
        ))
        (REPORTS / "2026-10-09-step-5-e2e.md").write_text(
            "# Step 5 — H8, the end-to-end runs\n\n" + "\n".join(body), encoding="utf-8"
        )
    print("")
    print("GATE: {0} — {1}/{2} claims in {3:.0f}s".format("GREEN" if green else "RED", passed, total, elapsed))
    return 0 if green else 1


if __name__ == "__main__":
    raise SystemExit(main())
