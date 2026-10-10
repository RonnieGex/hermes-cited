"""The by-construction verifier of cited mode and its fixed refusal (H4, H12, D5).

The verifier no longer reads prose. It asserts that every block the plugin is about to display is
*identical* to a full line of an excerpt of the turn and that it carries the identifier of its passage
(H14): no Unicode normalisation, no substring, no word list. A wrong subject, a changed sign, a changed
currency, a moved value or a forged seal never occurs because the block can only come from a line.
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


def line(passage, number, text, document="doc.md", heading="", pid=None):
    return render.Line(
        passage=passage,
        number=number,
        text=text,
        document=document,
        heading=heading,
        pid=pid if pid is not None else "P{0}".format(passage),
        original=passage,
    )


def test_a_full_line_of_an_excerpt_passes():
    result = verifier.verify_display([line(1, 3, "- Afinacion de bicicleta: 380 pesos.")], TURN_LINES)
    assert result.ok is True
    assert result.ungrounded == ()
    assert result.unbound == ()


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


def test_a_block_without_an_identifier_is_not_bound():
    """H14: a block must carry the identifier of the passage it came from."""
    orphan = render.Line(passage=1, number=3, text="- Afinacion de bicicleta: 380 pesos.")
    result = verifier.verify_display([orphan], TURN_LINES)
    assert result.ok is False
    assert result.unbound


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


def test_the_operational_refusal_carries_a_code_and_never_the_seal():
    """H10: the generic boundary text of the plugin, with an incident code and no error detail."""
    text = verifier.operational_refusal("CITED-9F3A21B7", "es")
    assert verifier.SEAL not in text
    assert "CITED-9F3A21B7" in text
    assert "No puedo entregar" in text
    assert verifier.operational_refusal("CITED-9F3A21B7", "en").startswith("I cannot deliver")
    assert "PermissionError" not in text


def test_the_seal_removal_is_retired():
    """D12: there is no seal to remove, so the verifier ships no removal."""
    assert not hasattr(verifier, "strip_seal")
