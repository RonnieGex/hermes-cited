"""The two native tools ``cited_search`` and ``cited_ask`` (H2).

Each handler returns a JSON envelope with the text Cited sent (the passages or the answer,
unchanged) and the structured content beside it. ``post_tool_call`` receives that same string as
``result``, so the cited-mode verifier and the audit log see exactly what Cited returned without
a second channel. A failure is a sentence, never an exception: Hermes keeps working.
"""

from __future__ import annotations

import json
import re

from . import config, render
from .client import CitedError, call_tool_full, call_tool_search, redact
from .config import settings_from_env

TOOLSET = "cited"
TOOL_NAMES = ("cited_search", "cited_ask", "cited_quote")
#: The handlers whose result is real evidence of Cited. ``cited_quote`` returns document text, so it is
#: a selection and never a source of new evidence (B-R4-2).
EVIDENCE_TOOLS = ("cited_search", "cited_ask")

DEFAULT_SEARCH_LIMIT = config.DEFAULT_SEARCH_LIMIT
MAX_SEARCH_LIMIT = config.MAX_SEARCH_LIMIT
MIN_SEARCH_LIMIT = config.MIN_SEARCH_LIMIT
MAX_SEARCH_QUERY = config.MAX_QUERY_LENGTH
_QUERY_PATTERN = re.compile(r"\S")

#: The wire v1 arguments of the search-only bridge: exactly ``$defs.arguments`` of the pinned schema.
SEARCH_WIRE_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "minLength": config.MIN_QUERY_LENGTH,
            "maxLength": MAX_SEARCH_QUERY,
            "pattern": "\\S",
        },
        "limit": {
            "type": "integer",
            "minimum": MIN_SEARCH_LIMIT,
            "maximum": MAX_SEARCH_LIMIT,
            "default": DEFAULT_SEARCH_LIMIT,
        },
    },
    "required": ["query"],
    "additionalProperties": False,
}

SEARCH_ONLY_DESCRIPTION = "Search unsealed document passages."

SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "The words to look for in the documents of the business.",
        },
        "limit": {
            "type": "integer",
            "minimum": 1,
            "maximum": MAX_SEARCH_LIMIT,
            "description": "How many passages to return, between 1 and {0}. {1} by default.".format(
                MAX_SEARCH_LIMIT, DEFAULT_SEARCH_LIMIT
            ),
        },
    },
    "required": ["query"],
}

ASK_SCHEMA = {
    "type": "object",
    "properties": {
        "question": {
            "type": "string",
            "description": "The question to answer from the documents of the business.",
        },
        "sessionId": {
            "type": "string",
            "description": "The same value across a conversation, so a follow-up keeps its thread.",
        },
    },
    "required": ["question"],
}

QUOTE_SCHEMA = {
    "type": "object",
    "properties": {
        "passage": {
            "type": "string",
            "description": "The `pid` of a passage of this turn, like `P1`, as the tool that returned it listed it.",
        },
        "lines": {
            "type": "array",
            "items": {"type": "integer", "minimum": 1},
            "description": "The line numbers of that passage to show, in order, as the passage's `lines` lists them.",
        },
    },
    "required": ["passage", "lines"],
}

SEARCH_DESCRIPTION = (
    "Read the passages of the Cited documents that match a query, with the document, the section, "
    "the position and the text of each one. Cite each passage by its number, like [1]. It never "
    "writes an answer and never calls a language model."
)

ASK_DESCRIPTION = (
    "Answer a question from the documents of Cited, with numbered citations and the passage each one "
    "came from. When the documents do not hold the answer it returns refused instead of inventing it; "
    "pass that refusal to the user."
)

QUOTE_DESCRIPTION = (
    "In cited mode, choose the exact lines the user will see. The plugin gives every passage of the turn a "
    "unique `pid` the moment it enters the turn: the first passage is `P1`, the next `P2`, and so on, so "
    "two searches that both return a passage 1 do not collide. Pass that `pid` as `passage` and the line "
    "numbers as `lines`; the tool returns the exact text of those lines and the plugin writes the answer "
    "from them. The model's own prose is discarded. A plain number is accepted only while it identifies "
    "exactly one passage of the turn."
)


def search(args, settings=None, **kwargs) -> str:
    """The ``cited_search`` handler: the passages of the documents that match a query."""
    arguments = dict(args or {})
    query = str(arguments.get("query") or "").strip()
    if not query:
        return "Cited could not search: the `query` argument must be a non-empty string."
    call_arguments = {"query": query}
    limit = arguments.get("limit")
    if limit is not None:
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            return "Cited could not search: the `limit` argument must be an integer between 1 and {0}.".format(
                MAX_SEARCH_LIMIT
            )
        if limit < 1 or limit > MAX_SEARCH_LIMIT:
            return "Cited could not search: the `limit` argument must be an integer between 1 and {0}.".format(
                MAX_SEARCH_LIMIT
            )
        call_arguments["limit"] = limit
    return _call("cited_search", call_arguments, _search_envelope, settings=settings)


def ask(args, settings=None, **kwargs) -> str:
    """The ``cited_ask`` handler: an answer from the documents, with its citations."""
    arguments = dict(args or {})
    question = str(arguments.get("question") or "").strip()
    if not question:
        return "Cited could not answer: the `question` argument must be a non-empty string."
    call_arguments = {"question": question}
    session_id = arguments.get("sessionId")
    if session_id is not None and str(session_id).strip():
        call_arguments["sessionId"] = str(session_id)
    return _call("cited_ask", call_arguments, _ask_envelope, settings=settings)


def _call(name, arguments, build, settings=None) -> str:
    token = ""
    try:
        settings = settings if settings is not None else settings_from_env()
        token = settings.token
        result = call_tool_full(name, arguments, settings)
    except CitedError as error:
        return str(error)
    except Exception as error:
        return redact(
            "Cited could not be called: {0}: {1}".format(type(error).__name__, error), token
        )
    built = build(result, arguments)
    if token and token in built:
        return (
            "Cited answered with a result that reflects the bearer token. The answer was discarded "
            "and nothing of it is shown or recorded."
        )
    return built


def validate_search_arguments(args):
    """The strict wire v1 arguments of search mode: no coercion, no trimming, no unknown property.

    Returns ``(arguments, error)``. A boolean, a float, a string limit, an out-of-range limit, a
    non-string query, an over-long query and a whitespace-only query are all refused here, before any
    request, because the schema and the handler must agree without coercing anything (H21).
    """
    if args is None:
        arguments = {}
    elif isinstance(args, dict):
        arguments = args
    else:
        return None, "Cited could not search: the arguments must be an object that carries a `query`."
    if any(not isinstance(key, str) for key in arguments):
        return None, "Cited could not search: argument names must be strings."
    unknown = sorted(set(arguments) - {"query", "limit"})
    if unknown:
        return None, "Cited could not search: `{0}` is not an argument of the search-only contract.".format(
            unknown[0]
        )
    if "query" not in arguments:
        return None, _QUERY_SENTENCE
    query = arguments["query"]
    if (
        not isinstance(query, str)
        or not config.MIN_QUERY_LENGTH <= len(query) <= MAX_SEARCH_QUERY
        or not _QUERY_PATTERN.search(query)
    ):
        return None, _QUERY_SENTENCE
    validated = {"query": query}
    if "limit" in arguments:
        limit = arguments["limit"]
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not MIN_SEARCH_LIMIT <= limit <= MAX_SEARCH_LIMIT
        ):
            return None, _LIMIT_SENTENCE
        validated["limit"] = limit
    return validated, ""


_QUERY_SENTENCE = (
    "Cited could not search: the `query` argument must be a string of 1 to {0} characters with at least "
    "one non-whitespace character.".format(MAX_SEARCH_QUERY)
)
_LIMIT_SENTENCE = "Cited could not search: the `limit` argument must be an integer between 1 and {0}.".format(
    MAX_SEARCH_LIMIT
)


def search_model_envelope(result, arguments) -> str:
    """The model-visible envelope of search mode: the JSON *string*, never the RPC wrapper (H21).

    It carries the unchanged query, the text block and every passage with its ``lines``, and it
    introduces no ``pid``, no seal and no audit field: the full-mode composition does not exist here.
    """
    passages = []
    for passage in result.passages:
        item = dict(passage)
        item["lines"] = render.numbered_lines(item.get("excerpt") or "")
        passages.append(item)
    envelope = {
        "cited_tool": "cited_search",
        "query": arguments.get("query", ""),
        "text": result.text,
        "passages": passages,
    }
    return json.dumps(envelope, ensure_ascii=False)


def search_only(args, registration) -> str:
    """The registered search handler: settings from its own profile, wire v1 and a redacted sentence.

    It never touches the audit log, the skill, the commands, the hooks or any file under the home, and it
    never requests ``CITED_MCP_TOKEN``.
    """
    try:
        settings = config.search_settings_for(registration)
    except config.CitedError as error:
        return str(error)
    except Exception:
        return "Cited could not search: the configuration of this profile could not be read."
    arguments, error = validate_search_arguments(args)
    if error:
        return redact(error, settings.token)
    try:
        result = call_tool_search(settings, arguments)
    except CitedError as error:
        return redact(str(error), settings.token)
    except Exception:
        # The transport categories are fixed sentences in the client; anything outside them is a fixed
        # sentence here too, so an exception's own text never reaches the model (M02, H21).
        return redact(
            "Cited could not be called: the search transport failed before an answer was read.",
            settings.token,
        )
    return redact(search_model_envelope(result, arguments), settings.token)


def _search_envelope(result, arguments) -> str:
    passages = result.structured.get("passages")
    if not isinstance(passages, list):
        return "Cited answered the search without its passages."
    envelope = {
        "cited_tool": "cited_search",
        "query": arguments.get("query", ""),
        "text": result.text,
        "passages": [_passage_of(item) for item in passages],
    }
    return json.dumps(envelope, ensure_ascii=False)


def _ask_envelope(result, arguments) -> str:
    structured = result.structured
    status = structured.get("status")
    answer = structured.get("answer")
    citations = structured.get("citations")
    if status not in ("answered", "refused") or not isinstance(answer, str) or not isinstance(citations, list):
        return "Cited answered the question without its status, its answer or its citations."
    envelope = {
        "cited_tool": "cited_ask",
        "question": arguments.get("question", ""),
        "text": result.text,
        "status": status,
        "answer": answer,
        "citations": [_passage_of(item, with_lead=True) for item in citations],
    }
    return json.dumps(envelope, ensure_ascii=False)


def _passage_of(raw, with_lead: bool = False) -> dict:
    if not isinstance(raw, dict):
        return {"n": 0, "document": "", "heading": None, "position": 0, "excerpt": str(raw), "lines": []}
    excerpt = raw.get("excerpt") if isinstance(raw.get("excerpt"), str) else ""
    passage = {
        "n": raw.get("n") if isinstance(raw.get("n"), int) else 0,
        "document": raw.get("document") if isinstance(raw.get("document"), str) else "",
        "heading": raw.get("heading") if isinstance(raw.get("heading"), str) else None,
        "position": raw.get("position") if isinstance(raw.get("position"), int) else 0,
        "excerpt": excerpt,
        "lines": render.numbered_lines(excerpt),
    }
    if with_lead:
        passage["lead"] = raw.get("lead") if isinstance(raw.get("lead"), int) else 0
    return passage


def parse_tool_result(raw, expected=None) -> dict:
    """Recover the envelope of a Cited tool result; ``None`` when the string is not one.

    ``expected`` names the handler that produced the result: the envelope's own ``cited_tool`` must match
    it, so a document that happens to be a valid envelope can never be presented as another call's
    evidence (B-R4-2).
    """
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(data, dict) or data.get("cited_tool") not in TOOL_NAMES:
        return None
    if expected is not None and data.get("cited_tool") != expected:
        return None
    return data


def _places_of(envelope: dict):
    for key in ("passages", "citations"):
        for place in envelope.get(key) or []:
            if isinstance(place, dict):
                yield place


def envelope_places(envelope: dict) -> list:
    """The place objects of an envelope, as the model received them, with their identifiers (M-R4-3)."""
    return [place for place in _places_of(envelope or {})]


def evidence_objects(envelope: dict) -> list:
    """The place objects of an envelope that carry a non-empty excerpt, in order (M-R4-3)."""
    objects = []
    for place in _places_of(envelope or {}):
        excerpt = place.get("excerpt")
        if isinstance(excerpt, str) and excerpt.strip():
            objects.append(place)
    return objects


def grounding_excerpts(envelope: dict) -> list:
    """The evidence of one Cited result: only the non-empty excerpt of every passage or citation.

    The transport text, the query, the generated answer, the headings, the positions and the counts
    are deliberately left out: a turn must never verify itself (B2/D2).
    """
    excerpts = []
    for place in _places_of(envelope):
        excerpt = place.get("excerpt")
        if isinstance(excerpt, str) and excerpt.strip():
            excerpts.append(excerpt)
    return excerpts


def excerpt_pairs(envelope: dict) -> list:
    """``(sha256, text)`` of every excerpt, so the log can prove its digests later (H5)."""
    from .audit import excerpt_digest

    pairs = []
    for place in _places_of(envelope):
        excerpt = place.get("excerpt")
        if isinstance(excerpt, str):
            pairs.append((excerpt_digest(excerpt), excerpt))
    return pairs


def evidence_places(envelope: dict) -> list:
    """The quotable places of one envelope, in order, with their document, section, lines and number.

    ``pid``, ``call`` and ``uid`` are empty here: the turn assigns them when the place enters the turn, so
    two searches of the same turn never collide (H14).
    """
    places = []
    for place in _places_of(envelope):
        excerpt = place.get("excerpt")
        if not isinstance(excerpt, str) or not excerpt.strip():
            continue
        number = place.get("n") if isinstance(place.get("n"), int) else 0
        heading = place.get("heading") if isinstance(place.get("heading"), str) else ""
        document = place.get("document") if isinstance(place.get("document"), str) else ""
        position = place.get("position") if isinstance(place.get("position"), int) else 0
        places.append(
            {
                "n": number,
                "document": document,
                "heading": heading,
                "position": position,
                "excerpt": excerpt,
                "lines": render.numbered_lines(excerpt),
                "pid": "",
                "call": 0,
                "uid": "",
            }
        )
    return places


def bound_places(envelope: dict) -> list:
    """The places of an envelope that already carry the identifiers the handler assigned (M-R4-3).

    The internal passage keeps the same ``pid``, ``call`` and ``uid`` the model received, so the hook
    never renumbers a passage that was already bound.
    """
    places = []
    for place in _places_of(envelope):
        excerpt = place.get("excerpt")
        if not isinstance(excerpt, str) or not excerpt.strip():
            continue
        number = place.get("n") if isinstance(place.get("n"), int) else 0
        heading = place.get("heading") if isinstance(place.get("heading"), str) else ""
        document = place.get("document") if isinstance(place.get("document"), str) else ""
        position = place.get("position") if isinstance(place.get("position"), int) else 0
        places.append(
            {
                "n": number,
                "document": document,
                "heading": heading,
                "position": position,
                "excerpt": excerpt,
                "lines": render.numbered_lines(excerpt),
                "pid": str(place.get("pid") or ""),
                "call": int(place.get("call") or 0) if isinstance(place.get("call"), int) else 0,
                "uid": str(place.get("uid") or ""),
            }
        )
    return places


def citation_numbers(envelope: dict) -> list:
    """The numbers the turn's passages and citations carry, for the ``[n]`` check of H4."""
    numbers = []
    for place in _places_of(envelope):
        number = place.get("n")
        if isinstance(number, int) and number > 0 and number not in numbers:
            numbers.append(number)
    return numbers


def refusals_of(envelope: dict) -> list:
    """The refusal sentences of a ``cited_ask`` result, so the turn answers with a refusal (D2)."""
    if envelope.get("cited_tool") != "cited_ask" or envelope.get("status") != "refused":
        return []
    answer = envelope.get("answer")
    return [answer.strip()] if isinstance(answer, str) and answer.strip() else ["Cited refused."]


def redact_result(raw: str, token: str) -> str:
    """A visible result with the bearer replaced, for the last line of defence of H6."""
    return redact(raw, token)


def excerpt_digests(envelope: dict) -> list:
    """The SHA-256 of every excerpt Cited returned, for the audit entry (H5)."""
    return [digest for digest, _ in excerpt_pairs(envelope)]


def source_labels(envelope: dict) -> list:
    """The document and section of every place, deduplicated, for the cited-mode seal."""
    labels = []
    for place in _places_of(envelope):
        document = place.get("document") if isinstance(place.get("document"), str) else ""
        heading = place.get("heading") if isinstance(place.get("heading"), str) else ""
        label = "{0} - {1}".format(document, heading) if heading else document
        label = label.strip()
        if label and label not in labels:
            labels.append(label)
    return labels
