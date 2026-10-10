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

#: D11.3/H16: every audit entry carries this sentence, so a reader never mistakes the row for a record of
#: the terminal message the host delivered.
COMPOSITION_NOTE = {
    "es": (
        "esta fila registra la composicion del plugin; el host puede mostrar borradores mientras se genera "
        "y agregar avisos propios al final, asi que la fila no es constancia del mensaje terminal."
    ),
    "en": (
        "this row registers the plugin's composition; the host may show drafts while the answer is written "
        "and add its own notices at the end, so the row is not a record of the terminal message."
    ),
}

_MODE_CITED = {
    "es": (
        "Modo cited activado. El plugin compone la respuesta: solo se muestran los renglones textuales que "
        "elijan `cited_search` y `cited_quote`, con su fuente. La prosa del modelo se descarta. El sello "
        "`Verified by Cited` no se emite mientras el host no exponga un contrato de entrega acreditable, "
        "asi que la respuesta lleva la nota fija que dice que el sello se retiene. La promesa es sobre el "
        "mensaje final que compone el plugin, no sobre los borradores que el host pueda mostrar mientras se "
        "genera ni sobre los avisos que agregue al final."
    ),
    "en": (
        "Cited mode is on. The plugin composes the answer: only the literal lines chosen with "
        "`cited_search` and `cited_quote` are shown, with their source. The model's prose is discarded. "
        "The seal `Verified by Cited` is not emitted while the host exposes no accreditable delivery "
        "contract, so the answer carries the fixed note that says the seal is withheld. The promise is "
        "about the final message the plugin composes, not about the drafts the host may show while the "
        "answer is written or the notices it adds at the end."
    ),
}

_MODE_DOT = {
    "es": (
        "Modo dot activado. Cited sigue disponible cuando ayuda. Nada en modo dot está verificado, diga lo "
        "que diga el texto: esta versión del plugin no escribe ningún sello, así que la frase "
        "`Verified by Cited` en una respuesta nunca viene del plugin, y el texto del modelo se entrega "
        "intacto. El registro guarda exactamente el texto que se entrega. /cited vuelve a activar el modo "
        "cited."
    ),
    "en": (
        "Dot mode is on. Cited is still there when it helps. Nothing in dot mode is verified, whatever the "
        "text says: this version of the plugin writes no seal, so the phrase `Verified by Cited` in an "
        "answer never comes from the plugin, and the model's text is delivered intact. The record stores "
        "exactly the text that is delivered. /cited turns cited mode back on."
    ),
}


def refusal_text(language) -> str:
    return REFUSAL[language_of(language)]


def operational_text(language, code) -> str:
    return OPERATIONAL[language_of(language)].format(code=str(code or "unknown"))


def composition_note(language) -> str:
    """The fixed sentence that says what an audit row registers (D11.3)."""
    return COMPOSITION_NOTE[language_of(language)]


def mode_text(language, mode) -> str:
    table = _MODE_CITED if str(mode or "").strip().lower() == "cited" else _MODE_DOT
    return table[language_of(language)]
