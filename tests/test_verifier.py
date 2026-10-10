"""The deterministic verifier and the cited-mode refusal and seal (H4)."""

from __future__ import annotations

from hermes_cited import verifier

GROUNDING = [
    'Cited found 1 passage(s) for "precio". Cite each one by its number, like [1].\n\n'
    "1. cafe-la-horquilla.md - Precios\n"
    "Precios\n- Espresso: 35 pesos.\n- Afinacion de bicicleta: 380 pesos.",
    "Afinacion de bicicleta: 380 pesos.",
    "Every repair carries a guarantee of 90 days from the day of delivery.",
]


def test_a_grounded_number_passes():
    result = verifier.verify("La afinacion cuesta 380 pesos [1].", GROUNDING)
    assert result.ok is True
    assert result.ungrounded == ()


def test_a_grounded_answer_is_sealed_with_its_sources():
    result = verifier.verify("La afinacion cuesta 380 pesos [1].", GROUNDING)
    assert result.ok
    sealed = verifier.seal(result, ["cafe-la-horquilla.md - Precios"])
    assert sealed.startswith("La afinacion cuesta 380 pesos [1].")
    assert "Verified by Cited" in sealed
    assert "cafe-la-horquilla.md - Precios" in sealed


def test_an_invented_number_is_refused_and_named():
    result = verifier.verify("La afinacion cuesta 450 pesos [1].", GROUNDING)
    assert result.ok is False
    assert "450" in result.ungrounded
    refusal = verifier.refusal(result)
    assert "450" in refusal
    assert "Verified by Cited" not in refusal


def test_a_number_only_in_the_question_is_not_grounded():
    result = verifier.verify("Son 2 afinaciones y el total es 999.", GROUNDING)
    assert result.ok is False
    assert "999" in result.ungrounded


def test_an_ungrounded_unit_is_refused():
    result = verifier.verify("La afinacion cuesta 380 euros [1].", GROUNDING)
    assert result.ok is False
    assert any("euro" in claim.lower() for claim in result.ungrounded)


def test_accents_case_and_thousands_separators_do_not_matter():
    assert verifier.verify("La afinacion cuesta 380 PESOS.", GROUNDING).ok
    assert verifier.verify("La afinacion cuesta 380 pesos.", GROUNDING).ok
    assert verifier.verify("El total es 1,200 pesos.", ["El total es 1200 pesos."]).ok


def test_a_decimal_is_compared_as_a_number():
    assert verifier.verify("Cuesta 380.50 pesos.", ["Cuesta 380.50 pesos."]).ok
    assert verifier.verify("Cuesta 380.75 pesos.", ["Cuesta 380.50 pesos."]).ok is False


def test_english_units_of_time_are_checked():
    assert verifier.verify("The guarantee is 90 days.", GROUNDING).ok
    assert verifier.verify("The guarantee is 30 days.", GROUNDING).ok is False


def test_a_turn_without_any_cited_result_cannot_pass():
    result = verifier.verify("El cafe abre de martes a domingo.", [])
    assert result.ok is False
    assert result.has_grounding is False
    refusal = verifier.refusal(result)
    assert "Cited" in refusal


def test_an_answer_without_claims_passes_when_cited_answered():
    result = verifier.verify("No esta en los documentos.", GROUNDING)
    assert result.ok is True


def test_a_code_is_checked():
    assert verifier.verify("Factura con RFC-1234.", ["Pide el RFC-1234 en la compra."]).ok
    assert verifier.verify("Factura con RFC-9999.", ["Pide el RFC-1234 en la compra."]).ok is False


def test_extract_claims_finds_numbers_units_and_codes():
    claims = verifier.extract_claims("380 pesos, 90 days, RFC-1234")
    assert "380" in claims
    assert "90" in claims
    assert "pesos" in claims
    assert "days" in claims
    assert "RFC-1234" in claims
