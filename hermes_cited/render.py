"""The deterministic line division and the plugin-written render of cited mode (H11, H12, D5, D12).

Cited mode no longer verifies the model's prose: the model *chooses* numbered lines with ``cited_quote``
and this module builds the answer from them. A line is the exact substring between two line breaks of an
excerpt (a paragraph with no break is one line); the render copies it byte for byte and adds the mark and
the source, both generated here. Nothing in this module reads the model's text.

Round 4 shielded the metadata: the document and the section are escaped into a single line, so a metadata
value can never inject a body, a link, an emphasis or a mark.

Round 8 (D12) retires the protection of the reserved mark. With D11 the plugin emits no seal on any route,
so no authentic seal exists that anyone could forge, and no hand-written reader of the host's Markdown
consumer reproduced the visible text without opening a new evasion or deleting legitimate text (rounds 3 to
7). ``strip_mark``, ``contains_mark``, ``consumer_visible``, ``SanitizationFailed`` and the fixed
sanitisation notes are gone from the product: dot mode delivers the model's text untouched and a cited
documentary line that carries the phrase is data like any other. The code stays in ``git log``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .messages import language_of, refusal_text as _refusal_text  # noqa: F401  (re-exported for callers)

SEAL = "Verified by Cited"
DEFAULT_LANGUAGE = "es"
LANGUAGES = ("es", "en")

ENTRY = {"es": "Según tus documentos:", "en": "From your documents:"}
REFUSAL = {"es": "No está en los documentos.", "en": "It is not in the documents."}
SOURCE_PREFIX = {"es": "Fuente:", "en": "Source:"}

#: The Markdown characters a document or a section must never carry live (M-R4-4). The ampersand is
#: escaped too, so a named entity of the metadata can never be interpreted by the consumer.
_META_CHARS = "\\`*_[]()#>~|<{}!&"
MAX_META = 200


def excerpt_lines(excerpt) -> list:
    """The lines of one excerpt: split by line break, ``\\r`` dropped, blank lines not numbered."""
    lines = []
    for raw in str(excerpt or "").split("\n"):
        line = raw.rstrip("\r")
        if line.strip():
            lines.append(line)
    return lines


def numbered_lines(excerpt) -> list:
    """The lines of one excerpt with their 1-based number, for the model and the render."""
    return [{"line": number, "text": text} for number, text in enumerate(excerpt_lines(excerpt), start=1)]


def escape_meta(value) -> str:
    """Document names and sections as escaped, single-line metadata (M-R3-3, M-R4-4).

    A line break becomes a space, every interpretable Markdown metacharacter is escaped and the result is
    capped, so a document name can never inject a body, a heading, a link or an emphasis.
    """
    text = str(value if value is not None else "")
    for old, new in (("\r\n", " "), ("\r", " "), ("\n", " "), ("\t", " ")):
        text = text.replace(old, new)
    text = " ".join(text.split())
    text = "".join("\\" + char if char in _META_CHARS else char for char in text)
    if len(text) > MAX_META:
        text = text[:MAX_META].rstrip() + "…"
    return text


@dataclass(frozen=True)
class Line:
    """One line the model chose: a full line of one passage of the turn."""

    passage: int
    number: int
    text: str
    document: str = ""
    heading: str = ""
    pid: str = ""
    call: int = 0
    original: int = 0
    position: int = 0
    uid: str = ""

    def identifier(self) -> str:
        """The unique identifier of the passage inside the turn, as the model passed it."""
        if self.pid:
            return str(self.pid)
        return str(int(self.number))

    def mark(self) -> str:
        """The ``[n]`` mark: the number of the passage inside the turn, never the model's text."""
        if self.pid:
            digits = re.sub(r"\D", "", str(self.pid))
            if digits:
                return "[{0}]".format(digits)
        return "[{0}]".format(int(self.original or self.passage or 0))

    def source(self) -> str:
        document = escape_meta(self.document).strip()
        heading = escape_meta(self.heading).strip()
        if document and heading:
            return "{0} - {1}".format(document, heading)
        return document or heading


def entry_text(language) -> str:
    return ENTRY[language_of(language)]


def refusal_text(language) -> str:
    return REFUSAL[language_of(language)]


def source_prefix(language) -> str:
    return SOURCE_PREFIX[language_of(language)]


def render_block(line: Line, language) -> str:
    """One chosen line, byte for byte, with its plugin-generated mark and its escaped source."""
    head = "{0} {1}".format(line.text, line.mark())
    source = line.source()
    if not source:
        return head
    return "{0}\n{1} {2}".format(head, source_prefix(language), source)


def render_answer(language, lines) -> str:
    """The body of a cited-mode answer: the entry template and the chosen blocks, no seal."""
    blocks = [render_block(line, language) for line in (lines or [])]
    if not blocks:
        return _refusal_text(language)
    return "{0}\n\n{1}".format(entry_text(language), "\n\n".join(blocks))
