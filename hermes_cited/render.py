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

Round 6 (M-R5-3) reads that visible text over the **whole** document: a soft line break, a named or
numeric entity (``Verified &#98;y Cited``, ``Verified&nbsp;by&nbsp;Cited``) and a reference link
(``Verified by [Cited][c]``) are the same mark, one span per occurrence. The removal is followed by the
postcondition of absence after normalising, and it repeats a bounded number of times because a removal can
concatenate the ends into a new mark; when it cannot complete, ``strip_mark`` raises
:class:`SanitizationFailed` and the transformer delivers a fixed safe note instead of the model's text.
``escape_meta`` also escapes the entity ampersand, so a document or a section can never read as the mark.

Round 7 (M-R6-1) reads that visible text with the **same consumer the host uses**: ``markdown_it`` of the
Hermes installation renders the document, every tag becomes a space and every entity is decoded, so an
entity inside a link label, a shortcut reference resolved against its definition and the line break an HTML
``<br>`` renders are one mark. ``consumer_visible`` is that text, ``consumer_mark`` is the detection on it,
and ``_visible_tokens`` maps each visible character back to the span of the original document that produced
it, so the removal takes the whole construct with the mark. The postcondition of ``strip_mark`` is checked
on that same render; when the map and the consumer disagree, the bounded removal gives up and the caller
delivers the fixed safe note, never the model's untransformed text.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

from .messages import language_of, refusal_text as _refusal_text  # noqa: F401  (re-exported for callers)

try:  # pragma: no cover - the host ships markdown_it; the fallback keeps the module importable alone
    from markdown_it import MarkdownIt as _MarkdownIt
except Exception:  # pragma: no cover
    _MarkdownIt = None

SEAL = "Verified by Cited"
DEFAULT_LANGUAGE = "es"
LANGUAGES = ("es", "en")

ENTRY = {"es": "Según tus documentos:", "en": "From your documents:"}
REFUSAL = {"es": "No está en los documentos.", "en": "It is not in the documents."}
SOURCE_PREFIX = {"es": "Fuente:", "en": "Source:"}

#: The visible text of the reserved mark: a run of whitespace between the words, so a line break or the
#: markup of an emphasis does not hide it.
_SEAL_RE = re.compile(r"verified\s+by\s+cited(?![\w])", re.IGNORECASE)
#: An HTML inline tag, the line break of ``<br>`` included: the consumer renders it and a text reader sees
#: a space, never the tag (M-R6-1).
_HTML_TAG_RE = re.compile(
    r"<!--.*?-->|<\?.*?\?>|<!\[CDATA\[.*?\]\]>|</?[A-Za-z][A-Za-z0-9-]*(?:\s+[^<>]*?)?\s*/?>",
    re.DOTALL,
)
#: A reference definition (``[label]: destination``): the consumer renders nothing for the line, so it is
#: not visible text and it resolves the shortcut and collapsed references of the document (M-R6-1).
_REF_DEF_RE = re.compile(r"(?m)^ {0,3}\[([^\]\n]+)\]:[ \t]*\S+(?:[ \t]+\S.*)?$")
#: A named or numeric character reference: what the consumer renders is the decoded character (M-R5-3).
_ENTITY_RE = re.compile(r"&(?:#[0-9]{1,7}|#[xX][0-9a-fA-F]{1,6}|[A-Za-z][A-Za-z0-9]{1,31});")
#: The markup that is not visible: emphasis, strong, strikethrough and code spans.
_INVISIBLE_CHARS = "*_~`"
#: The characters a backslash can escape in CommonMark; an escaped character is a literal, not markup.
_ASCII_PUNCT = set("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")
#: The sentinel that marks where a span of the reserved mark was removed (M-R5-3).
_SENTINEL = "\x00"
#: The bounded number of removal passes: a removal can concatenate the ends into a new mark.
MAX_SANITIZE_PASSES = 8
#: A line that holds only decoration and punctuation: a mark-only line disappears with it.
_DECOR_ONLY_RE = re.compile(r"^[\s>*_#~`\-–—•·.,;:!?…¡¿«»\"'\[\]\(\)0-9]*$")
#: The Markdown characters a document or a section must never carry live (M-R4-4, M-R5-3). The ampersand
#: is escaped too, so a named entity of the metadata can never read as the reserved mark.
_META_CHARS = "\\`*_[]()#>~|<{}!&"
MAX_META = 200


class SanitizationFailed(Exception):
    """The reserved mark could not be removed; the caller delivers a fixed safe note (M-R5-3)."""



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


def _decoded_entity(text, start):
    """``(decoded, end)`` of the character reference at *start*, or ``None`` when it is not one."""
    match = _ENTITY_RE.match(text, start)
    if match is None:
        return None
    value = html.unescape(match.group(0))
    if value == match.group(0):
        return None
    return value, match.end()


_MARKDOWN_RENDERER = None


def _renderer():
    """The Markdown consumer of the host, built once, or ``None`` when the module is not importable."""
    global _MARKDOWN_RENDERER
    if _MarkdownIt is None:
        return None
    if _MARKDOWN_RENDERER is None:
        _MARKDOWN_RENDERER = _MarkdownIt()
    return _MARKDOWN_RENDERER


def consumer_visible(text) -> str:
    """The visible text the supported consumer renders for *text* (M-R6-1).

    The module renders the document with ``markdown_it``, the consumer of the host, replaces every tag with
    a space, decodes every entity and collapses the whitespace, so the reading is the consumer's and not a
    second hand-written parser. Without the module the internal token reader is used instead, which is the
    conservative fallback of a host that does not ship it.
    """
    value = str(text or "")
    renderer = _renderer()
    if renderer is None:
        return " ".join(_internal_visible(value).split())
    rendered = renderer.render(value)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", rendered)).split())


def consumer_mark(text) -> bool:
    """True when the reserved mark is visible in the render of the supported consumer (M-R6-1)."""
    return bool(_SEAL_RE.search(consumer_visible(text)))


def _internal_visible(text) -> str:
    return "".join(item[0] for item in _visible_tokens(text))


def _normalize_label(value) -> str:
    """A reference label the way the consumer folds it: whitespace collapsed and case-insensitive."""
    return " ".join(str(value or "").split()).lower()


def _reference_definitions(value):
    """``(labels, spans)`` of the reference definitions of the document, which render nothing (M-R6-1)."""
    labels = set()
    spans = []
    for match in _REF_DEF_RE.finditer(value):
        label = _normalize_label(match.group(1))
        if label:
            labels.add(label)
            spans.append((match.start(), match.end()))
    return labels, spans


def _bracket_end(value, start):
    """The index just after the ``]`` that closes the ``[`` at *start*, or ``None``."""
    depth = 0
    index = start
    while index < len(value):
        char = value[index]
        if char == "\\":
            index += 2
            continue
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    return None


def _paren_end(value, start):
    """The index just after the ``)`` that closes the ``(`` at *start*, or ``None``."""
    depth = 0
    index = start
    while index < len(value):
        char = value[index]
        if char == "\\":
            index += 2
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    return None


def _link_construct(value, index, labels):
    """``(label, start, end, image)`` of the link or image at *index*, or ``None`` when it is not one.

    An inline link ``[label](destination)`` is always a link; a full, collapsed or shortcut reference is a
    link only when its label is one of the definitions of the document, exactly as the consumer resolves it
    (M-R6-1).
    """
    image = value[index] == "!"
    open_at = index + 1 if image else index
    if open_at >= len(value) or value[open_at] != "[":
        return None
    close = _bracket_end(value, open_at)
    if close is None:
        return None
    label = value[open_at + 1: close - 1]
    after = close
    if after < len(value) and value[after] == "(":
        end = _paren_end(value, after)
        if end is not None:
            return label, index, end, image
        return None
    if after < len(value) and value[after] == "[":
        end = _bracket_end(value, after)
        if end is not None:
            reference = value[after + 1: end - 1]
            target = label if not reference.strip() else reference
            if _normalize_label(target) in labels:
                return label, index, end, image
        return None
    if _normalize_label(label) in labels:
        return label, index, close, image
    return None


def _label_tokens(label, start, end):
    """The visible characters of a link label, each one carrying the span of the whole construct."""
    tokens = []
    index = 0
    while index < len(label):
        char = label[index]
        if char == "\\" and index + 1 < len(label) and label[index + 1] in _ASCII_PUNCT:
            tokens.append((label[index + 1], start, end))
            index += 2
            continue
        if char == "&":
            decoded = _decoded_entity(label, index)
            if decoded is not None:
                for item in decoded[0]:
                    tokens.append((item, start, end))
                index = decoded[1]
                continue
        if char not in _INVISIBLE_CHARS:
            tokens.append((char, start, end))
        index += 1
    return tokens


def _visible_tokens(text):
    """``(char, start, end)`` of every visible character of the supported Markdown presentations.

    A link or an image contributes its label; every label character carries the span of the whole
    construct, so a mark that ends inside a label takes the construct with it. The emphasis markup is not
    visible and contributes no token. A named or numeric character reference contributes the character the
    consumer renders, with the span of the whole reference, and a soft line break contributes its
    whitespace, so a mark broken across a line or written with entities is still the mark. A reference link
    contributes its label and not its reference, a definition contributes nothing, an image contributes a
    space and an HTML tag the consumer renders — the line break of ``<br>`` included — contributes a space
    too, which is what a reader of its render sees (M-R5-3, M-R6-1).
    """
    value = str(text or "")
    length = len(value)
    labels, definitions = _reference_definitions(value)
    tokens = []
    index = 0
    definition = 0
    while index < length:
        while definition < len(definitions) and definitions[definition][1] <= index:
            definition += 1
        if definition < len(definitions):
            start, end = definitions[definition]
            if start <= index < end:
                index = end
                continue
        char = value[index]
        if char == "\\" and index + 1 < length and value[index + 1] in _ASCII_PUNCT:
            tokens.append((value[index + 1], index, index + 2))
            index += 2
            continue
        if char == "<":
            match = _HTML_TAG_RE.match(value, index)
            if match is not None:
                tokens.append((" ", index, match.end()))
                index = match.end()
                continue
        if char == "&":
            decoded = _decoded_entity(value, index)
            if decoded is not None:
                for item in decoded[0]:
                    tokens.append((item, index, decoded[1]))
                index = decoded[1]
                continue
        if char in "![":
            construct = _link_construct(value, index, labels)
            if construct is not None:
                label, start, end, image = construct
                if image:
                    tokens.append((" ", start, end))
                else:
                    tokens.extend(_label_tokens(label, start, end))
                index = end
                continue
        if char not in _INVISIBLE_CHARS:
            tokens.append((char, index, index + 1))
        index += 1
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
    return consumer_mark(text)


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


def _blank_spans(text: str, spans) -> str:
    """The text with every span replaced by the sentinel, so a mark-only line can be told apart."""
    kept = []
    position = 0
    for start, end in spans:
        kept.append(text[position:start])
        kept.append(_SENTINEL)
        position = max(position, end)
    kept.append(text[position:])
    return "".join(kept)


def _tidy(value: str, spans) -> str:
    """Remove the spans and drop the lines that held nothing else, keeping every line with content."""
    blanked = _blank_spans(value, spans)
    kept = []
    for raw in blanked.split("\n"):
        line = raw.replace(_SENTINEL, "")
        line = re.sub(r"[\s>*_#~`\-–—•·]{2,}", " ", line).rstrip()
        if _SENTINEL in raw and not any(char.isalnum() for char in line):
            continue
        kept.append(line)
    while kept and not kept[0].strip():
        kept.pop(0)
    while kept and not kept[-1].strip():
        kept.pop()
    return "\n".join(kept)


def strip_mark(text) -> str:
    """The text without every occurrence of the reserved mark (M-R5-3, M-R6-1).

    The spans are computed over the **whole** document, so a mark broken across a line or written with
    entities, links, references or an HTML break is one span; they are removed, the result is normalised,
    and the postcondition of absence is checked **on the render of the supported consumer** before
    returning, not on the detector again. A removal can concatenate the ends of the text into a new mark, so
    the pass repeats a bounded number of times; when it cannot complete, the caller gets
    :class:`SanitizationFailed` and delivers the fixed safe note instead of the model's text. A line that
    held only the mark (and decoration) disappears; a line with any content keeps it.
    """
    value = str(text or "")
    for _ in range(MAX_SANITIZE_PASSES):
        if not contains_mark(value):
            return value
        spans = mark_spans(value)
        if not spans:
            break
        value = _tidy(value, spans)
    raise SanitizationFailed(
        "the reserved mark could not be removed after {0} passes".format(MAX_SANITIZE_PASSES)
    )


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
