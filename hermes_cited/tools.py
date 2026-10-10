"""The two native tools ``cited_search`` and ``cited_ask`` (H2).

Each handler returns a JSON envelope with the text Cited sent (the passages or the answer,
unchanged) and the structured content beside it. ``post_tool_call`` receives that same string as
``result``, so the cited-mode verifier and the audit log see exactly what Cited returned without
a second channel. A failure is a sentence, never an exception: Hermes keeps working.
"""

from __future__ import annotations

import json

from . import render
from .client import CitedError, call_tool_full, redact
from .config import settings_from_env

TOOLSET = "cited"
TOOL_NAMES = ("cited_search", "cited_ask", "cited_quote")

DEFAULT_SEARCH_LIMIT = 5
MAX_SEARCH_LIMIT = 8

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


def search(args, **kwargs) -> str:
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
    return _call("cited_search", call_arguments, _search_envelope)


def ask(args, **kwargs) -> str:
    """The ``cited_ask`` handler: an answer from the documents, with its citations."""
    arguments = dict(args or {})
    question = str(arguments.get("question") or "").strip()
    if not question:
        return "Cited could not answer: the `question` argument must be a non-empty string."
    call_arguments = {"question": question}
    session_id = arguments.get("sessionId")
    if session_id is not None and str(session_id).strip():
        call_arguments["sessionId"] = str(session_id)
    return _call("cited_ask", call_arguments, _ask_envelope)


def _call(name, arguments, build) -> str:
    token = ""
    try:
        settings = settings_from_env()
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


def parse_tool_result(raw) -> dict:
    """Recover the envelope of a Cited tool result; ``None`` when the string is not one."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(data, dict) or data.get("cited_tool") not in TOOL_NAMES:
        return None
    return data


def _places_of(envelope: dict):
    for key in ("passages", "citations"):
        for place in envelope.get(key) or []:
            if isinstance(place, dict):
                yield place


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
