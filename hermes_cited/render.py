"""The deterministic line division and the shielded render of cited mode (H11, H12, D5, D10).

Cited mode no longer verifies the model's prose: the model *chooses* numbered lines with ``cited_quote``
and this module builds the answer from them. A line is the exact substring between two line breaks of an
excerpt (a paragraph with no break is one line); the render copies it byte for byte and adds the mark and
the source, both generated here. Nothing in this module reads the model's text.

Round 4 shields two more paths of the reserved mark (M-R3-3): the document and the section are escaped into
a single line, so a metadata value can never inject a body or a mark; and ``contains_mark`` lets the
transformer detect a mark inside a chosen line or a metadata value, in which case the seal is withheld and a
fixed note is delivered instead (D13). ``strip_mark`` removes every occurrence of the mark from the model's
text in dot mode, Markdown presentation included.

Round 5 (M-R4-4) reads the mark in the **visible text** of the admitted Markdown presentations: internal
emphasis (``Verified **by** Cited``) and link labels (``Verified by [Cited](url)``) are the same reserved
mark, because that is what a reader sees. The detection builds the visible characters with the span of
each one in the original text, so the removal takes the whole presentation with it, and ``escape_meta``
escapes every interpretable Markdown metacharacter of a document or a section, not only the backslash and
the backtick.
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

#: The visible text of the reserved mark: a run of whitespace between the words, so a line break or the
#: markup of an emphasis does not hide it.
_SEAL_RE = re.compile(r"verified\s+by\s+cited(?![\w])", re.IGNORECASE)
#: A Markdown link or image: the label is the visible text and the target is not.
_LINK_RE = re.compile(r"!?\[([^\]\n]*)\]\([^)\n]*\)")
#: The markup that is not visible: emphasis, strong, strikethrough and code spans.
_INVISIBLE_CHARS = "*_~`"
#: A line that holds only decoration and punctuation: a mark-only line disappears with it.
_DECOR_ONLY_RE = re.compile(r"^[\s>*_#~`\-–—•·.,;:!?…¡¿«»\"'\[\]\(\)0-9]*$")
#: The Markdown characters a document or a section must never carry live (M-R4-4).
_META_CHARS = "\\`*_[]()#>~|<{}!"
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


def _visible_tokens(text):
    """``(char, start, end)`` of every visible character of the admitted Markdown presentations.

    A link or an image contributes its label; every label character carries the span of the whole
    construct, so a mark that ends inside a label takes the construct with it. The emphasis markup is
    not visible and contributes no token.
    """
    value = str(text or "")
    tokens = []
    position = 0
    for match in _LINK_RE.finditer(value):
        for index in range(position, match.start()):
            char = value[index]
            if char not in _INVISIBLE_CHARS:
                tokens.append((char, index, index + 1))
        for char in match.group(1):
            if char not in _INVISIBLE_CHARS:
                tokens.append((char, match.start(), match.end()))
        position = match.end()
    for index in range(position, len(value)):
        char = value[index]
        if char not in _INVISIBLE_CHARS:
            tokens.append((char, index, index + 1))
    return tokens


def mark_spans(text) -> list:
    """The ``(start, end)`` spans of the original text whose visible text is the reserved mark."""
    tokens = _visible_tokens(text)
    if not tokens:
        return []
    visible = "".join(item[0] for item in tokens)
    spans = []
    for match in _SEAL_RE.finditer(visible):
        spans.append((tokens[match.start()][1], tokens[match.end() - 1][2]))
    return spans


def contains_mark(text) -> bool:
    """True when the reserved mark is visible, in any casing and in any admitted presentation."""
    return bool(mark_spans(text))


def _remove_spans(text: str, spans) -> str:
    if not spans:
        return text
    kept = []
    position = 0
    for start, end in spans:
        kept.append(text[position:start])
        position = max(position, end)
    kept.append(text[position:])
    return "".join(kept)


def strip_mark(text) -> str:
    """The text without every occurrence of the reserved mark.

    A line that is only the mark (with or without decoration) disappears; a mark inside a line takes its
    decoration and the punctuation that followed it with it. Lines keep their order and their remaining
    characters.
    """
    value = str(text or "")
    if not contains_mark(value):
        return value
    kept = []
    for line in value.split("\n"):
        spans = mark_spans(line)
        cleaned = _remove_spans(line, spans)
        if spans and _DECOR_ONLY_RE.match(cleaned):
            continue
        cleaned = re.sub(r"[\s>*_#~`\-–—•·]{2,}", " ", cleaned).rstrip()
        if cleaned.strip() or not kept:
            kept.append(cleaned.rstrip())
    while kept and not kept[0].strip():
        kept.pop(0)
    while kept and not kept[-1].strip():
        kept.pop()
    return "\n".join(kept)


def _neutralise_mark(text: str) -> str:
    """Break the visible mark with a word joiner, so an escaped metadata value cannot read as the seal."""
    spans = mark_spans(text)
    if not spans:
        return text
    kept = []
    position = 0
    for start, end in spans:
        kept.append(text[position:start])
        kept.append(text[start:end].replace(" ", "\u2060"))
        position = max(position, end)
    kept.append(text[position:])
    return "".join(kept)


def escape_meta(value) -> str:
    """Document names and sections as escaped, single-line metadata (M-R3-3, M-R4-4).

    A line break becomes a space, every interpretable Markdown metacharacter is escaped, the reserved mark
    is neutralised so it can never read as the plugin's seal, and the result is capped, so a document name
    can never inject a body, a heading, a link, an emphasis or a mark.
    """
    text = str(value if value is not None else "")
    for old, new in (("\r\n", " "), ("\r", " "), ("\n", " "), ("\t", " ")):
        text = text.replace(old, new)
    text = " ".join(text.split())
    text = "".join("\\" + char if char in _META_CHARS else char for char in text)
    text = _neutralise_mark(text)
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

    def has_mark(self) -> bool:
        """Whether a line or its metadata carries the reserved mark, before escaping (M-R3-3)."""
        return contains_mark(self.text) or contains_mark(self.document) or contains_mark(self.heading)


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
