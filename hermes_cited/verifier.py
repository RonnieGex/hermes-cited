"""The by-construction verifier of cited mode (H4, H12, D5).

The verifier no longer reads prose. It asserts that every block the plugin is about to display is
*identical* to a full line of an excerpt of the same turn. There is no Unicode normalisation, no
substring comparison and no word list: all of those were the holes of D2. In dot mode the model's text
is delivered as it is, minus the reserved seal, which only the plugin may write.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import render
from .render import SEAL, Line


@dataclass(frozen=True)
class Verification:
    """The outcome of the by-construction check over the blocks of one turn."""

    text: str
    ok: bool
    blocks: tuple
    ungrounded: tuple
    has_grounding: bool


def verify_display(lines, turn_lines) -> Verification:
    """True only when every block is a full line of the turn and the turn had at least one line."""
    blocks = tuple(lines or ())
    known = {str(item) for item in (turn_lines or ())}
    ungrounded = tuple(block.text for block in blocks if block.text not in known)
    ok = bool(blocks) and bool(known) and not ungrounded
    return Verification(
        text="",
        ok=ok,
        blocks=blocks,
        ungrounded=ungrounded,
        has_grounding=bool(known),
    )


def refusal_text(language="es") -> str:
    """The fixed refusal of cited mode, in the configured language."""
    return render.refusal_text(language)


def sealed(body: str) -> str:
    """The plugin's seal, appended only to a body that has already been verified and persisted."""
    return "{0}\n\n{1}".format(str(body).rstrip(), SEAL)


def operational_refusal(detail: str) -> str:
    """The refusal of a turn whose answer could not be recorded, so it carries no seal (H10)."""
    return (
        "In cited mode I cannot deliver this answer as verified: the audit log could not be written "
        "({0}), so this answer was not recorded. Fix the log and ask again, or switch to dot mode "
        "with /dot.".format(str(detail or "unknown error"))
    )


def strip_seal(text: str) -> str:
    """The model's text without the reserved seal: only the plugin may write it (M-R2-2)."""
    value = str(text or "")
    if SEAL not in value:
        return value
    lines = [line for line in value.split("\n") if line.strip() != SEAL]
    while lines and not lines[-1].strip():
        lines.pop()
    while lines and not lines[0].strip():
        lines.pop(0)
    return "\n".join(lines)
