"""The by-construction verifier of cited mode (H4, H12, D5).

The verifier does not read prose. It asserts that every block the plugin is about to display is *identical*
to a full line of an excerpt of the same turn, and that the block carries the identifier of the passage it
came from, so the mark of the render, the selection of the model and the row of the log are the same
reference (H14). There is no Unicode normalisation, no substring comparison and no word list: all of those
were the holes of D2. In dot mode the model's text is delivered as it is: with D12 this version writes no
seal, so there is no mark to remove and no fixed note that replaces anything.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import messages, render
from .render import SEAL, Line  # noqa: F401  (SEAL and Line are re-exported for callers)


@dataclass(frozen=True)
class Verification:
    """The outcome of the by-construction check over the blocks of one turn."""

    text: str
    ok: bool
    blocks: tuple
    ungrounded: tuple
    has_grounding: bool
    unbound: tuple = ()


def verify_display(lines, turn_lines) -> Verification:
    """True only when every block is a full line of the turn and the turn had at least one line."""
    blocks = tuple(lines or ())
    known = {str(item) for item in (turn_lines or ())}
    ungrounded = tuple(block.text for block in blocks if block.text not in known)
    unbound = tuple(block.text for block in blocks if not str(getattr(block, "pid", "") or "").strip())
    ok = bool(blocks) and bool(known) and not ungrounded and not unbound
    return Verification(
        text="",
        ok=ok,
        blocks=blocks,
        ungrounded=ungrounded,
        has_grounding=bool(known),
        unbound=unbound,
    )


def refusal_text(language="es") -> str:
    """The fixed refusal of cited mode, in the configured language."""
    return render.refusal_text(language)


def sealed(body: str) -> str:
    """The plugin's seal, appended only to a body that has already been verified and persisted."""
    return "{0}\n\n{1}".format(str(body).rstrip(), SEAL)


def operational_refusal(code, language="es") -> str:
    """The fixed operational refusal of a turn that could not be composed or recorded (H10, D10).

    It carries an incident code and no seal, and interpolates no error detail: the diagnostic goes to the
    log and to ``stderr`` only.
    """
    return messages.operational_text(language, code)
