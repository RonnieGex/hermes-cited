"""``/cited`` and ``/dot``: the mode of the conversation, and where that mode is stored (H4).

The mode lives in the plugin's profile-scoped state. A turn resolves it as: the session entry,
then the profile entry, then ``CITED_DEFAULT_MODE``, then ``dot``. The session key is the agent's
session when the surface exposes one and the gateway's bound ``HERMES_SESSION_KEY``/``
HERMES_SESSION_ID`` when it does not, so the CLI (one conversation per process) and the gateway
(one conversation per session) are both covered.
"""

from __future__ import annotations

from .config import MODES, mode_default

PROFILE_KEY = "mode.profile"
SESSION_PREFIX = "mode.session."


def session_key(session_id: str) -> str:
    return "{0}{1}".format(SESSION_PREFIX, str(session_id or "").strip())


def current_session_key() -> str:
    """The session the gateway bound around this call, or an empty string on the CLI."""
    try:
        from gateway.session_context import get_session_env
    except Exception:
        return ""
    for name in ("HERMES_SESSION_KEY", "HERMES_SESSION_ID"):
        try:
            value = get_session_env(name, "") or ""
        except Exception:
            value = ""
        if str(value).strip():
            return str(value).strip()
    return ""


def _clean(mode) -> str:
    value = str(mode or "").strip().lower()
    return value if value in MODES else ""


def _candidates(session_id) -> list:
    values = []
    for candidate in (str(session_id or "").strip(), current_session_key()):
        if candidate and candidate not in values:
            values.append(candidate)
    return values


def resolve_mode(state, session_id=None, default_mode=None) -> str:
    """The mode of this turn: session, then profile, then the configured default, then dot."""
    for candidate in _candidates(session_id):
        value = _clean(state.get(session_key(candidate)))
        if value:
            return value
    value = _clean(state.get(PROFILE_KEY))
    if value:
        return value
    return _clean(default_mode) or mode_default() or "dot"


resolve_for_turn = resolve_mode


def set_mode(state, mode, session_id=None) -> str:
    """Store the mode for one session, or for the whole profile when there is no session."""
    value = _clean(mode) or "dot"
    key = session_key(session_id) if str(session_id or "").strip() else PROFILE_KEY
    state.set(key, value)
    return key


def mode_command(state, mode):
    """The handler of ``/cited`` or ``/dot``: change the mode of this conversation."""
    value = _clean(mode) or "dot"

    def handler(raw_args=""):
        session_id = current_session_key()
        set_mode(state, value, session_id=session_id)
        if value == "cited":
            return (
                "Cited mode is on. Every number, unit, price and code of the next answers must come "
                "from a passage Cited returned in the same turn; an answer that does not is replaced "
                "by a refusal that names what could not be verified, and a verified answer ends with "
                "\"Verified by Cited\" and its sources. /dot turns this off."
            )
        return (
            "Dot mode is on. Cited is still there when it helps, and no answer is sealed or replaced "
            "by the verifier. /cited turns cited mode back on."
        )

    return handler
