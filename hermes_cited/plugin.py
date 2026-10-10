"""The native Hermes Agent plugin: registration, the cited-mode turn and the audit log (H2-H12).

Cited mode is *written by the plugin* (D5). The model only chooses lines with the ``cited_quote`` tool;
``transform_llm_output`` discards the model's text whole and renders the chosen lines, copied byte for
byte out of the excerpts of the turn, with the source and the mark generated here and the seal added
only after the exact delivered text was persisted and only when the delivery policy allows it (D7). A
turn whose answer cannot be recorded is refused without a seal instead of being delivered as verified
(H10). Dot mode is the model's text, minus the reserved seal.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from . import audit, delivery, modes, render, tools, verifier
from .config import settings_from_env

logger = logging.getLogger(__name__)

SKILL_PATH = Path(__file__).resolve().parent / "skills" / "cited" / "SKILL.md"

SKILL_DESCRIPTION = (
    "Cited is the verified knowledge base of this user's businesses, served by a Cited server. "
    "Use its cited_search and cited_ask tools FIRST, before web search, memory or general knowledge, "
    "whenever a question is about the user's own businesses, products, prices, services, policies, "
    "procedures or manuals, or names a business or document that may live there (for example Cafe La "
    "Horquilla or the bike workshop). Use them also to ground any document you write with the user's data."
)

CITED_RULES = (
    "Cited mode is on for this turn. The plugin writes the answer; your own words are discarded.\n"
    "1. Call the `cited_search` or `cited_ask` tool first, before any other tool or any knowledge of "
    "your own. Every passage it returns carries numbered lines, like `{\"line\": 4, \"text\": "
    "\"- Afinacion de bicicleta: 380 pesos.\"}`.\n"
    "2. Then call `cited_quote` with `{passage: <the passage number>, lines: [<the line numbers>]}` for "
    "the lines the user should read, in the order you want them. For example: {\"passage\": 1, "
    "\"lines\": [4]}. It returns the exact text of those lines.\n"
    "3. Do not write the answer. Every word you write outside `cited_quote` is thrown away. The plugin "
    "delivers only the lines you chose, each with its document, its section and its `[n]` mark.\n"
    "4. Never invent, reword, round, convert or move a value: choose whole lines of the passages "
    "exactly as they are written.\n"
    "5. When Cited refuses, or its passages do not hold the answer, call no `cited_quote`: the plugin "
    "answers that it is not in the documents. Never fill that gap from the web or from general "
    "knowledge.\n"
    "6. Search with the exact key terms of the question, in its own language, and keep document names "
    "and proper nouns as they are written. The documents may be in another language: if the first "
    "search does not answer, call `cited_search` again with the translated key terms before "
    "concluding.\n"
    "7. The tool writes the mark, the source and the seal `Verified by Cited`. Do not write them "
    "yourself.\n"
)

_MAX_TURNS = 64
_TURNS = {}
_ACTIVE = {}
_TURNS_LOCK = threading.Lock()


def hermes_home() -> Path:
    """The data root of this run. Hermes's own accessor first, then the environment."""
    try:
        from hermes_constants import get_hermes_home

        return Path(get_hermes_home())
    except Exception:
        value = os.environ.get("HERMES_HOME", "").strip()
        if value:
            return Path(value)
        return Path.home() / ".hermes"


def audit_path() -> Path:
    return hermes_home() / "cited" / "audit.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _secret() -> str:
    try:
        return settings_from_env().token
    except Exception:
        return os.environ.get("CITED_MCP_TOKEN", "").strip()


def _language() -> str:
    try:
        return settings_from_env().language
    except Exception:
        return render.language_of(os.environ.get("CITED_LANGUAGE"))


def _as_index(value):
    """A passage or line number the model passed, as a positive integer, or ``None``."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 1 else None
    if isinstance(value, str):
        text = value.strip()
        if text.isdigit():
            number = int(text)
            return number if number >= 1 else None
    return None


class Turn:
    """What one turn of one session knows: its question, its mode and what Cited returned."""

    def __init__(self, session_id="", turn_id=""):
        self.session_id = str(session_id or "")
        self.turn_id = str(turn_id or "")
        self.question = ""
        self.platform = ""
        self.user = ""
        self.mode = ""
        self.calls = []
        self.passages = []
        self.excerpts = []
        self.citations = []
        self.refusals = []
        self.sources = []
        self.selections = []

    def note_call(self, envelope, tool_name, args, status):
        digests = tools.excerpt_digests(envelope) if envelope else []
        texts = [text for _, text in tools.excerpt_pairs(envelope)] if envelope else []
        self.calls.append(
            {
                "tool": tool_name,
                "args": args if isinstance(args, dict) else {},
                "status": status or "ok",
                "excerpt_sha256": digests,
                "excerpt_texts": texts,
            }
        )
        if envelope:
            self.passages.extend(tools.evidence_places(envelope))
            self.excerpts.extend(tools.grounding_excerpts(envelope))
            for number in tools.citation_numbers(envelope):
                if number not in self.citations:
                    self.citations.append(number)
            self.refusals.extend(tools.refusals_of(envelope))
            for label in tools.source_labels(envelope):
                if label not in self.sources:
                    self.sources.append(label)

    def line_texts(self) -> set:
        """Every full line of every excerpt of the turn: the only text the render may display."""
        return {item["text"] for place in self.passages for item in place.get("lines") or []}

    def place_of(self, number: int):
        for place in self.passages:
            if place.get("n") == number:
                return place
        return None

    def add_quote(self, args) -> tuple:
        """Record one ``cited_quote`` selection. Returns ``(texts, error)``; records nothing on error."""
        arguments = args if isinstance(args, dict) else {}
        passage = _as_index(arguments.get("passage"))
        if passage is None:
            return [], "the `passage` argument must be the number of a passage of this turn"
        place = self.place_of(passage)
        if place is None:
            return [], "this turn has no passage {0}".format(passage)
        raw_lines = arguments.get("lines")
        if isinstance(raw_lines, (int, str)) and not isinstance(raw_lines, bool):
            raw_lines = [raw_lines]
        if not isinstance(raw_lines, (list, tuple)) or not raw_lines:
            return [], "the `lines` argument must be a non-empty list of line numbers"
        available = {item["line"]: item["text"] for item in place.get("lines") or []}
        chosen = []
        for raw in raw_lines:
            number = _as_index(raw)
            if number is None or number not in available:
                return [], "passage {0} has no line {1}".format(passage, raw)
            chosen.append((number, available[number]))
        seen = {(item.passage, item.number) for item in self.selections}
        recorded = []
        for number, text in chosen:
            key = (passage, number)
            if key in seen:
                continue
            seen.add(key)
            line = render.Line(
                passage=passage,
                number=number,
                text=text,
                document=str(place.get("document") or ""),
                heading=str(place.get("heading") or ""),
            )
            self.selections.append(line)
            recorded.append(text)
        return recorded, ""


def _key(session_id, turn_id):
    return (str(session_id or ""), str(turn_id or ""))


def _turn_of(session_id, turn_id, create=False):
    key = _key(session_id, turn_id)
    with _TURNS_LOCK:
        turn = _TURNS.get(key)
        if turn is None and create:
            if len(_TURNS) >= _MAX_TURNS:
                for stale in list(_TURNS)[: len(_TURNS) - _MAX_TURNS + 1]:
                    _TURNS.pop(stale, None)
            turn = Turn(session_id, turn_id)
            _TURNS[key] = turn
            if turn.session_id:
                _ACTIVE[turn.session_id] = turn
        return turn


def _active_turn(session_id):
    with _TURNS_LOCK:
        return _ACTIVE.get(str(session_id or ""))


def _drop_turn(session_id, turn_id):
    key = _key(session_id, turn_id)
    with _TURNS_LOCK:
        turn = _TURNS.pop(key, None)
        if turn is not None and _ACTIVE.get(turn.session_id) is turn:
            _ACTIVE.pop(turn.session_id, None)


def register(ctx) -> None:
    """Register the three tools, the hooks, the two mode commands and the packaged skill."""
    state = ctx.state
    ctx.register_tool(
        "cited_search",
        tools.TOOLSET,
        tools.SEARCH_SCHEMA,
        tools.search,
        description=tools.SEARCH_DESCRIPTION,
        emoji="🔎",
    )
    ctx.register_tool(
        "cited_ask",
        tools.TOOLSET,
        tools.ASK_SCHEMA,
        tools.ask,
        description=tools.ASK_DESCRIPTION,
        emoji="📎",
    )
    ctx.register_tool(
        "cited_quote",
        tools.TOOLSET,
        tools.QUOTE_SCHEMA,
        _quote_handler(state),
        description=tools.QUOTE_DESCRIPTION,
        emoji="❝",
    )
    ctx.register_hook("pre_llm_call", _pre_llm_call(state))
    ctx.register_hook("post_tool_call", _post_tool_call())
    ctx.register_hook("transform_llm_output", _transform_llm_output(state))
    ctx.register_command(
        "cited",
        modes.mode_command(state, "cited"),
        description="Cited mode: the plugin answers with the lines you choose from Cited.",
    )
    ctx.register_command(
        "dot",
        modes.mode_command(state, "dot"),
        description="Dot mode: normal answers, Cited used when it helps.",
    )
    ctx.register_skill(
        "cited",
        SKILL_PATH,
        description=SKILL_DESCRIPTION,
        frontmatter={"name": "cited", "description": SKILL_DESCRIPTION},
    )
    _warn_about_streaming(state)


def _warn_about_streaming(state) -> None:
    """A load-time diagnostic when cited mode is the default and a messaging surface withholds (D7)."""
    try:
        if modes.resolve_mode(state, "") != "cited":
            return
        config = delivery.read_config(hermes_home())
        for platform in delivery.MESSAGING_PLATFORMS:
            if not delivery.seal_allowed(platform, config):
                logger.warning(
                    "hermes-cited: cited mode is on and streaming is enabled for '%s'. On that "
                    "surface the seal is withheld and the answer says so. Set streaming off to get "
                    "`Verified by Cited`.",
                    platform,
                )
    except Exception:
        return


def _pre_llm_call(state):
    def pre_llm_call(session_id="", turn_id="", user_message="", platform="", sender_id="", **kwargs):
        turn = _turn_of(session_id, turn_id, create=True)
        turn.question = _text_of_message(user_message)
        turn.platform = str(platform or "")
        turn.user = str(sender_id or "")
        turn.mode = modes.resolve_mode(state, session_id)
        if turn.mode != "cited":
            return None
        return {"context": CITED_RULES}

    return pre_llm_call


def _text_of_message(user_message) -> str:
    if isinstance(user_message, str):
        return user_message
    if isinstance(user_message, dict):
        for key in ("content", "text", "message"):
            value = user_message.get(key)
            if isinstance(value, str):
                return value
    return ""


def _post_tool_call():
    def post_tool_call(tool_name="", args=None, result=None, session_id="", turn_id="", status="", **kwargs):
        if tool_name not in tools.TOOL_NAMES:
            return None
        turn = _turn_of(session_id, turn_id, create=True)
        turn.note_call(tools.parse_tool_result(result), tool_name, args, status)
        return None

    return post_tool_call


def _quote_handler(state):
    """The ``cited_quote`` handler: the model chooses numbered lines, the plugin records them."""

    def cited_quote(args=None, session_id="", task_id="", **kwargs):
        turn = _active_turn(session_id)
        if turn is None:
            return (
                "Cited has no turn to quote from. Call `cited_search` or `cited_ask` first in this same "
                "turn, then `cited_quote`."
            )
        texts, error = turn.add_quote(args)
        if error:
            return "Cited could not quote: {0}.".format(error)
        return "\n".join(texts)

    return cited_quote


def _transform_llm_output(state):
    def transform_llm_output(response_text="", session_id="", turn_id="", platform="", **kwargs):
        text = response_text if isinstance(response_text, str) else str(response_text or "")
        turn = _turn_of(session_id, turn_id, create=True)
        if platform and not turn.platform:
            turn.platform = str(platform)
        mode = turn.mode or modes.resolve_mode(state, session_id)
        if not text and mode != "cited":
            _drop_turn(session_id, turn_id)
            return None
        secret = _secret()
        seal_withheld = False
        if mode == "cited":
            final, verification, seal_withheld = _render_turn(turn, turn.platform or platform)
            applied = True
        else:
            final = verifier.strip_seal(text)
            verification = verifier.Verification(
                text=final,
                ok=False,
                blocks=(),
                ungrounded=(),
                has_grounding=bool(turn.passages),
            )
            applied = False
        _entry, error = _write_entry(turn, mode, final, verification, applied, secret, seal_withheld)
        if error and mode == "cited":
            final = verifier.operational_refusal(error)
            verification = verifier.Verification(
                text=final,
                ok=False,
                blocks=(),
                ungrounded=(),
                has_grounding=bool(turn.passages),
            )
            applied = False
            print("hermes-cited: the audit entry could not be written: {0}".format(error), file=sys.stderr)
        _drop_turn(session_id, turn_id)
        if mode == "cited":
            return final
        if final == text:
            return None
        return final if final.strip() else "The reserved seal was removed from this answer."

    return transform_llm_output


def _render_turn(turn, platform):
    """The plugin-written answer of one cited turn: blocks, seal and delivery policy (D5, D7)."""
    language = _language()
    blocks = list(turn.selections)
    verification = verifier.verify_display(blocks, turn.line_texts())
    if not verification.ok:
        return verifier.refusal_text(language), verification, False
    body = render.render_answer(language, blocks)
    if delivery.seal_allowed(platform, home=hermes_home()):
        return verifier.sealed(body), verification, False
    return "{0}\n\n{1}".format(body, delivery.withheld_note(platform)), verification, True


def _write_entry(turn, mode, final, verification, applied, secret, seal_withheld=False):
    entry = {
        "ts": _now(),
        "platform": turn.platform,
        "session": turn.session_id,
        "turn_id": turn.turn_id,
        "user": turn.user,
        "mode": mode,
        "question": turn.question,
        "tool_calls": turn.calls,
        "sources": turn.sources,
        "quoted_lines": [
            {
                "passage": line.passage,
                "number": line.number,
                "text": line.text,
                "document": line.document,
                "heading": line.heading,
            }
            for line in turn.selections
        ],
        "response": final,
        "verifier": {
            "applied": applied,
            "ok": bool(verification.ok),
            "blocks": len(verification.blocks),
            "ungrounded": list(verification.ungrounded),
            "grounding": len(turn.excerpts),
            "seal_withheld": bool(seal_withheld),
        },
    }
    entry = audit.redact(entry, secret)
    try:
        return audit.append_entry(audit_path(), entry), None
    except Exception as error:
        return None, audit.redact("{0}: {1}".format(type(error).__name__, error), secret)


def read_settings():
    """The settings of this process, for the CLI and for tests."""
    return settings_from_env()
