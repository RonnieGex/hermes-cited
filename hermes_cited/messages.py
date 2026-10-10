"""The fixed, localized sentences of cited mode (H10, H12, D10, D11).

Every string the plugin puts in front of the user is one of these templates, chosen by ``CITED_LANGUAGE``
(``es`` by default). They are fixed: an error is never interpolated into an answer, only an incident code
and the name of the surface that withheld the seal. The templates live here so the render, the verifier and
the delivery policy never disagree about the wording.
"""

from __future__ import annotations

DEFAULT_LANGUAGE = "es"
LANGUAGES = ("es", "en")


def language_of(value) -> str:
    """The configured language, ``es`` when it is missing or unknown."""
    text = str(value or "").strip().lower().replace("_", "-")
    base = text.split("-")[0]
    return base if base in LANGUAGES else DEFAULT_LANGUAGE


REFUSAL = {
    "es": "No está en los documentos.",
    "en": "It is not in the documents.",
}

#: The operational refusal of a cited turn the plugin could not compose or record (H10). ``code`` is the
#: incident code. No error detail is ever interpolated, and the reserved mark is never written.
OPERATIONAL = {
    "es": (
        "No puedo entregar esta respuesta como verificada en modo cited (incidente {code}). No quedó "
        "registrada, así que no lleva el sello. Revisa la bitácora en $HERMES_HOME/cited/audit.jsonl y "
        "vuelve a preguntar, o cambia a modo dot con /dot."
    ),
    "en": (
        "I cannot deliver this answer as verified in cited mode (incident {code}). It was not recorded, so "
        "it does not carry the seal. Check the log at $HERMES_HOME/cited/audit.jsonl and ask again, or "
        "switch to dot mode with /dot."
    ),
}

#: Dot mode: the model's text was nothing but the reserved mark, so what is delivered is this note (D11).
SEAL_ONLY_NOTE = {
    "es": "La respuesta del modelo era solo el sello reservado y se retiró: no quedó nada más que mostrar.",
    "en": "The model's answer was only the reserved seal and it was removed: there was nothing else to show.",
}

#: A block or metadata of the turn contains the reserved mark, so the seal is withheld (M-R3-3).
MARK_RETAINED_NOTE = {
    "es": (
        "Nota: el texto de esta respuesta contiene la marca reservada que solo el plugin escribe; por eso "
        "el sello se retiene. El contenido se muestra tal como lo devolvieron los documentos."
    ),
    "en": (
        "Note: the text of this answer contains the reserved mark, which only the plugin writes, so the "
        "seal is withheld. The content is shown exactly as the documents returned it."
    ),
}

_MODE_CITED = {
    "es": (
        "Modo cited activado. El plugin escribe la respuesta: solo se muestran los renglones textuales que "
        "elijan `cited_search` y `cited_quote`, con su fuente y su sello. La prosa del modelo se descarta."
    ),
    "en": (
        "Cited mode is on. The plugin writes the answer: only the literal lines chosen with `cited_search` "
        "and `cited_quote` are shown, with their source and their seal. The model's prose is discarded."
    ),
}

_MODE_DOT = {
    "es": (
        "Modo dot activado. Cited sigue disponible cuando ayuda y ninguna respuesta se sella ni se "
        "reemplaza. /cited vuelve a activar el modo cited."
    ),
    "en": (
        "Dot mode is on. Cited is still there when it helps, and no answer is sealed or replaced. /cited "
        "turns cited mode back on."
    ),
}


def refusal_text(language) -> str:
    return REFUSAL[language_of(language)]


def operational_text(language, code) -> str:
    return OPERATIONAL[language_of(language)].format(code=str(code or "unknown"))


def seal_only_note(language) -> str:
    return SEAL_ONLY_NOTE[language_of(language)]


def mark_retained_note(language) -> str:
    return MARK_RETAINED_NOTE[language_of(language)]


def mode_text(language, mode) -> str:
    table = _MODE_CITED if str(mode or "").strip().lower() == "cited" else _MODE_DOT
    return table[language_of(language)]
