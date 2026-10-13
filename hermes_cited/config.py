"""Configuration of the Cited plugin, read from the active profile of the running Hermes.

Inside Hermes the blessed accessor ``agent.secret_scope`` is used: the mapping and the home of the active
profile are required at registration and at every handler call, a missing value takes its documented
default and never a process-environment fallback, and a failing accessor fails closed (D2). Only a run
outside Hermes, where the ``agent`` package is absent, reads the plain environment, so the client stays
testable without the host.

``CITED_BRIDGE_TOOLS`` is a closed switch: absent or empty selects ``full``, ``search`` selects the
search-only bridge, and any other value refuses registration before a callback is installed (H19). Full
mode keeps the ``POST <CITED_URL>/api/mcp`` contract and its ``CITED_MCP_TOKEN``; search mode reads
``CITED_SEARCH_TOKEN`` only and never requests the MCP token, not even to redact or check it (H20, H21).
"""

from __future__ import annotations

import collections.abc
import contextvars
import os
from dataclasses import dataclass
from typing import Callable, Mapping, Optional

DEFAULT_TIMEOUT_MS = 30000
MCP_PATH = "/api/mcp"
CHASSIS_PATH = "/api/chassis/mcp"
MODES = ("dot", "cited")
DEFAULT_MODE = "dot"
LANGUAGES = ("es", "en")
DEFAULT_LANGUAGE = "es"

BRIDGE_TOOLS_ENV = "CITED_BRIDGE_TOOLS"
BRIDGE_FULL = "full"
BRIDGE_SEARCH = "search"
BRIDGE_MODES = (BRIDGE_FULL, BRIDGE_SEARCH)
DEFAULT_BRIDGE_MODE = BRIDGE_FULL

MCP_TOKEN_NAME = "CITED_MCP_TOKEN"
SEARCH_TOKEN_NAME = "CITED_SEARCH_TOKEN"

MIN_TIMEOUT_MS = 1
MAX_TIMEOUT_MS = 120000
MIN_QUERY_LENGTH = 1
MAX_QUERY_LENGTH = 1000
MIN_SEARCH_LIMIT = 1
MAX_SEARCH_LIMIT = 8
DEFAULT_SEARCH_LIMIT = 5

#: The one sentence of a scope that cannot be read. It never carries a token, a URL or a profile name.
SCOPE_SENTENCE = (
    "Cited is not configured: this Hermes profile has no readable secret scope. Register the plugin "
    "again from the profile that owns this conversation."
)


class CitedError(Exception):
    """A Cited failure as a sentence the model can read; it never carries the token."""


class CitedConfigError(CitedError):
    """A configuration the plugin cannot work with, as a sentence the model can read."""


class CitedScopeError(CitedConfigError):
    """The active profile scope is missing, unreadable or no longer the registration's own."""


@dataclass(frozen=True)
class Settings:
    url: str
    token: str
    timeout_ms: int
    default_mode: str
    language: str = DEFAULT_LANGUAGE


@dataclass(frozen=True)
class SearchSettings:
    """The three values the search bridge needs, read fresh from one profile scope on every call."""

    url: str
    token: str
    timeout_ms: int
    home: str = ""


@dataclass(frozen=True)
class Registration:
    """What one registration captured: its mode and the canonical home identity of its profile."""

    mode: str
    home: str
    explicit: bool = False


@dataclass(frozen=True)
class ProfileScope:
    """The mapping and the home of one profile.

    ``values`` is kept as it arrived, never copied: a test can instrument the mapping and prove that the
    search path never asks for ``CITED_MCP_TOKEN`` (H20).
    """

    values: Mapping
    home: str
    getter: Optional[Callable] = None
    source: str = "explicit"

    def has(self, name) -> bool:
        return name in self.values

    def get(self, name, default=""):
        """The documented default when the key is absent; never a process-environment fallback."""
        try:
            if name not in self.values:
                return default
            reader = self.getter
            value = reader(name, default) if reader is not None else self.values.get(name, default)
            return default if value is None else str(value)
        except Exception:
            raise CitedScopeError(SCOPE_SENTENCE) from None


_SCOPE_STACK: contextvars.ContextVar = contextvars.ContextVar("hermes_cited_profile_scope", default=None)


def bridge_mode_of(value) -> str:
    """``full`` for absent or empty, ``search`` for search, and a refusal for anything else."""
    text = "" if value is None else str(value)
    if not text:
        return BRIDGE_FULL
    if text in BRIDGE_MODES:
        return text
    raise CitedConfigError(
        "Cited is not configured: CITED_BRIDGE_TOOLS accepts only 'full' or 'search'; the plugin "
        "registered nothing."
    )


def bind_scope(mapping, home, getter=None):
    """The test seam: bind one explicit profile scope and return the token that releases it."""
    scope = ProfileScope(
        values=mapping if mapping is not None else {},
        home=str(home or ""),
        getter=getter,
        source="explicit",
    )
    return _SCOPE_STACK.set(scope)


def unbind_scope(token) -> None:
    _SCOPE_STACK.reset(token)


def _environ_scope() -> ProfileScope:
    """The only fallback: execution outside Hermes, where the ``agent`` package is absent."""
    return ProfileScope(
        values=os.environ,
        home=os.environ.get("HERMES_HOME", "").strip(),
        getter=None,
        source="environ",
    )


def _agent_is_absent(error) -> bool:
    """True only when ``agent`` itself is missing, not when one of its own dependencies is (B01)."""
    name = str(getattr(error, "name", "") or "")
    return name == "agent"


def host_is_present() -> bool:
    """True when the ``agent`` package of Hermes is installed, even when importing it fails.

    A ``ModuleNotFoundError`` raised by a dependency *inside* the host (its ``name`` is not ``agent``)
    means the host is present and broken; that must fail closed and never fall back to the environment
    (D2, B01).
    """
    try:
        import agent  # noqa: F401
    except ModuleNotFoundError as error:
        return not _agent_is_absent(error)
    except Exception:
        return True
    return True


def canonical_home(value) -> str:
    """One canonical spelling of a home directory, so ``home/child/..`` is the same identity (m01)."""
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        resolved = os.path.realpath(text)
    except Exception:
        resolved = os.path.abspath(text)
    try:
        return os.path.normcase(os.path.normpath(resolved))
    except Exception:
        return resolved


def active_scope() -> ProfileScope:
    """The scope of the active profile, or :class:`CitedScopeError` when it cannot be read."""
    override = _SCOPE_STACK.get()
    if override is not None:
        return override
    try:
        import agent  # noqa: F401
    except ModuleNotFoundError as error:
        if _agent_is_absent(error):
            return _environ_scope()
        raise CitedScopeError(SCOPE_SENTENCE) from None
    except Exception:
        raise CitedScopeError(SCOPE_SENTENCE) from None
    try:
        from agent.secret_scope import current_secret_scope, current_secret_scope_home, get_secret
    except Exception:
        raise CitedScopeError(SCOPE_SENTENCE) from None
    try:
        values = current_secret_scope()
        home = current_secret_scope_home()
    except Exception:
        raise CitedScopeError(SCOPE_SENTENCE) from None
    if not isinstance(values, collections.abc.Mapping):
        raise CitedScopeError(SCOPE_SENTENCE)
    if home is None or not str(home).strip():
        raise CitedScopeError(SCOPE_SENTENCE)
    return ProfileScope(values=values, home=str(home), getter=get_secret, source="hermes")


def _check_registration(scope: ProfileScope, registration: Registration) -> None:
    """A call in another home or with a changed mode is refused until that profile registers again."""
    if not scope.home or not registration.home:
        raise CitedScopeError(SCOPE_SENTENCE)
    if canonical_home(scope.home) != canonical_home(registration.home):
        raise CitedScopeError(SCOPE_SENTENCE)
    if bridge_mode_of(scope.get(BRIDGE_TOOLS_ENV)) != registration.mode:
        raise CitedScopeError(SCOPE_SENTENCE)


def get_secret(name: str, default: str = "") -> str:
    """Read one secret the way Hermes wants it read, falling back to ``os.environ`` (legacy full path)."""
    try:
        from agent.secret_scope import get_secret as scoped_get_secret
    except Exception:
        return os.environ.get(name, default)
    try:
        value = scoped_get_secret(name, default)
    except Exception:
        return os.environ.get(name, default)
    return default if value is None else value


def endpoint_of(url: str) -> str:
    """Return the absolute ``/api/mcp`` endpoint of *url*, or raise the sentence that says why not."""
    value = (url or "").strip()
    if not value:
        raise CitedConfigError(
            "Cited is not configured: set CITED_URL to the address of the Cited installation, "
            "like https://cited.example.com."
        )
    from urllib.parse import urlsplit, urlunsplit

    try:
        parts = urlsplit(value)
    except ValueError:
        raise CitedConfigError("Cited is not configured: CITED_URL is not an absolute address.")
    if not parts.scheme or not parts.netloc:
        raise CitedConfigError("Cited is not configured: CITED_URL is not an absolute address.")
    if parts.scheme not in ("http", "https"):
        raise CitedConfigError("Cited is not configured: CITED_URL must be http or https.")
    path = parts.path.rstrip("/")
    if not path.endswith(MCP_PATH):
        path = path + MCP_PATH
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def chassis_endpoint_of(url) -> str:
    """The strict search-mode origin: explicit http/https, no userinfo, path, query or fragment."""
    value = (url or "").strip()
    if any(ord(char) <= 32 or ord(char) == 127 for char in value):
        raise CitedConfigError("Cited is not configured: CITED_URL must carry no control characters or spaces.")
    if not value:
        raise CitedConfigError(
            "Cited is not configured: set CITED_URL to the origin of the Cited installation, "
            "like https://cited.example.com."
        )
    from urllib.parse import urlsplit, urlunsplit

    try:
        parts = urlsplit(value)
        parts.port
    except ValueError:
        raise CitedConfigError("Cited is not configured: CITED_URL is not an absolute http or https origin.")
    if not parts.scheme or not parts.netloc or parts.scheme not in ("http", "https"):
        raise CitedConfigError("Cited is not configured: CITED_URL must be an absolute http or https origin.")
    if parts.username is not None or parts.password is not None:
        raise CitedConfigError("Cited is not configured: CITED_URL must carry no userinfo.")
    if parts.path:
        raise CitedConfigError(
            "Cited is not configured: CITED_URL must be an origin with no path, not even a trailing slash."
        )
    if "?" in value or "#" in value:
        raise CitedConfigError("Cited is not configured: CITED_URL must carry no query and no fragment.")
    return urlunsplit((parts.scheme, parts.netloc, CHASSIS_PATH, "", ""))


def token_of(token: str) -> str:
    value = (token or "").strip()
    if not value:
        raise CitedConfigError(
            "Cited is not configured: set CITED_MCP_TOKEN to the bearer token of that installation."
        )
    return value


def token_of_search(token) -> str:
    value = (token or "").strip()
    if not value:
        raise CitedConfigError(
            "Cited is not configured: set CITED_SEARCH_TOKEN to the search-only bearer of the "
            "chassis surface."
        )
    return value


def timeout_of(value) -> int:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT_MS
    return number if number > 0 else DEFAULT_TIMEOUT_MS


def search_timeout_of(value) -> int:
    """The search timeout: an integer from 1 through 120000, or a sentence that names the setting."""
    text = str(value).strip() if value is not None else ""
    if not text:
        return DEFAULT_TIMEOUT_MS
    if not text.isascii() or not text.isdigit():
        raise CitedConfigError(
            "Cited is not configured: CITED_TIMEOUT_MS must be an integer between 1 and 120000."
        )
    number = int(text)
    if not MIN_TIMEOUT_MS <= number <= MAX_TIMEOUT_MS:
        raise CitedConfigError(
            "Cited is not configured: CITED_TIMEOUT_MS must be an integer between 1 and 120000."
        )
    return number


def _env(env: Optional[Mapping[str, str]] = None) -> Mapping[str, str]:
    return os.environ if env is None else env


def mode_default_of(value) -> str:
    text = str(value or "").strip().lower()
    return text if text in MODES else DEFAULT_MODE


def mode_default(env: Optional[Mapping[str, str]] = None) -> str:
    return mode_default_of(_env(env).get("CITED_DEFAULT_MODE", ""))


def language_of(value) -> str:
    """The configured language of the cited-mode render, ``es`` when it is missing or unknown."""
    text = str(value or "").strip().lower().replace("_", "-")
    base = text.split("-")[0]
    return base if base in LANGUAGES else DEFAULT_LANGUAGE


def settings_from_scope(scope: ProfileScope) -> Settings:
    return Settings(
        url=scope.get("CITED_URL").strip(),
        token=scope.get(MCP_TOKEN_NAME).strip(),
        timeout_ms=timeout_of(scope.get("CITED_TIMEOUT_MS")),
        default_mode=mode_default_of(scope.get("CITED_DEFAULT_MODE")),
        language=language_of(scope.get("CITED_LANGUAGE")),
    )


def settings_for(registration: Registration) -> Settings:
    """The full-mode settings of one registration, read fresh from its own profile scope.

    A registration without a home is the legacy full surface outside Hermes: it reads the process
    environment exactly as H0-H18 always did. Inside Hermes a registration without a home can only be a
    stale one, so it fails closed instead of reaching the environment (D2, B01).
    """
    if not registration.home:
        if host_is_present():
            raise CitedScopeError(SCOPE_SENTENCE)
        return settings_from_env()
    scope = active_scope()
    _check_registration(scope, registration)
    return settings_from_scope(scope)


def search_settings_for(registration: Registration) -> SearchSettings:
    """The search settings of one registration; the MCP token is never named on this path."""
    scope = active_scope()
    _check_registration(scope, registration)
    url = scope.get("CITED_URL")
    chassis_endpoint_of(url)
    token = token_of_search(scope.get(SEARCH_TOKEN_NAME))
    timeout = search_timeout_of(scope.get("CITED_TIMEOUT_MS"))
    return SearchSettings(url=str(url).strip(), token=token, timeout_ms=timeout, home=str(scope.home))


def settings_from_env(env: Optional[Mapping[str, str]] = None) -> Settings:
    source = _env(env)
    return Settings(
        url=str(source.get("CITED_URL", "") or "").strip(),
        token=str(source.get(MCP_TOKEN_NAME, "") or "").strip(),
        timeout_ms=timeout_of(source.get("CITED_TIMEOUT_MS")),
        default_mode=mode_default(env),
        language=language_of(source.get("CITED_LANGUAGE")),
    )
