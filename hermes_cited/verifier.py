"""The deterministic, non-AI verifier of cited mode (H4).

It extracts every number, unit, price and code from the final text and checks each one against
the passages Cited returned in the same turn. It never calls a model, never consults the question
and never guesses: a claim that is not literally in what Cited returned is not verified.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

SEAL = "Verified by Cited"

NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)*")
THOUSANDS_RE = re.compile(r"\d{1,3}(?:[.,]\d{3})+")
DECIMAL_RE = re.compile(r"\d+[.,]\d+")
CODED_RE = re.compile(r"\b[A-Z][A-Z0-9]*(?:[-/][A-Z0-9]+)+\b")
CODED_DIGITS_RE = re.compile(r"\b[A-Z]{2,}\d+[A-Z0-9]*\b")

UNIT_WORDS = (
    "peso", "pesos", "mxn", "dolar", "dolares", "dollars", "usd", "eur", "euro", "euros",
    "centavo", "centavos", "cent", "cents",
    "dia", "dias", "day", "days", "semana", "semanas", "week", "weeks",
    "mes", "meses", "month", "months", "ano", "anos", "year", "years",
    "hora", "horas", "hour", "hours", "minuto", "minutos", "minute", "minutes",
    "kg", "g", "mg", "km", "cm", "mm", "m", "l", "ml", "litro", "litros", "liters", "litres",
    "por ciento", "percent",
)


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
    """Casefold, drop accents and collapse whitespace so ``Afinación`` matches ``Afinacion``."""
    return " ".join(_strip_accents(str(text)).casefold().split())


def canonical_number(token: str) -> str:
    """A comparable form of one number: thousands separators out, decimals as a point."""
    value = str(token).strip().replace(" ", "")
    if THOUSANDS_RE.fullmatch(value):
        return re.sub(r"[.,]", "", value)
    if DECIMAL_RE.fullmatch(value):
        return value.replace(",", ".")
    return value


def _is_number(claim: str) -> bool:
    return bool(NUMBER_RE.fullmatch(claim))


def _is_code(claim: str) -> bool:
    return bool(CODED_RE.fullmatch(claim) or CODED_DIGITS_RE.fullmatch(claim))


def extract_claims(text: str) -> tuple:
    """Every number, unit, price and code of *text*, in order, without duplicates."""
    value = str(text or "")
    claims = []
    for match in NUMBER_RE.finditer(value):
        claims.append(match.group(0))
    for pattern in (CODED_RE, CODED_DIGITS_RE):
        for match in pattern.finditer(value):
            claims.append(match.group(0))
    normalized = normalize(value)
    for unit in UNIT_WORDS:
        if re.search(r"(?<![\w]){0}(?![\w])".format(re.escape(unit)), normalized):
            claims.append(unit)
    unique = []
    for claim in claims:
        if claim and claim not in unique:
            unique.append(claim)
    return tuple(unique)


def _corpus_facts(grounding_texts) -> tuple:
    corpus = "\n".join(str(text) for text in grounding_texts if text)
    numbers = {canonical_number(match.group(0)) for match in NUMBER_RE.finditer(corpus)}
    codes = set()
    codes.update(match.group(0).upper() for match in CODED_RE.finditer(corpus))
    codes.update(match.group(0).upper() for match in CODED_DIGITS_RE.finditer(corpus))
    return normalize(corpus), numbers, codes


def _has_word(normalized_corpus: str, word: str) -> bool:
    return bool(re.search(r"(?<![\w]){0}(?![\w])".format(re.escape(word)), normalized_corpus))


def verify(text: str, grounding_texts) -> Verification:
    """Check every claim of *text* against what Cited returned in this turn."""
    grounding = [str(item) for item in (grounding_texts or []) if str(item).strip()]
    claims = extract_claims(text)
    normalized_corpus, numbers, codes = _corpus_facts(grounding)
    ungrounded = []
    for claim in claims:
        if _is_number(claim):
            if canonical_number(claim) not in numbers:
                ungrounded.append(claim)
        elif _is_code(claim):
            if claim.upper() not in codes:
                ungrounded.append(claim)
        else:
            if not _has_word(normalized_corpus, normalize(claim)):
                ungrounded.append(claim)
    has_grounding = bool(grounding)
    return Verification(
        text=str(text or ""),
        ok=has_grounding and not ungrounded,
        claims=claims,
        ungrounded=tuple(ungrounded),
        has_grounding=has_grounding,
    )


def refusal(verification: Verification) -> str:
    """The refusal that replaces an answer the verifier could not ground, naming what failed."""
    if not verification.has_grounding:
        return (
            "In cited mode I cannot answer this: Cited returned no passage in this turn, so nothing "
            "in the answer could be verified. Ask again, or switch to dot mode with /dot."
        )
    return (
        "In cited mode I cannot give this answer: these values do not appear in the passages Cited "
        "returned in this turn: {0}. Nothing that is not in the documents is stated here. Ask again, "
        "or switch to dot mode with /dot.".format(", ".join(verification.ungrounded))
    )


def seal(verification: Verification, sources) -> str:
    """The verified text with the seal and the sources Cited gave it."""
    labels = [str(label).strip() for label in (sources or []) if str(label).strip()]
    parts = [verification.text.rstrip(), "", SEAL]
    if labels:
        parts.append("Sources:")
        parts.extend("- {0}".format(label) for label in labels)
    return "\n".join(parts)
