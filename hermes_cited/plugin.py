"""The native Hermes Agent plugin: registration, the cited-mode turn and the audit log (H2-H6, H9, H10).

The cited-mode verifier is extractive (D2): it only accepts a datum that is copied verbatim from an
excerpt Cited returned in the same turn. The delivery policy (D1) is checked per turn: on a surface
whose streaming is on, the seal is withheld and the answer says so. A turn whose answer cannot be
recorded is refused without a seal instead of being delivered as verified (H10).
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from . import audit, delivery, modes, tools, verifier
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
    "Cited mode is on for this turn.\n"
    "1. Call the `cited_search` or `cited_ask` tool first, before any other tool or any knowledge of "
    "your own, and answer only from the excerpts it returns.\n"
    "2. Copy every fact verbatim. Each sentence or line that carries a number, a price, a unit, a "
    "date or a code must be written between « » exactly as an excerpt of this turn writes it, with "
    "its subject, on its own line, and exactly once. For example: «Afinación de bicicleta: 380 "
    "pesos.» Never reword, round, convert, translate or move a value to another subject.\n"
    "3. Never write a number, price, unit, date or code outside « » anywhere in the answer, not even "
    "to announce, repeat or summarise the quotation. The only exception is a citation mark such as "
    "[1]. A valid answer looks like this:\n"
    "«Afinación de bicicleta: 380 pesos.»\n"
    "Fuente: cafe-la-horquilla.md, Precios [1].\n"
    "4. Keep the citation marks such as [1] and name the source document and its section.\n"
    "5. When Cited refuses, or its excerpts do not hold the answer, say plainly that it is not in the "
    "documents. Never fill that gap from the web or from general knowledge.\n"
    "6. A deterministic verifier checks this answer before delivery. A datum that is not copied "
    "verbatim from an excerpt of this turn, or that appears outside « », makes the whole answer be "
    "replaced by a refusal naming it, so do not state anything you did not read in an excerpt.\n"
)

_MAX_TURNS = 64
_TURNS = {}
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
        self.excerpts = []
        self.citations = []
        self.refusals = []
        self.sources = []

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
            self.excerpts.extend(tools.grounding_excerpts(envelope))
            for number in tools.citation_numbers(envelope):
                if number not in self.citations:
                    self.citations.append(number)
            self.refusals.extend(tools.refusals_of(envelope))
            for label in tools.source_labels(envelope):
                if label not in self.sources:
                    self.sources.append(label)


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
        return turn


def _drop_turn(session_id, turn_id):
    with _TURNS_LOCK:
        _TURNS.pop(_key(session_id, turn_id), None)


def register(ctx) -> None:
    """Register the tools, the hooks, the two mode commands and the packaged skill."""
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
    ctx.register_hook("pre_llm_call", _pre_llm_call(state))
    ctx.register_hook("post_tool_call", _post_tool_call())
    ctx.register_hook("transform_llm_output", _transform_llm_output(state))
    ctx.register_command(
        "cited",
        modes.mode_command(state, "cited"),
        description="Cited mode: verify every value against the passages Cited returned.",
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
    """A load-time diagnostic when cited mode is the default and a surface streams (D1)."""
    try:
        if modes.resolve_mode(state, "") != "cited":
            return
        config = delivery.read_config(hermes_home())
        for platform in delivery.MESSAGING_PLATFORMS + ("cli",):
            if delivery.streaming_surface(platform) and delivery.effective_streaming(platform, config):
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


def _transform_llm_output(state):
    def transform_llm_output(response_text="", session_id="", turn_id="", platform="", **kwargs):
        text = response_text if isinstance(response_text, str) else str(response_text or "")
        if not text:
            return None
        turn = _turn_of(session_id, turn_id, create=True)
        if platform and not turn.platform:
            turn.platform = str(platform)
        mode = turn.mode or modes.resolve_mode(state, session_id)
        secret = _secret()
        seal_withheld = False
        if mode == "cited":
            if turn.refusals:
                verification = verifier.Verification(
                    text="",
                    ok=False,
                    claims=(),
                    ungrounded=(),
                    has_grounding=bool(turn.excerpts),
                )
                final = verifier.refusal(verification, refused_reason="; ".join(turn.refusals))
            else:
                verification = verifier.verify(text, turn.excerpts, turn.citations)
                if verification.ok:
                    if delivery.seal_allowed(turn.platform or platform, home=hermes_home()):
                        final = verifier.seal(verification, turn.sources)
                    else:
                        final = "{0}\n\n{1}".format(
                            verification.text.rstrip(), delivery.withheld_note(turn.platform or platform)
                        )
                        seal_withheld = True
                else:
                    final = verifier.refusal(verification)
                    verification = verifier.Verification(
                        text=final,
                        ok=False,
                        claims=verification.claims,
                        ungrounded=verification.ungrounded,
                        has_grounding=verification.has_grounding,
                    )
            applied = True
        else:
            final = text
            verification = verifier.Verification(
                text=text,
                ok=False,
                claims=(),
                ungrounded=(),
                has_grounding=bool(turn.excerpts),
            )
            applied = False
        _entry, error = _write_entry(turn, mode, final, verification, applied, secret, seal_withheld)
        if error and mode == "cited":
            final = verifier.operational_refusal(error)
            verification = verifier.Verification(
                text=final,
                ok=False,
                claims=(),
                ungrounded=(),
                has_grounding=bool(turn.excerpts),
            )
            applied = False
            print("hermes-cited: the audit entry could not be written: {0}".format(error), file=sys.stderr)
        _drop_turn(session_id, turn_id)
        return final if mode == "cited" else None

    return transform_llm_output


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
        "response": final,
        "verifier": {
            "applied": applied,
            "ok": bool(verification.ok),
            "claims": list(verification.claims),
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


def _session_of_turn(session_id):
    return json.dumps({"session": str(session_id or "")}, ensure_ascii=False)
