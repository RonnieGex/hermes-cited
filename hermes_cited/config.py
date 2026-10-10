"""Configuration of the Cited plugin, read from the environment of the Hermes process.

Hermes loads ``$HERMES_HOME/.env`` into ``os.environ`` before a plugin runs, so this module
reads the same names the operator wrote there. The blessed accessor ``agent.secret_scope``
is used when the plugin runs inside Hermes and the plain environment otherwise, so the
client is testable outside Hermes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping, Optional

DEFAULT_TIMEOUT_MS = 30000
MCP_PATH = "/api/mcp"
MODES = ("dot", "cited")
DEFAULT_MODE = "dot"
LANGUAGES = ("es", "en")
DEFAULT_LANGUAGE = "es"


class CitedError(Exception):
    """A Cited failure as a sentence the model can read; it never carries the token."""


class CitedConfigError(CitedError):
    """A configuration the plugin cannot work with, as a sentence the model can read."""


@dataclass(frozen=True)
class Settings:
    url: str
    token: str
    timeout_ms: int
    default_mode: str
    language: str = DEFAULT_LANGUAGE


def get_secret(name: str, default: str = "") -> str:
    """Read one secret the way Hermes wants it read, falling back to ``os.environ``."""
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


def token_of(token: str) -> str:
    value = (token or "").strip()
    if not value:
        raise CitedConfigError(
            "Cited is not configured: set CITED_MCP_TOKEN to the bearer token of that installation."
        )
    return value


def timeout_of(value) -> int:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT_MS
    return number if number > 0 else DEFAULT_TIMEOUT_MS


def _env(env: Optional[Mapping[str, str]] = None) -> Mapping[str, str]:
    return os.environ if env is None else env


def mode_default(env: Optional[Mapping[str, str]] = None) -> str:
    value = str(_env(env).get("CITED_DEFAULT_MODE", "") or "").strip().lower()
    return value if value in MODES else DEFAULT_MODE


def language_of(value) -> str:
    """The configured language of the cited-mode render, ``es`` when it is missing or unknown."""
    text = str(value or "").strip().lower().replace("_", "-")
    base = text.split("-")[0]
    return base if base in LANGUAGES else DEFAULT_LANGUAGE


def settings_from_env(env: Optional[Mapping[str, str]] = None) -> Settings:
    source = _env(env)
    return Settings(
        url=str(source.get("CITED_URL", "") or "").strip(),
        token=str(source.get("CITED_MCP_TOKEN", "") or "").strip(),
        timeout_ms=timeout_of(source.get("CITED_TIMEOUT_MS")),
        default_mode=mode_default(env),
        language=language_of(source.get("CITED_LANGUAGE")),
    )
