"""Permanent regression of the fourth review: the 62 data variants of the extractive matrix.

R4, appendix ``regressions.py``. It reproduces the 31 free-prose and manipulated-data cases of R1 M1,
R2 B-R2-1/B-R2-2/M-R2-1 and R3, each one bare and wrapped in guillemets: 62 variants and 124
transformations. A forged block must be rejected, a turn with no selection must deliver the fixed
refusal, and a selected line must render byte for byte with the mark and the seal.
"""

from __future__ import annotations

import json

import pytest

from hermes_cited import plugin, render, verifier

QUIET = (
    "streaming:\n  enabled: false\ndisplay:\n  streaming: false\n  interim_assistant_messages: false\n"
)

CASES = [
    ("currency", "€380", "$380"),
    ("sign", "-380 pesos", "380 pesos"),
    ("decimal", "1.200 mg", "1200 mg"),
    ("superscript", "⁹⁹⁹ pesos", "380 pesos"),
    ("fullwidth", "３８０", "380"),
    ("thousands", "1\u202f200", "1200"),
    ("plural", "1 día", "1 días"),
    ("date", "10/09/2026", "09/10/2026"),
    ("code", "xyz-123", "abc-123"),
    ("number_word", "novecientos", "trescientos"),
    ("unit", "5 mcg", "5 mg"),
    ("subject", "Espresso: 380 pesos.", "Espresso: 35 pesos. Afinación: 380 pesos."),
    ("citation", "Cuesta 380 pesos [1]", "Cuesta 380 pesos"),
    ("uppercase", "CUESTA 380 PESOS", "Cuesta 380 pesos"),
    ("free_one", "una reparación", "dos reparaciones"),
    ("free_zero", "Stock: cero.", "Stock: cinco."),
    ("free_half", "medio comprimido", "dos comprimidos"),
    ("free_unit", "La dosis se expresa en mcg.", "La dosis se expresa en mg."),
    ("free_code", "XYZ", "ABC"),
    ("free_date", "mañana", "hoy"),
    ("free_percent", "cien\u200bto por ciento", "Sin descuento"),
    ("free_symbol", "⅓", "Sin descuento"),
    ("free_infinity", "∞", "5"),
    ("leading_minus", "-380 pesos.", "380 pesos."),
    ("superscript_exponent", "10³ mg", "103 mg"),
    ("subscript_code", "H₂O", "H2O"),
    ("substring_quantity", "380 pesos.", "1380 pesos."),
    ("split_subject", "Espresso:\n«380 pesos.»", "Espresso: 35 pesos. Afinación: 380 pesos."),
    ("outside_quote_number", "«Afinación»: 380 pesos.", "Afinación: 380 pesos."),
    ("partial_quote", "Cuesta «380» pesos", "Cuesta 380 pesos"),
    ("bracket_datum", "Cantidad [1]", "Cantidad 5"),
]


class State:
    def get(self, key, default=None):
        return "cited" if key == "mode.profile" else default


@pytest.mark.parametrize("index,name,draft,source", [
    (index, name, draft, source) for index, (name, draft, source) in enumerate(CASES)
], ids=[name for name, _, _ in CASES])
@pytest.mark.parametrize("wrapped", [False, True], ids=["bare", "wrapped"])
def test_r4_matrix_one_variant(index, name, draft, source, wrapped, hermes_home):
    """R4 appendix: one data variant of the extractive matrix, bare and wrapped in guillemets."""
    (hermes_home / "config.yaml").write_text(QUIET, encoding="utf-8")
    state = State()
    text = "«" + draft + "»" if wrapped else draft
    forged = render.Line(1, 1, text, "sample.md", "H", pid="P1")
    rejected = not verifier.verify_display([forged], render.excerpt_lines(source)).ok
    assert rejected is True, name
    actual = []
    for selected in (False, True):
        turn_id = "{0}-{1}-{2}".format(index, wrapped, selected)
        plugin._pre_llm_call(state)(session_id="s", turn_id=turn_id, platform="cli")
        payload = {
            "cited_tool": "cited_search",
            "query": text,
            "text": text,
            "answer": text,
            "passages": [{"n": 1, "document": "sample.md", "heading": "H", "position": 2, "excerpt": source}],
        }
        plugin._post_tool_call()(tool_name="cited_search", result=json.dumps(payload),
                                 session_id="s", turn_id=turn_id)
        if selected:
            plugin._quote_handler(state)({"passage": "P1", "lines": [1]}, session_id="s", turn_id=turn_id)
        final = plugin._transform_llm_output(state)(response_text=text, session_id="s", turn_id=turn_id,
                                                    platform="cli")
        if selected:
            expected = verifier.sealed(render.render_answer(
                "es", [render.Line(1, 1, source, "sample.md", "H", pid="P1")]))
        else:
            expected = render.refusal_text("es")
        actual.append(final == expected)
    assert actual == [True, True], "{0}: {1}".format(name, actual)
