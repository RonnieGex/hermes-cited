"""The extractive verifier and the cited-mode refusal and seal (H4, D2, M1).

The rule: a response segment (sentence or line) that carries a datum is accepted only when it
appears verbatim, after Unicode and whitespace normalisation on both sides, inside an excerpt Cited
returned in the same turn, and only when it is written between « ». Free text cannot carry a datum.
"""

from __future__ import annotations

import pytest

from hermes_cited import verifier

EXCERPTS = [
    "Precios\n- Espresso: 35 pesos.\n- Afinación de bicicleta: 380 pesos.",
    "Every repair carries a guarantee of 90 days from the day of delivery.",
]


def quoted(text):
    return "«{0}»".format(text)


def test_a_copied_segment_passes():
    result = verifier.verify(quoted("Afinación de bicicleta: 380 pesos.") + " [1]", EXCERPTS, [1])
    assert result.ok is True
    assert result.ungrounded == ()


def test_a_copied_answer_is_sealed_with_its_sources():
    result = verifier.verify(quoted("Afinación de bicicleta: 380 pesos."), EXCERPTS, [1])
    assert result.ok
    sealed = verifier.seal(result, ["cafe-la-horquilla.md - Precios"])
    assert sealed.startswith("«Afinación de bicicleta: 380 pesos.»")
    assert "Verified by Cited" in sealed
    assert "cafe-la-horquilla.md - Precios" in sealed


def test_a_reworded_datum_is_refused_and_named():
    result = verifier.verify("La afinación cuesta 380 pesos [1].", EXCERPTS, [1])
    assert result.ok is False
    assert any("380 pesos" in item for item in result.ungrounded)
    refusal = verifier.refusal(result)
    assert "380 pesos" in refusal
    assert "Verified by Cited" not in refusal


def test_free_text_cannot_carry_a_datum():
    result = verifier.verify("El total es 380 [1].", EXCERPTS, [1])
    assert result.ok is False
    assert any("El total es 380" in item for item in result.ungrounded)


def test_a_reworded_answer_with_no_datum_passes():
    result = verifier.verify("Está en la lista de precios del café.", EXCERPTS, [1, 2])
    assert result.ok is True


def test_a_number_only_in_the_question_is_not_grounded():
    result = verifier.verify("Son 999 y 2 afinaciones.", EXCERPTS, [1])
    assert result.ok is False
    assert result.ungrounded


def test_an_ungrounded_unit_is_refused():
    result = verifier.verify(quoted("Afinación de bicicleta: 380 euros."), EXCERPTS, [1])
    assert result.ok is False


def test_accents_case_and_whitespace_do_not_matter():
    assert verifier.verify(quoted("Afinacion de bicicleta: 380 PESOS."), EXCERPTS, [1]).ok
    assert verifier.verify(quoted("Afinación de bicicleta: 380 pesos."), EXCERPTS, [1]).ok
    assert verifier.verify(quoted("El total es 1 200 pesos."), ["El total es 1200 pesos."]).ok


def test_an_ambiguous_separator_is_literal():
    assert verifier.verify(quoted("El total es 1,200 pesos."), ["El total es 1,200 pesos."]).ok
    assert verifier.verify(quoted("El total es 1,200 pesos."), ["El total es 1200 pesos."]).ok is False
    assert verifier.verify(quoted("Dosis 1.200 mg."), ["Dosis 1200 mg."]).ok is False
    assert verifier.verify(quoted("Dosis 1.200 mg."), ["Dosis 1.200 mg."]).ok


def test_fullwidth_and_superscript_digits_are_normalised():
    assert verifier.verify(quoted("Cuesta ３８０ pesos."), ["Cuesta 380 pesos."]).ok
    result = verifier.verify(quoted("Cuesta ⁹⁹⁹ pesos."), ["Cuesta 380 pesos."])
    assert result.ok is False
    assert "999" in result.claims


def test_a_decimal_must_be_literal():
    assert verifier.verify(quoted("Cuesta 380.50 pesos."), ["Cuesta 380.50 pesos."]).ok
    assert verifier.verify(quoted("Cuesta 380.75 pesos."), ["Cuesta 380.50 pesos."]).ok is False


def test_english_units_of_time_are_checked():
    assert verifier.verify(
        quoted("Every repair carries a guarantee of 90 days from the day of delivery."), EXCERPTS, [2]
    ).ok
    assert verifier.verify(quoted("Every repair carries a guarantee of 30 days."), EXCERPTS, [2]).ok is False


def test_a_turn_without_any_excerpt_cannot_pass():
    result = verifier.verify(quoted("Cuesta 380 pesos."), [])
    assert result.ok is False
    assert result.has_grounding is False
    refusal = verifier.refusal(result)
    assert "Cited" in refusal


def test_a_transport_text_is_not_evidence():
    transport = 'Cited found 0 passage(s) for "999 pesos". Cite each one by its number, like [1].'
    result = verifier.verify(quoted("Cuesta 999 pesos."), [], [])
    assert result.ok is False
    assert transport  # the string exists, but it is never passed as evidence


def test_a_code_is_checked():
    assert verifier.verify(quoted("Pide el RFC-1234."), ["Pide el RFC-1234."]).ok
    assert verifier.verify(quoted("Pide el RFC-9999."), ["Pide el RFC-1234."]).ok is False


def test_a_citation_mark_is_checked_against_the_map():
    result = verifier.verify(quoted("Afinación de bicicleta: 380 pesos.") + " [3]", EXCERPTS, [1])
    assert result.ok is False
    assert "[3]" in result.ungrounded
    assert "3" not in result.claims


def test_a_citation_mark_is_never_read_as_a_quantity():
    result = verifier.verify(quoted("Afinación de bicicleta: 380 pesos.") + " [1]", EXCERPTS, [1])
    assert result.ok is True


def test_every_case_of_the_m1_table_is_refused():
    cases = [
        ("Cuesta €380.", "Cuesta $380."),
        ("Saldo: -380 pesos.", "Saldo: 380 pesos."),
        ("Fecha 10/09/2026.", "Fecha 09/10/2026."),
        ("Código xyz-123.", "Código abc-123."),
        ("Cuesta novecientos pesos.", "Cuesta trescientos pesos."),
        ("Dosis 5 mcg.", "Dosis 5 mg."),
    ]
    for answer, excerpt in cases:
        result = verifier.verify(quoted(answer), [excerpt])
        assert result.ok is False, answer
        assert result.ungrounded, answer


def test_a_swapped_subject_is_refused():
    result = verifier.verify(
        quoted("Espresso: 380 pesos."),
        ["Espresso: 35 pesos. Afinación: 380 pesos."],
    )
    assert result.ok is False


def test_a_value_glued_to_a_wrong_free_subject_is_refused():
    """The reader sees "Espresso: 380 pesos"; that line is not in the excerpt."""
    result = verifier.verify(
        "Espresso: «380 pesos.»",
        ["Espresso: 35 pesos. Afinación: 380 pesos."],
    )
    assert result.ok is False
    assert any("Espresso" in item for item in result.ungrounded)


def test_a_value_glued_to_its_own_subject_passes():
    result = verifier.verify(
        "Afinación de bicicleta: «380 pesos.»",
        ["Espresso: 35 pesos. Afinación de bicicleta: 380 pesos."],
    )
    assert result.ok is True


def test_plain_text_without_quotes_and_with_a_datum_is_refused():
    assert verifier.verify("Afinación de bicicleta: 380 pesos.", EXCERPTS, [1]).ok is False


def test_multiline_quotation_of_a_price_list_passes():
    answer = "«Precios\n- Espresso: 35 pesos.\n- Afinación de bicicleta: 380 pesos.» [1]"
    assert verifier.verify(answer, EXCERPTS, [1]).ok


def test_data_markers_find_numbers_currency_and_written_numerals():
    markers = verifier.data_markers("380 pesos, 90 days, RFC-1234")
    assert "380" in markers
    assert "pesos" in markers
    assert "days" not in markers
    assert verifier.has_data("novecientos pesos")
    assert verifier.has_data("$380")
    assert verifier.has_data("⁹⁹⁹")
    assert verifier.has_data("1 200")
    assert verifier.has_data("2026-10-09")


def test_plain_prose_has_no_data():
    assert verifier.has_data("Está en los documentos del negocio.") is False
    assert verifier.has_data("Te paso el resumen.") is False


def test_short_units_alone_are_not_a_datum():
    assert verifier.has_data("Los días de entrega varían.") is False
    assert verifier.has_data("El total es de 90 días.") is True


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Cuesta ３８０ pesos.", "cuesta 380 pesos."),
        ("Cuesta 1\u202f200 pesos.", "cuesta 1200 pesos."),
        ("Cuesta  380   pesos.", "cuesta 380 pesos."),
    ],
)
def test_normalize(text, expected):
    assert verifier.normalize(text) == expected
