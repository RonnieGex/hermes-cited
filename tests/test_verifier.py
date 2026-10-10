"""The by-construction verifier of cited mode and its fixed refusal (H4, H12, D5).

The verifier no longer reads prose. It asserts that every block the plugin is about to display is
*identical* to a full line of an excerpt of the turn: no Unicode normalisation, no substring, no word
list. A wrong subject, a changed sign, a changed currency, a moved value or a forged seal never occurs
because the block can only come from a line.
"""

from __future__ import annotations

from hermes_cited import render, verifier

EXCERPTS = [
    "Precios\n- Espresso: 35 pesos.\n- Afinacion de bicicleta: 380 pesos.",
    "Every repair carries a guarantee of 90 days from the day of delivery.",
]

TURN_LINES = {
    "Precios",
    "- Espresso: 35 pesos.",
    "- Afinacion de bicicleta: 380 pesos.",
    "Every repair carries a guarantee of 90 days from the day of delivery.",
}


def line(passage, number, text, document="doc.md", heading=""):
    return render.Line(passage=passage, number=number, text=text, document=document, heading=heading)


def test_a_full_line_of_an_excerpt_passes():
    result = verifier.verify_display([line(1, 3, "- Afinacion de bicicleta: 380 pesos.")], TURN_LINES)
    assert result.ok is True
    assert result.ungrounded == ()


def test_a_changed_datum_cannot_pass_even_if_it_looks_right():
    result = verifier.verify_display([line(1, 3, "- Afinacion de bicicleta: 1380 pesos.")], TURN_LINES)
    assert result.ok is False
    assert result.ungrounded


def test_a_substring_of_a_line_does_not_pass():
    result = verifier.verify_display([line(1, 3, "380 pesos.")], TURN_LINES)
    assert result.ok is False


def test_a_swapped_subject_does_not_pass():
    result = verifier.verify_display([line(1, 3, "Espresso: 380 pesos.")], TURN_LINES)
    assert result.ok is False


def test_no_normalisation_is_applied():
    """Uppercase, accents and a narrow space are a different string; the line must be copied exactly."""
    assert verifier.verify_display([line(1, 3, "- AFINACION DE BICICLETA: 380 PESOS.")], TURN_LINES).ok is False
    assert verifier.verify_display([line(1, 3, "- Afinación de bicicleta: 380 pesos.")], TURN_LINES).ok is False
    assert verifier.verify_display([line(2, 1, "Every repair carries a guarantee of 90 days.")], TURN_LINES).ok is False


def test_a_full_line_of_the_english_excerpt_passes():
    result = verifier.verify_display(
        [line(2, 1, "Every repair carries a guarantee of 90 days from the day of delivery.")], TURN_LINES
    )
    assert result.ok is True


def test_no_block_is_a_refusal_without_grounding():
    result = verifier.verify_display([], TURN_LINES)
    assert result.ok is False
    assert result.has_grounding is True


def test_a_turn_without_any_line_cannot_pass():
    result = verifier.verify_display([line(1, 1, "Precios")], set())
    assert result.ok is False
    assert result.has_grounding is False


def test_the_refusal_is_the_fixed_template_in_the_configured_language():
    assert verifier.refusal_text("es") == "No está en los documentos."
    assert verifier.refusal_text("en") == "It is not in the documents."
    assert verifier.SEAL not in verifier.refusal_text("es")


def test_the_seal_is_never_part_of_the_body():
    body = render.render_answer("es", [line(1, 3, "- Afinacion de bicicleta: 380 pesos.")])
    assert verifier.SEAL not in body
    assert verifier.SEAL in verifier.sealed(body)


def test_the_operational_refusal_never_carries_the_seal():
    text = verifier.operational_refusal("PermissionError: synthetic read-only log")
    assert verifier.SEAL not in text
    assert "could not be written" in text


def test_a_dot_mode_text_that_writes_the_seal_is_stripped():
    text = "La afinacion cuesta 380 pesos.\n\nVerified by Cited"
    stripped = verifier.strip_seal(text)
    assert verifier.SEAL not in stripped
    assert "380 pesos" in stripped


def test_stripping_a_text_without_the_seal_returns_it_unchanged():
    text = "La afinacion cuesta 380 pesos."
    assert verifier.strip_seal(text) == text
