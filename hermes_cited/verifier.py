"""The deterministic, non-AI verifier of cited mode (H4).

Cited mode is *extractive*. The evidence of a turn is only the non-empty excerpts Cited returned in
that same turn. A response segment (sentence or line) that carries a datum — a number, a unit, a
currency, a date or a code — is accepted only when the segment appears verbatim, after Unicode and
whitespace normalisation on both sides, inside one of those excerpts. Free text outside ``« »``
cannot carry a datum: prose may not restate a value. Citation marks such as ``[1]`` are validated
separately against the citation map of the turn and never count as data. The verifier never calls a
model and never reads the question.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

SEAL = "Verified by Cited"

CITATION_RE = re.compile(r"\[(\d{1,3})\]")
QUOTED_RE = re.compile(r"«([^«»]*)»|“([^“”]*)”|\"([^\"]*)\"|„([^“”]*)“")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?;])\s+")

DIGIT_RE = re.compile(r"\d")
NUMBER_RE = re.compile(r"[+-]?\d+(?:[.,]\d+)*")

CURRENCY_SYMBOLS = "$€£¥₱₹₽₩₺₴₦₲₡₵"
CURRENCY_WORDS = (
    "peso", "pesos", "mxn", "dolar", "dolares", "dollar", "dollars", "usd", "eur", "euro", "euros",
    "centavo", "centavos", "cent", "cents", "libra", "libras", "yen", "yenes", "real", "reales",
)
NUMBER_WORDS = (
    "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez", "once", "doce",
    "trece", "catorce", "quince", "dieciseis", "diecisiete", "dieciocho", "diecinueve", "veinte",
    "veintiuno", "veintidos", "veintitres", "veinticuatro", "veinticinco", "veintiseis",
    "veintisiete", "veintiocho", "veintinueve", "treinta", "cuarenta", "cincuenta", "sesenta",
    "setenta", "ochenta", "noventa", "cien", "ciento", "doscientos", "trescientos",
    "cuatrocientos", "quinientos", "seiscientos", "setecientos", "ochocientos", "novecientos",
    "mil", "millon", "millones",
    "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
    "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty",
    "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety", "hundred", "thousand",
    "million",
)

_CURRENCY_RE = re.compile(r"(?<![\w])(?:{0})(?![\w])".format("|".join(CURRENCY_WORDS)))
_NUMBER_WORD_RE = re.compile(r"(?<![\w])(?:{0})(?![\w])".format("|".join(NUMBER_WORDS)))
_DATA_RES = (_CURRENCY_RE, _NUMBER_WORD_RE)


@dataclass(frozen=True)
class Segment:
    """One piece of the response: a line or a sentence, and whether it was quoted."""

    text: str
    quoted: bool


@dataclass(frozen=True)
class Verification:
    text: str
    ok: bool
    claims: tuple
    ungrounded: tuple
    has_grounding: bool


def _strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(character for character in decomposed if not unicodedata.combining(character))


def normalize(text: str) -> str:
    """NFKC (fullwidth, superscripts, narrow spaces), accents off, casefold, whitespace collapsed.

    The same function is applied to the response segment and to the excerpt, so the comparison is
    literal after the normalisation both sides share. A space between digit groups (including the
    narrow no-break space that NFKC turns into a space) is a thousands separator and is removed on
    both sides.
    """
    value = unicodedata.normalize("NFKC", str(text))
    value = _strip_accents(value).casefold()
    value = re.sub(r"\s+([.,;:!?])", r"\1", value)
    value = " ".join(value.split())
    previous = None
    while previous != value:
        previous = value
        value = re.sub(r"(?<=\d) (?=\d{3}(?!\d))", "", value)
    return value


def without_citations(text: str) -> str:
    """The text with its ``[n]`` marks removed, so a mark is never read as a quantity."""
    return CITATION_RE.sub(" ", str(text or ""))


def data_markers(text: str) -> tuple:
    """The data of one segment: digit runs, currency symbols and words, written numerals."""
    value = normalize(without_citations(text))
    markers = []
    for match in NUMBER_RE.finditer(value):
        markers.append(match.group(0))
    for character in value:
        if character in CURRENCY_SYMBOLS:
            markers.append(character)
    for pattern in _DATA_RES:
        for match in pattern.finditer(value):
            markers.append(match.group(0))
    unique = []
    for marker in markers:
        if marker and marker not in unique:
            unique.append(marker)
    return tuple(unique)


def has_data(text: str) -> bool:
    return bool(data_markers(text))


def _masked_text(text: str) -> tuple:
    """The text with the quote delimiters removed, plus a per-character "inside a quote" mask."""
    chars = []
    flags = []
    position = 0
    for match in QUOTED_RE.finditer(text):
        outside = text[position:match.start()]
        chars.extend(outside)
        flags.extend([False] * len(outside))
        inner = next((group for group in match.groups() if group is not None), "")
        chars.extend(inner)
        flags.extend([True] * len(inner))
        position = match.end()
    tail = text[position:]
    chars.extend(tail)
    flags.extend([False] * len(tail))
    return "".join(chars), flags


def split_segments(text: str) -> list:
    """The reader-visible segments of a response: a sentence or a line, quotes stripped.

    A segment is *quoted* when the characters it is made of came from between ``« »``. The reader
    sees the quotation without its delimiters, so that is what the verifier compares: a value with
    the wrong subject ("Espresso: 380 pesos") never appears verbatim in the excerpt.
    """
    visible, flags = _masked_text(str(text or ""))
    segments = []
    offset = 0
    for raw_line in visible.split("\n"):
        line = raw_line.rstrip("\r")
        bounds = []
        cursor = 0
        for match in re.finditer(r"(?<=[.!?;])\s+", line):
            bounds.append((cursor, match.start()))
            cursor = match.end()
        bounds.append((cursor, len(line)))
        for start_in_line, end_in_line in bounds:
            piece = line[start_in_line:end_in_line]
            cleaned = piece.strip().strip("-*•#> \t\r\n")
            if not cleaned:
                continue
            start = offset + start_in_line
            end = offset + end_in_line
            quoted = any(
                flags[index]
                for index in range(start, min(end, len(flags)))
                if not visible[index].isspace()
            )
            segments.append(Segment(cleaned, quoted))
        offset += len(raw_line) + 1
    return segments


def citation_marks(text: str) -> tuple:
    return tuple(int(match.group(1)) for match in CITATION_RE.finditer(str(text or "")))


def verify(text: str, excerpts, citations=()) -> Verification:
    """Check every datum-bearing segment of *text* against the excerpts of this turn.

    ``citations`` is the set of numbers the turn's passages and citations carry, for the ``[n]``
    check. An empty set means the turn offered no citable source at all.
    """
    evidence = [str(item) for item in (excerpts or []) if str(item).strip()]
    normalized_excerpts = [normalize(item) for item in evidence]
    valid_marks = {int(number) for number in (citations or [])}
    claims = []
    ungrounded = []
    segments = split_segments(text)
    for segment in segments:
        markers = data_markers(segment.text)
        claims.extend(markers)
        if not markers:
            continue
        if not segment.quoted:
            ungrounded.append(segment.text)
            continue
        needle = normalize(without_citations(segment.text))
        if not needle or not any(needle in excerpt for excerpt in normalized_excerpts):
            ungrounded.append(segment.text)
    for mark in citation_marks(text):
        if mark not in valid_marks:
            ungrounded.append("[{0}]".format(mark))
    unique_claims = tuple(dict.fromkeys(claims))
    unique_ungrounded = tuple(dict.fromkeys(ungrounded))
    has_grounding = bool(evidence)
    return Verification(
        text=str(text or ""),
        ok=has_grounding and not unique_ungrounded,
        claims=unique_claims,
        ungrounded=unique_ungrounded,
        has_grounding=has_grounding,
    )


def refusal(verification: Verification, refused_reason: str = "") -> str:
    """The refusal that replaces an answer the verifier could not ground, naming what failed."""
    if refused_reason:
        return (
            "In cited mode I cannot answer this: Cited declined to answer from the documents of this "
            "installation ({0}). Nothing that is not in the documents is stated here. Ask again, or "
            "switch to dot mode with /dot.".format(refused_reason)
        )
    if not verification.has_grounding:
        return (
            "In cited mode I cannot answer this: Cited returned no excerpt in this turn, so nothing "
            "in the answer could be verified. Ask again, or switch to dot mode with /dot."
        )
    named = ", ".join("«{0}»".format(item) for item in verification.ungrounded)
    return (
        "In cited mode I cannot give this answer: these segments do not appear verbatim in the "
        "excerpts Cited returned in this turn: {0}. Copy each one between « » exactly as the excerpt "
        "writes it, or switch to dot mode with /dot.".format(named)
    )


def operational_refusal(detail: str) -> str:
    """The refusal of a turn whose answer could not be recorded, so it carries no seal (H10)."""
    return (
        "In cited mode I cannot deliver this answer as verified: the audit log could not be written "
        "({0}), so this answer was not recorded. Fix the log and ask again, or switch to dot mode "
        "with /dot.".format(str(detail or "unknown error"))
    )


def seal(verification: Verification, sources) -> str:
    """The verified text with the seal and the sources Cited gave it."""
    labels = [str(label).strip() for label in (sources or []) if str(label).strip()]
    parts = [verification.text.rstrip(), "", SEAL]
    if labels:
        parts.append("Sources:")
        parts.extend("- {0}".format(label) for label in labels)
    return "\n".join(parts)
