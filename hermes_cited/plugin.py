"""The native Hermes Agent plugin: registration, the cited-mode turn and the consistency record (H2-H15).

Cited mode is *written by the plugin* (D5). The model only chooses lines with the ``cited_quote`` tool;
``transform_llm_output`` discards the model's text whole and renders the chosen lines, copied byte for
byte out of the excerpts of the turn, with the source and the mark generated here. Round 6 (D11, H16)
retains the seal ``Verified by Cited`` on every route while the host does not expose an accreditable
delivery contract: the one capability point is ``delivery.accredited_delivery()``, the answer carries the
fixed note that names the retention, and the record states that it registers the plugin's composition and
not the terminal message.

Round 4 (D10) puts **one boundary around the whole transformer**: for every cited turn that reaches the
hook, the delivered text is exactly one of the render, the fixed localized refusal, or the fixed
localized operational refusal with an incident code, and any exception of reading the configuration,
resolving, rendering, composing or persisting produces that third one. The turn state is dropped in
``finally``. No error detail is ever interpolated into an answer.

Round 8 (D12) retires the protection of the reserved mark. With D11 the plugin emits no seal on any route,
so no authentic seal exists that anyone could forge: dot mode returns the model's text untouched and its
row records exactly that string, and a cited documentary line that carries the phrase is data like any
other, next to the general note that says this version emits no seal.
"""

from __future__ import annotations

import contextlib
import contextvars
import json
import logging
import os
import secrets
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from . import audit, config, delivery, messages, modes, render, tools, verifier
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
    "your own. Every passage it returns carries its identifier `pid` (like `P1`) and numbered lines, "
    "like `{\"line\": 4, \"text\": \"- Afinacion de bicicleta: 380 pesos.\"}`.\n"
    "2. Then call `cited_quote` with `{passage: \"<the pid of the passage>\", lines: [<the line "
    "numbers>]}` for the lines the user should read, in the order you want them. For example: "
    "{\"passage\": \"P1\", \"lines\": [4]}. It returns the exact text of those lines. The `pid` is "
    "unique inside the turn: two searches that both return a passage 1 give you `P1` and `P2`.\n"
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
    "7. The plugin writes the source and the fixed note; the seal `Verified by Cited` is not written at "
    "all while the host does not accredit the delivery of the turn (H16). Do not write the mark or the "
    "note yourself.\n"
)

MAX_INDEX = 10 ** 6
MAX_LINES = 500
_MAX_TURNS = 64
_TURNS = {}
_ACTIVE = {}
_TURNS_LOCK = threading.Lock()

#: The profile of the call in progress: ``(canonical home, settings)``. Every registered callback sets
#: it before an effect and reads the URL, the token, the language and the default mode from it, so a
#: process that hosts more than one Hermes profile never crosses them (D2, B01).
_CALL = contextvars.ContextVar("hermes_cited_profile_call", default=None)


@contextlib.contextmanager
def _profile_call(registration):
    """Validate the profile of *registration* and read its settings before any effect (D2, B01).

    With a registration, ``config.settings_for`` checks that the active scope is still the same home and
    the same mode and fails closed otherwise. Without one (a direct call of a factory by a test) the
    documented environment of a standalone run is used, exactly as H0-H18 always did.
    """
    if registration is None:
        settings = settings_from_env()
        home = ""
    else:
        settings = config.settings_for(registration)
        home = config.canonical_home(registration.home)
    token = _CALL.set((home, settings))
    try:
        yield settings
    finally:
        _CALL.reset(token)


def _owner(home):
    """The profile identity a lookup is bound to, or ``""`` for the unfiltered legacy path.

    Every registered callback passes the home of its registration explicitly, so the unfiltered form is
    reachable only from a direct call of a factory by a test or from a standalone run (D2, B01).
    """
    return config.canonical_home(home) if home is not None else ""


class _ProfileState:
    """The mode state of one profile, under the host's own per-profile partition (D7).

    The pinned host's ``PluginState`` already partitions its state per profile home, so the plugin
    writes the plain ``mode.profile`` key of the version before this change: the stored value survives
    an upgrade with no migration and every key satisfies the host pattern ``^[A-Za-z0-9_.:-]{1,128}$``.
    A host validation error is a defect, never the default, and a shared state object is not a host
    configuration: isolation comes from the host partition, not from a path or NUL prefix here.
    """

    def __init__(self, state, home=""):
        self._state = state

    def get(self, key, default=None):
        return self._state.get(str(key), default)

    def set(self, key, value):
        return self._state.set(str(key), value)


def hermes_home() -> Path:
    """The data root of this run: the profile of the call in progress, then Hermes, then the environment."""
    current = _CALL.get()
    if current is not None and current[0]:
        return Path(current[0])
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
    current = _CALL.get()
    if current is not None:
        return str(current[1].token or "")
    try:
        return settings_from_env().token
    except Exception:
        return os.environ.get("CITED_MCP_TOKEN", "").strip()


def _language() -> str:
    current = _CALL.get()
    if current is not None:
        return current[1].language
    try:
        return settings_from_env().language
    except Exception:
        return messages.language_of(os.environ.get("CITED_LANGUAGE"))


def _safe_language() -> str:
    """The language of an answer built after a failure: the same resolution, never raising (H10)."""
    try:
        return _language()
    except Exception:
        return messages.DEFAULT_LANGUAGE


#: B-R5-1: the constant, non-empty reserve code. When the entropy dependency fails, the incident code is
#: this value, so the refusal is built without touching entropy, disk, configuration or the logger.
RESERVE_INCIDENT_CODE = "CITED-00000000"


def incident_code() -> str:
    """The code of one operational refusal, generated at the failure site (H10, B-R5-1).

    It never raises: a failure of ``secrets.token_hex`` returns the constant reserve code instead, so the
    emergency exit of the transformer cannot depend on the entropy source that just failed.
    """
    try:
        return "CITED-{0}".format(secrets.token_hex(4).upper())
    except BaseException:
        return RESERVE_INCIDENT_CODE


def _as_index(value):
    """A passage or line number the model passed, as a positive integer, or ``None``.

    Only positive integers of the schema and their plain ASCII digit strings are accepted (m-R3-1):
    ``str.isdigit`` accepts characters such as ``²`` and it accepts a five-thousand-digit string, and
    both used to raise inside the handler.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if 1 <= value <= MAX_INDEX else None
    if isinstance(value, str):
        text = value.strip()
        if 1 <= len(text) <= 9 and text.isascii() and text.isdigit():
            number = int(text)
            return number if 1 <= number <= MAX_INDEX else None
    return None


def _as_identifier(value):
    """The ``pid`` of a passage, or ``None`` when the value is not one."""
    if isinstance(value, str):
        text = value.strip()
        if not text or len(text) > 32 or not text.isascii():
            return None
        if not text.isalnum():
            return None
        return text
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and 1 <= value <= MAX_INDEX:
        return str(value)
    return None


class Turn:
    """What one turn of one session knows: its question, its mode, its passages and its selections."""

    def __init__(self, session_id="", turn_id="", home=""):
        self.session_id = str(session_id or "")
        self.turn_id = str(turn_id or "")
        self.home = str(home or "")
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
        self.delivery = None
        self._passage_count = 0
        self._call_count = 0

    def note_call(self, envelope, tool_name, args, status):
        """Record one real evidence call; an envelope the handler already bound is not renumbered.

        Round 5 (M-R4-3) assigns the identifiers while the search result is built, so this path reads the
        ``pid``, ``call`` and ``uid`` the model received instead of assigning new ones.
        """
        if not envelope:
            return
        if self._is_registered(envelope):
            return
        digests = tools.excerpt_digests(envelope)
        texts = [text for _, text in tools.excerpt_pairs(envelope)]
        call_index = self._call_count
        self._call_count += 1
        self._record_tool_call(tool_name, args, status, digests, texts)
        for place in tools.evidence_places(envelope):
            self._passage_count += 1
            pid = "P{0}".format(self._passage_count)
            place["pid"] = pid
            place["call"] = call_index
            place["uid"] = "{0}:{1}:{2}".format(self.turn_id, call_index, pid)
            self.passages.append(place)
        self._note_evidence(envelope)

    def note_quote_call(self, args, status):
        """Record a ``cited_quote`` call as a selection; its text is never evidence (B-R4-2)."""
        self._record_tool_call("cited_quote", args, status, [], [])

    def bind_envelope(self, envelope, tool_name, args):
        """Assign the identifiers of the turn to one evidence envelope and register it (M-R4-3).

        The same record goes back to the model, to the render and to the log; the hook reads it out of the
        result instead of renumbering the passage.
        """
        places = tools.evidence_objects(envelope)
        if not places:
            self.note_call(envelope, tool_name, args, "ok")
            return json.dumps(envelope, ensure_ascii=False)
        call_index = self._call_count
        self._call_count += 1
        for place in places:
            self._passage_count += 1
            pid = "P{0}".format(self._passage_count)
            place["pid"] = pid
            place["call"] = call_index
            place["uid"] = "{0}:{1}:{2}".format(self.turn_id, call_index, pid)
        self._record_tool_call(
            tool_name, args, "ok", tools.excerpt_digests(envelope),
            [text for _, text in tools.excerpt_pairs(envelope)],
        )
        self.passages.extend(tools.bound_places(envelope))
        self._note_evidence(envelope)
        return json.dumps(envelope, ensure_ascii=False)

    def _record_tool_call(self, tool_name, args, status, digests, texts):
        self.calls.append(
            {
                "tool": str(tool_name or ""),
                "args": args if isinstance(args, dict) else {},
                "status": status or "ok",
                "excerpt_sha256": list(digests),
                "excerpt_texts": list(texts),
            }
        )

    def _note_evidence(self, envelope):
        self.excerpts.extend(tools.grounding_excerpts(envelope))
        for number in tools.citation_numbers(envelope):
            if number not in self.citations:
                self.citations.append(number)
        self.refusals.extend(tools.refusals_of(envelope))
        for label in tools.source_labels(envelope):
            if label not in self.sources:
                self.sources.append(label)

    def _is_registered(self, envelope) -> bool:
        """True when every evidence place of the envelope already carries an identifier of this turn."""
        places = tools.evidence_objects(envelope)
        if not places or not all(str(place.get("uid") or "") for place in places):
            return False
        known = {str(place.get("uid") or "") for place in self.passages}
        return all(str(place.get("uid") or "") in known for place in places)

    def line_texts(self) -> set:
        """Every full line of every excerpt of the turn: the only text the render may display."""
        return {item["text"] for place in self.passages for item in place.get("lines") or []}

    def place_of(self, identifier):
        """The passage a ``pid`` names, or a numeric ``passage`` when it identifies exactly one."""
        for place in self.passages:
            if str(place.get("pid")) == str(identifier):
                return place
        number = _as_index(identifier)
        if number is None:
            return None
        matches = [place for place in self.passages if place.get("n") == number]
        return matches[0] if len(matches) == 1 else None

    def numeric_is_ambiguous(self, identifier) -> bool:
        number = _as_index(identifier)
        if number is None:
            return False
        return len([place for place in self.passages if place.get("n") == number]) > 1

    def add_quote(self, args) -> tuple:
        """Record one ``cited_quote`` selection. Returns ``(texts, error)``; records nothing on error."""
        arguments = args if isinstance(args, dict) else {}
        raw_identifier = arguments.get("passage")
        text_identifier = _as_identifier(raw_identifier)
        if text_identifier is None:
            return [], (
                "the `passage` argument must be the `pid` of a passage of this turn, like `P1`, or its "
                "number when it is not ambiguous"
            )
        place = self.place_of(text_identifier)
        if place is None and self.numeric_is_ambiguous(text_identifier):
            return [], (
                "this turn has more than one passage with the number {0}: use the `pid` of the passage "
                "you want, like `P1` or `P2`".format(text_identifier)
            )
        if place is None:
            return [], "this turn has no passage {0}".format(text_identifier)
        raw_lines = arguments.get("lines")
        if isinstance(raw_lines, (int, str)) and not isinstance(raw_lines, bool):
            raw_lines = [raw_lines]
        if not isinstance(raw_lines, (list, tuple)) or not raw_lines:
            return [], "the `lines` argument must be a non-empty list of line numbers"
        if len(raw_lines) > MAX_LINES:
            return [], "the `lines` argument must hold at most {0} line numbers".format(MAX_LINES)
        available = {item["line"]: item["text"] for item in place.get("lines") or []}
        chosen = []
        for raw in raw_lines:
            number = _as_index(raw)
            if number is None or number not in available:
                return [], "passage {0} has no line {1}".format(text_identifier, raw)
            chosen.append((number, available[number]))
        pid = str(place.get("pid") or "")
        seen = {(item.uid, item.number) for item in self.selections}
        recorded = []
        for number, text in chosen:
            key = (str(place.get("uid") or ""), number)
            if key in seen:
                continue
            seen.add(key)
            line = render.Line(
                passage=place.get("n") or 0,
                number=number,
                text=text,
                document=str(place.get("document") or ""),
                heading=str(place.get("heading") or ""),
                pid=pid,
                call=int(place.get("call") or 0),
                original=int(place.get("n") or 0),
                position=int(place.get("position") or 0),
                uid=str(place.get("uid") or ""),
            )
            self.selections.append(line)
            recorded.append(text)
        return recorded, ""


def _find_turn_locked(session_id, turn_id, owner):
    """The live turn under one owner key, or the unique match for the legacy unfiltered path (D6).

    ``owner`` is the canonical home of the registering profile. The unfiltered form is reachable only
    from a direct call of a factory outside Hermes; with more than one owner holding the same
    identifiers it answers ``None`` instead of guessing which profile the caller means.
    """
    sid, tid = str(session_id or ""), str(turn_id or "")
    if owner:
        return _TURNS.get((owner, sid, tid))
    matches = [turn for key, turn in _TURNS.items() if key[1] == sid and key[2] == tid]
    return matches[0] if len(matches) == 1 else None


def _evict_oldest_locked(owner):
    """Drop the oldest turns of *one owner* so the cap never evicts another profile's turn (D6).

    The capacity of the turn table belongs to the ``(home, session, turn)`` key space: a busy profile
    that opens its whole capacity must never remove the pending evidence of a different validated
    registration. The oldest key of the calling owner is the one that goes, never the first key of the
    whole table.
    """
    owned = [key for key in _TURNS if key[0] == owner]
    excess = len(owned) - _MAX_TURNS + 1
    for stale in owned[:excess] if excess > 0 else ():
        _remove_locked(stale)


def _turn_of(session_id, turn_id, create=False, home=None):
    """The turn of ``(home, session, turn)``; two profiles with equal identifiers are two turns (D6)."""
    owner = _owner(home)
    sid, tid = str(session_id or ""), str(turn_id or "")
    with _TURNS_LOCK:
        turn = _find_turn_locked(sid, tid, owner)
        if turn is not None:
            return turn
        if not create:
            return None
        if not owner and any(key[1] == sid and key[2] == tid for key in _TURNS):
            # Another profile holds these identifiers and no owner was named: refuse instead of
            # creating a colliding second turn the caller cannot address.
            return None
        key = (owner, sid, tid)
        _evict_oldest_locked(owner)
        turn = Turn(session_id, turn_id, home=owner)
        _TURNS[key] = turn
        if turn.session_id:
            _ACTIVE.setdefault(turn.session_id, [])
            _ACTIVE[turn.session_id].append(turn)
        return turn


def _remove_locked(key):
    turn = _TURNS.pop(key, None)
    if turn is None:
        return None
    queue = _ACTIVE.get(turn.session_id)
    if queue:
        _ACTIVE[turn.session_id] = [item for item in queue if item is not turn]
        if not _ACTIVE[turn.session_id]:
            _ACTIVE.pop(turn.session_id, None)
    return turn


def _active_turns(session_id, home=None):
    """The turns of one session, of the profile in hand, that have not returned from the transformer."""
    owner = _owner(home)
    with _TURNS_LOCK:
        turns = list(_ACTIVE.get(str(session_id or ""), []))
    if not owner:
        return turns
    return [turn for turn in turns if not turn.home or turn.home == owner]


def _active_turn(session_id, home=None):
    """The only active turn of a session, or ``None`` when there is none or more than one (H14)."""
    turns = _active_turns(session_id, home=home)
    return turns[0] if len(turns) == 1 else None


def _identity_sequence(turn_id, task_id) -> tuple:
    """The explicit execution identities of a call, in precedence order (D6, H14).

    The pinned host composes its turn identifier as ``"<session>:<task>:<suffix>"`` and its tool
    dispatch hands the handler the task and the session, never the turn (``model_tools._execute_tool``).
    Both spellings are therefore accepted, but a present ``turn_id`` is authoritative: when it names no
    open turn the callback is refused instead of quoting the turn its ``task_id`` names. An empty value
    is not an identity. Creation, resolution and observation use the same raw spelling, never a trimmed
    variant, so two distinct identifiers never collapse into one (M02-B2R2).
    """
    turn_value = str(turn_id or "")
    if turn_value:
        return (("turn", turn_value),)
    task_value = str(task_id or "")
    if task_value:
        return (("task", task_value),)
    return ()


def _turn_has_identity(turn, session_id, kind, value) -> bool:
    """Whether *turn* is the one the host execution identity names (D6, H14).

    A ``turn`` identity matches the exact host turn identifier. A ``task`` identity matches that same
    identifier, which the host also uses as the middle component of the composed spelling, so a dispatch
    that carries only the task still reaches the turn its pre-hook opened.
    """
    turn_value = str(turn.turn_id or "")
    if kind == "turn":
        return turn_value == value
    if turn_value == value:
        return True
    parts = turn_value.split(":", 2)
    return len(parts) == 3 and parts[0] == str(session_id or "") and parts[1] == value


def _resolve_active_turn(session_id, turn_id="", task_id="", home=None):
    """Bind a selection to the turn of the execution identity, never to the latest one (H14).

    Returns ``(turn, error)``. The resolution distinguishes three cases: no identity at all, where the
    only open turn of the session is used and more than one is refused; an explicit identity (``turn_id``
    or ``task_id``) that resolves to exactly one open turn; and an explicit identity that resolves to no
    open turn, which is refused instead of being treated as an absent identity. A contradictory
    identifier never quotes a different live turn, and a present ``turn_id`` is never replaced by the
    ``task_id`` of the same call.
    """
    owner = _owner(home)
    turns = _active_turns(session_id, home=owner)
    if not turns:
        return None, (
            "Cited has no turn to quote from. Call `cited_search` or `cited_ask` first in this same turn, "
            "then `cited_quote`."
        )
    identities = _identity_sequence(turn_id, task_id)
    if not identities:
        if len(turns) == 1:
            return turns[0], ""
        return None, (
            "Cited cannot tell which of the {0} open turns of this session this quote belongs to: pass no "
            "passage, or ask again in a single turn".format(len(turns))
        )
    for kind, value in identities:
        matches = [turn for turn in turns if _turn_has_identity(turn, session_id, kind, value)]
        if len(matches) == 1:
            return matches[0], ""
        if len(matches) > 1:
            return None, (
                "Cited cannot tell which of the {0} open turns of this session this quote belongs to: pass "
                "no passage, or ask again in a single turn".format(len(matches))
            )
    return None, (
        "Cited cannot bind this selection to the execution identity it names: no open turn of this "
        "session has that identifier. Call `cited_search` or `cited_ask` in this same turn, then "
        "`cited_quote`."
    )


def _drop_turn(session_id, turn_id, home=None):
    """Drop only the turn this callback owns, resolved through its ``(home, session, turn)`` key (D6)."""
    owner = _owner(home)
    sid, tid = str(session_id or ""), str(turn_id or "")
    with _TURNS_LOCK:
        if owner:
            key = (owner, sid, tid)
            if key not in _TURNS:
                return None
            return _remove_locked(key)
        matches = [key for key in _TURNS if key[1] == sid and key[2] == tid]
        if len(matches) != 1:
            return None
        return _remove_locked(matches[0])


def register(ctx) -> None:
    """Register the surface of the configured mode: full keeps H0-H18; search registers one tool (H19).

    The mode and the canonical home identity of the active profile are captured once, here. An unknown
    mode, a missing scope or an unreadable accessor registers nothing and leaves a redacted sentence,
    before any callback is installed. There is no fallback to the process environment when Hermes is
    present: only a run in which the ``agent`` package is genuinely absent reads ``os.environ`` (D2, B01).
    """
    try:
        scope = config.active_scope()
    except config.CitedError as scope_error:
        _refuse_registration(scope_error)
        return
    try:
        mode = config.bridge_mode_of(scope.get(config.BRIDGE_TOOLS_ENV))
    except config.CitedError as error:
        _refuse_registration(error)
        return
    home = config.canonical_home(scope.home)
    if mode == config.BRIDGE_SEARCH and not home:
        _refuse_registration(config.CitedScopeError(config.SCOPE_SENTENCE))
        return
    registration = config.Registration(mode=mode, home=home, explicit=scope.source == "explicit")
    if mode == config.BRIDGE_SEARCH:
        _register_search(ctx, registration)
        return
    _register_full(ctx, registration)


def _refuse_registration(error) -> None:
    """Register nothing and say so, redacted: no token, URL or profile name is part of this sentence."""
    message = "hermes-cited: registration refused: {0}".format(error)
    try:
        logger.error("%s", message)
    except BaseException:
        pass
    try:
        print(message, file=sys.stderr)
    except BaseException:
        pass


def _register_search(ctx, registration) -> None:
    """Search registers exactly one native tool and no command, hook, skill or log writer (H20)."""
    ctx.register_tool(
        "cited_search",
        tools.TOOLSET,
        tools.SEARCH_WIRE_SCHEMA,
        _search_handler(registration),
        description=tools.SEARCH_ONLY_DESCRIPTION,
        emoji="🔎",
    )


def _search_handler(registration):
    """The one search handler, bound to the registration's own profile identity for every call."""

    def cited_search(args=None, **kwargs):
        return tools.search_only(args, registration)

    return cited_search


def _register_full(ctx, registration) -> None:
    """The full surface of H0-H18, with every handler bound to its registration (D2, B01)."""
    state = _ProfileState(ctx.state, registration.home)
    ctx.register_tool(
        "cited_search",
        tools.TOOLSET,
        tools.SEARCH_SCHEMA,
        _evidence_handler(tools.search, registration),
        description=tools.SEARCH_DESCRIPTION,
        emoji="🔎",
    )
    ctx.register_tool(
        "cited_ask",
        tools.TOOLSET,
        tools.ASK_SCHEMA,
        _evidence_handler(tools.ask, registration),
        description=tools.ASK_DESCRIPTION,
        emoji="📎",
    )
    ctx.register_tool(
        "cited_quote",
        tools.TOOLSET,
        tools.QUOTE_SCHEMA,
        _quote_handler(state, registration),
        description=tools.QUOTE_DESCRIPTION,
        emoji="❝",
    )
    ctx.register_hook("pre_llm_call", _pre_llm_call(state, registration))
    ctx.register_hook("post_tool_call", _post_tool_call(registration))
    ctx.register_hook("transform_llm_output", _transform_llm_output(state, registration))
    ctx.register_command(
        "cited",
        _profile_command(registration, modes.mode_command(state, "cited", language=_safe_language)),
        description="Cited mode: the plugin answers with the lines you choose from Cited.",
    )
    ctx.register_command(
        "dot",
        _profile_command(registration, modes.mode_command(state, "dot", language=_safe_language)),
        description="Dot mode: normal answers, Cited used when it helps.",
    )
    ctx.register_skill(
        "cited",
        SKILL_PATH,
        description=SKILL_DESCRIPTION,
        frontmatter={"name": "cited", "description": SKILL_DESCRIPTION},
    )
    _warn_about_streaming(state, registration)


def _profile_command(registration, action):
    """A command validates the profile of its registration before it changes any state (D2, B01)."""

    def handler(raw_args="", **kwargs):
        secret = ""
        try:
            with _profile_call(registration) as settings:
                secret = settings.token
                return action(raw_args)
        except config.CitedError as error:
            return str(error)
        except BaseException as error:
            _report_failure("the Cited command failed", incident_code(), error, secret=secret)
            return (
                "Cited could not change the mode: the configuration of this profile could not be read."
            )

    return handler


def _warn_about_streaming(state, registration=None) -> None:
    """A load-time diagnostic when cited mode is the default and a messaging surface withholds (D7)."""
    try:
        with _profile_call(registration) as settings:
            if modes.resolve_mode(state, "", settings.default_mode) != "cited":
                return
            for platform in delivery.MESSAGING_PLATFORMS:
                snap = delivery.snapshot(platform, home=hermes_home())
                if not snap.seal:
                    logger.warning(
                        "hermes-cited: cited mode is on and '%s' withholds the seal (%s).",
                        platform,
                        ", ".join(snap.reasons) or "unknown",
                    )
    except Exception:
        return


def _pre_llm_call(state, registration=None):
    def pre_llm_call(session_id="", turn_id="", user_message="", platform="", sender_id="", **kwargs):
        secret = ""
        try:
            with _profile_call(registration) as settings:
                secret = settings.token
                turn = _turn_of(session_id, turn_id, create=True, home=registration.home if registration else None)
                turn.question = _text_of_message(user_message)
                turn.platform = str(platform or "")
                turn.user = str(sender_id or "")
                turn.mode = modes.resolve_mode(state, session_id, settings.default_mode)
                if turn.mode != "cited":
                    return None
                turn.delivery = delivery.snapshot(turn.platform, home=hermes_home())
                return {"context": CITED_RULES}
        except config.CitedError:
            return None
        except BaseException as error:
            _report_failure("the pre_llm_call hook failed", incident_code(), error, secret=secret)
            return None

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


def _evidence_handler(build, registration):
    """The registered ``cited_search``/``cited_ask`` handler: the result carries the ``pid`` (M-R4-3).

    The identifiers are assigned while the result is built and bound to the real turn of the execution, so
    the model, the render and the log use the same record and the hook never renumbers it. The settings are
    read fresh from the profile of *registration* on every call, and a changed home or mode is refused
    before the request, so the callback can never act for another profile (D2, B01).
    """

    def handler(args=None, session_id="", task_id="", turn_id="", **kwargs):
        try:
            with _profile_call(registration) as settings:
                result = build(args, settings=settings, **kwargs)
                return _bind_result(
                    result, args, session_id, turn_id, task_id, home=registration.home
                )
        except config.CitedError as error:
            return str(error)
        except Exception:
            return "Cited could not be called: the configuration of this profile could not be read."

    return handler


def _bind_result(result, args, session_id, turn_id, task_id, home=None):
    if not isinstance(result, str):
        return result
    try:
        envelope = tools.parse_tool_result(result)
        if envelope is None:
            return result
        turn, _error = _resolve_active_turn(session_id, turn_id=turn_id, task_id=task_id, home=home)
        if turn is None:
            return result
        return turn.bind_envelope(envelope, str(envelope.get("cited_tool") or ""), args)
    except BaseException as error:
        _report_failure("the evidence handler failed", incident_code(), error)
        return result


def _observed_turn(session_id, turn_id, task_id, home=None):
    """The live turn an observation names, located with the identity policy of the handlers (D6, H14).

    The pinned host's ``post_tool_call`` carries the composed turn identifier, but a reduced observation
    may carry only the task. Both resolve to the same turn. The observation never fabricates one: an
    explicit identity that names no open turn is ignored instead of reviving a returned turn or opening an
    identity-less second execution (M02-B2R2).
    """
    owner = _owner(home)
    sid = str(session_id or "")
    identities = _identity_sequence(turn_id, task_id)
    with _TURNS_LOCK:
        if not identities:
            return _TURNS.get((owner, sid, ""))
        for kind, value in identities:
            matches = [
                turn
                for key, turn in _TURNS.items()
                if key[0] == owner and key[1] == sid and _turn_has_identity(turn, sid, kind, value)
            ]
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                return None
        return None


def _note_tool_call(tool_name, args, result, session_id, turn_id, status, home=None, task_id=""):
    if tool_name not in tools.EVIDENCE_TOOLS:
        try:
            turn = _observed_turn(session_id, turn_id, task_id, home=home)
        except BaseException:
            turn = None
        if turn is not None:
            turn.note_quote_call(args if isinstance(args, dict) else {}, status)
        return None
    turn = _observed_turn(session_id, turn_id, task_id, home=home)
    if turn is None:
        return None
    envelope = tools.parse_tool_result(result, tool_name)
    if envelope is not None:
        turn.note_call(envelope, tool_name, args, status)
    return None


def _post_tool_call(registration=None):
    def post_tool_call(tool_name="", args=None, result=None, session_id="", turn_id="", task_id="", status="", **kwargs):
        if tool_name not in tools.TOOL_NAMES:
            return None
        home = registration.home if registration is not None else None
        secret = ""
        try:
            with _profile_call(registration) as settings:
                secret = settings.token
                return _note_tool_call(
                    tool_name, args, result, session_id, turn_id, status, home=home, task_id=task_id
                )
        except config.CitedError:
            return None
        except BaseException as error:
            _report_failure("the post_tool_call hook failed", incident_code(), error, secret=secret)
            return None

    return post_tool_call


def _quote_handler(state, registration=None):
    """The ``cited_quote`` handler: the model chooses numbered lines, the plugin records them."""

    def cited_quote(args=None, session_id="", task_id="", turn_id="", **kwargs):
        secret = ""
        try:
            with _profile_call(registration) as settings:
                secret = settings.token
                home = registration.home if registration is not None else None
                turn, error = _resolve_active_turn(
                    session_id, turn_id=turn_id, task_id=task_id, home=home
                )
                if turn is None:
                    return error
                texts, error = turn.add_quote(args)
                if error:
                    return audit.redact("Cited could not quote: {0}.".format(error), secret)
                return "\n".join(texts)
        except config.CitedError as error:
            return str(error)
        except BaseException as error:
            _report_failure("the cited_quote handler failed", incident_code(), error, secret=secret)
            return "Cited could not quote this selection."

    return cited_quote


def _recorded_mode(session_id, turn_id, home=None) -> str:
    """The mode recorded for this turn, read only under its own ``(home, session, turn)`` key (D6)."""
    try:
        with _TURNS_LOCK:
            turn = _find_turn_locked(session_id, turn_id, _owner(home))
        if turn is None:
            return ""
        return str(turn.mode or "").strip().lower()
    except BaseException:
        return ""


def _operational_refusal(code) -> str:
    """The fixed operational refusal, built so that no secondary failure can escape (B-R4-1, B-R5-1).

    Every step is guarded and the last one is a literal, so the emergency exit depends on no entropy, no
    disk, no configuration and no logger.
    """
    try:
        return verifier.operational_refusal(code, _safe_language())
    except BaseException:
        pass
    try:
        return messages.operational_text(messages.DEFAULT_LANGUAGE, code)
    except BaseException:
        return "CITED incident {0}: the answer could not be delivered as verified.".format(code)


def _sanitized_diagnostic(message, code, error, secret=None) -> str:
    """One diagnostic with the bearer redacted from the whole formatted traceback (M-R4-5, D8).

    ``secret`` is the redaction set of the profile whose callback failed; when the caller does not yet
    know it (a failure before its settings were read) the call context is consulted.
    """
    import traceback

    body = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    text = "hermes-cited: {0} (incident {1})\n{2}".format(message, code, body)
    return audit.redact(text, _secret() if secret is None else secret)


def _report_failure(message, code, error, secret=None) -> None:
    """Emit only the sanitized diagnostic; never hand a raw traceback to a logger (M-R4-5, D8)."""
    try:
        logger.error("%s", _sanitized_diagnostic(message, code, error, secret))
    except BaseException:
        pass
    try:
        print(
            "hermes-cited: incident {0}: {1}; see the log for the redacted traceback".format(code, message),
            file=sys.stderr,
        )
    except BaseException:
        pass


def _transform_llm_output(state, registration=None):
    def transform_llm_output(response_text="", session_id="", turn_id="", platform="", **kwargs):
        home = registration.home if registration is not None else None
        intent = ""
        mode = None
        secret = ""
        owned = False
        try:
            text = response_text if isinstance(response_text, str) else str(response_text or "")
            with _profile_call(registration) as settings:
                # D6: the registration is validated before any turn is read, created or dropped. A
                # callback whose scope resolves to another home or mode never reaches this point, so the
                # refusal performs no cleanup and never destroys the owner's live turn.
                owned = True
                secret = settings.token
                intent = _recorded_mode(session_id, turn_id, home=home)
                turn = _turn_of(session_id, turn_id, create=True, home=home)
                if platform and not turn.platform:
                    turn.platform = str(platform)
                recorded = str(turn.mode or "").strip().lower()
                if recorded:
                    intent = recorded
                mode = recorded or modes.resolve_mode(state, session_id, settings.default_mode)
                if mode != "cited":
                    return _deliver_dot(turn, text)
                language = settings.language
                if turn.delivery is None:
                    turn.delivery = delivery.snapshot(turn.platform or platform, home=hermes_home())
                return _deliver_cited(turn, language)
        except BaseException as error:
            code = incident_code()
            _report_failure("the cited-mode transformer failed", code, error, secret=secret if owned else "")
            if mode == "dot" or (mode is None and intent == "dot"):
                # D12: dot mode delivers the model's text untouched, so a failure of the pass-through
                # returns ``None`` and leaves the text in place. The mode was resolved affirmatively, so
                # this is never the undetermined case M-R4-1 removed.
                return None
            return _operational_refusal(code)
        finally:
            if owned:
                try:
                    _drop_turn(session_id, turn_id, home=home)
                except BaseException:
                    pass

    return transform_llm_output


def _deliver_cited(turn, language):
    """Compose, persist and return one cited answer. Raises on a failure the boundary turns into (c)."""
    if turn.refusals:
        final = verifier.refusal_text(language)
        entry, error = _write_entry(turn, "cited", final, _verification(turn, applied=True, ok=False), True)
        if error:
            return verifier.operational_refusal(incident_code(), language)
        return final
    blocks = list(turn.selections)
    verification = verifier.verify_display(blocks, turn.line_texts())
    if not verification.ok:
        final = verifier.refusal_text(language)
        _entry, error = _write_entry(turn, "cited", final, verification, True)
        if error:
            return verifier.operational_refusal(incident_code(), language)
        return final
    snap = turn.delivery
    sealed = bool(snap is not None and snap.seal)
    body = render.render_answer(language, blocks)
    final = verifier.sealed(body) if sealed else body
    if not sealed:
        final = "{0}\n\n{1}".format(final, delivery.withheld_note(snap if snap is not None else turn.platform))
    verification = verifier.Verification(
        text=final,
        ok=True,
        blocks=tuple(blocks),
        ungrounded=(),
        has_grounding=bool(turn.line_texts()),
        unbound=verification.unbound,
    )
    _entry, error = _write_entry(
        turn,
        "cited",
        final,
        verification,
        True,
        verified=sealed,
        seal_withheld=not sealed,
        transcript=body,
    )
    if error:
        return verifier.operational_refusal(incident_code(), language)
    return final


def _verification(turn, applied=True, ok=False, blocks=()):
    return verifier.Verification(
        text="",
        ok=ok,
        blocks=tuple(blocks),
        ungrounded=(),
        has_grounding=bool(turn.line_texts()),
    )


def _deliver_dot(turn, text):
    """Dot mode: the model's text passes intact, and the row records exactly that string (D12).

    This version of the plugin writes no seal, so there is no mark to detect and no text to rewrite: the
    transformer returns ``None`` (the host keeps the model's own text) and the entry stores the text that
    reaches the user, unchanged.
    """
    verification = _verification(turn, applied=False, ok=False)
    _entry, error = _write_entry(turn, "dot", text, verification, False, transcript=text)
    if error:
        print(
            "hermes-cited: the dot-mode audit entry could not be written: {0}".format(error),
            file=sys.stderr,
        )
    return None


def _write_entry(
    turn,
    mode,
    final,
    verification,
    applied,
    verified=False,
    seal_withheld=False,
    transcript="",
):
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
        "refusals": list(turn.refusals),
        "evidence": [
            {
                "call": place.get("call"),
                "pid": place.get("pid"),
                "uid": place.get("uid"),
                "number": place.get("n"),
                "document": place.get("document"),
                "heading": place.get("heading"),
                "position": place.get("position"),
                "lines": [
                    {"line": item.get("line"), "text": item.get("text")}
                    for item in place.get("lines") or []
                ],
            }
            for place in turn.passages
        ],
        "quoted_lines": [
            {
                "pid": line.pid,
                "call": line.call,
                "original": line.original,
                "position": line.position,
                "uid": line.uid,
                "passage": line.passage,
                "number": line.number,
                "text": line.text,
                "document": line.document,
                "heading": line.heading,
            }
            for line in turn.selections
        ],
        "transcript": transcript,
        "composition_note": messages.composition_note(_language()),
        "response": final,
        "delivery": (turn.delivery.as_dict() if isinstance(turn.delivery, delivery.Snapshot) else {}),
        "verifier": {
            "applied": bool(applied),
            "ok": bool(verification.ok),
            "verified": bool(verified),
            "blocks": len(verification.blocks),
            "ungrounded": list(verification.ungrounded),
            "unbound": list(getattr(verification, "unbound", ()) or ()),
            "grounding": len(turn.excerpts),
            "seal_withheld": bool(seal_withheld),
        },
    }
    secret = _secret()
    entry = audit.redact(entry, secret)
    try:
        return audit.append_entry(audit_path(), entry), None
    except Exception as error:
        return None, audit.redact("{0}: {1}".format(type(error).__name__, error), secret)


def read_settings():
    """The settings of this process, for the CLI and for tests."""
    return settings_from_env()
