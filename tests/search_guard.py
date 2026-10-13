"""Test isolation guard of the search-only bridge (task 1.1 of search-only-bridge).

Every run of this change uses a temporary ``HERMES_HOME``; the personal installation under
``%LOCALAPPDATA%\\hermes`` and the ``hermes-agent`` checkout are read-only, and the ports 3240 and 3241
belong to the personal services and are never touched. This module holds the predicates that enforce
that and nothing else:

* :func:`guard_target` / :func:`guard_url` / :func:`guard_socket_address` reject the forbidden ports in
  every spelling, including the ``localhost`` aliases and their IPv6 equivalents.
* :func:`guard_path` rejects the personal installation, a symlink or junction that escapes the
  registered temporary workspace, and any path outside the workspaces registered for the run.
* :func:`require_names` fails on a missing override before any file, process or network effect.

The autouse fixture of ``tests/conftest.py`` installs :func:`install_socket_guard`, so a test that tries
to open a socket to 3240/3241 fails instead of reaching a personal service.
"""

from __future__ import annotations

import ipaddress
import os
import socket
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

FORBIDDEN_PORTS = frozenset({3240, 3241})

_WORKSPACES = []


class GuardError(AssertionError):
    """A test tried to reach the personal installation, a forbidden port or a foreign path."""


def personal_home() -> Path:
    """The personal Hermes installation, which every run of this change treats as read-only."""
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return (Path(base) / "hermes").resolve(strict=False)
    return (Path.home() / "AppData" / "Local" / "hermes").resolve(strict=False)


def canonical_host(host) -> str:
    """One spelling for every alias of the local machine, IPv6 forms included.

    ``localhost``, ``127.0.0.1``, ``127.0.0.2``, ``0.0.0.0``, ``::1``, ``::ffff:127.0.0.1`` and a
    bracketed ``[::1]`` all answer ``loopback``; any other host answers itself, lowercased.
    """
    text = str(host or "").strip().lower()
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    text = text.rstrip(".")
    if text == "localhost" or text.endswith(".localhost"):
        return "loopback"
    try:
        address = ipaddress.ip_address(text)
    except ValueError:
        return text
    if address.is_loopback or address.is_unspecified:
        return "loopback"
    mapped = getattr(address, "ipv4_mapped", None)
    if mapped is not None and (mapped.is_loopback or mapped.is_unspecified):
        return "loopback"
    return str(address)


def guard_port(port) -> int:
    """The port as an integer, or :class:`GuardError` when it is a personal port or not a port."""
    try:
        number = int(port)
    except (TypeError, ValueError):
        raise GuardError("the target carries no usable port: {0!r}".format(port))
    if number in FORBIDDEN_PORTS:
        raise GuardError(
            "the target port {0} is a personal service of this machine (3240/3241) and is never used".format(
                number
            )
        )
    if not 1 <= number <= 65535:
        raise GuardError("the target port {0} is outside 1..65535".format(number))
    return number


def guard_target(host, port) -> None:
    """Reject one host/port pair when it is a forbidden personal destination."""
    number = guard_port(port)
    if canonical_host(host) == "loopback" and number in FORBIDDEN_PORTS:
        raise GuardError("the loopback alias {0!r} resolves to a personal port".format(host))


def guard_url(url) -> str:
    """Reject one absolute URL whose effective port is forbidden; return the canonical host."""
    text = str(url or "").strip()
    if not text:
        raise GuardError("the guard needs an absolute URL")
    parts = urlsplit(text)
    host = parts.hostname or ""
    if not host:
        raise GuardError("the URL {0!r} carries no host".format(text))
    try:
        port = parts.port
    except ValueError:
        raise GuardError("the URL {0!r} carries an invalid port".format(text))
    if port is None:
        port = 443 if parts.scheme == "https" else 80
    guard_target(host, port)
    return canonical_host(host)


def guard_socket_address(address) -> None:
    """Reject the destination of one ``socket.connect`` call, in its socket tuple form.

    An IPv6 address arrives as ``(host, port, flowinfo, scope_id)``; a plain string arrives as
    ``host:port``.
    """
    if isinstance(address, (tuple, list)):
        if len(address) < 2:
            raise GuardError("the socket address {0!r} carries no port".format(address))
        guard_target(address[0], address[1])
        return
    text = str(address or "")
    host, _, port = text.rpartition(":")
    if not host or not port:
        raise GuardError("the socket address {0!r} carries no port".format(address))
    guard_target(host.strip("[]"), port)


def register_workspace(root) -> Path:
    """Register a directory that this run may write under."""
    resolved = Path(root).expanduser().resolve(strict=False)
    if resolved not in _WORKSPACES:
        _WORKSPACES.append(resolved)
    return resolved


def workspaces() -> list:
    return list(_WORKSPACES)


def _is_link(path: Path) -> bool:
    """True for a symlink or a Windows junction/reparse point, without following it."""
    try:
        info = os.lstat(path)
    except OSError:
        return False
    if os.path.islink(path):
        return True
    return bool(getattr(info, "st_reparse_tag", 0))


def guard_path(path, kind="path") -> Path:
    """Reject a path that leaves its registered workspace or hides behind a link.

    The personal installation is rejected first, so a workspace registered by mistake can never make it
    reachable. Every component below the workspace root is checked, so a junction cannot smuggle a path
    out of the temporary tree.
    """
    requested = Path(path).expanduser()
    resolved = requested.resolve(strict=False)
    home = personal_home()
    if resolved == home or home in resolved.parents:
        raise GuardError("the {0} {1} is inside the read-only personal installation".format(kind, resolved))
    root = next((item for item in _WORKSPACES if resolved == item or item in resolved.parents), None)
    if root is None:
        raise GuardError(
            "the {0} {1} is outside every registered temporary workspace: {2}".format(
                kind, resolved, ", ".join(str(item) for item in _WORKSPACES) or "none"
            )
        )
    current = root
    for part in resolved.relative_to(root).parts:
        current = current / part
        if _is_link(current):
            raise GuardError("the {0} {1} hides behind a link or junction".format(kind, current))
    return resolved


def require_names(env, names) -> None:
    """Fail before any effect when one of the documented overrides is missing."""
    source = env if env is not None else {}
    missing = [str(name) for name in names if not str(source.get(name) or "").strip()]
    if missing:
        raise GuardError("missing override(s) before any effect: {0}".format(", ".join(missing)))


def guard_environment(env) -> None:
    """Validate the overrides of a run: a safe temporary home and no forbidden destination."""
    source = env if env is not None else {}
    home = str(source.get("HERMES_HOME") or "").strip()
    if home:
        guard_path(home, kind="HERMES_HOME")
    url = str(source.get("CITED_URL") or "").strip()
    if url:
        guard_url(url)


def install_socket_guard(monkeypatch) -> None:
    """Patch every outbound connection so a forbidden port cannot be reached by any test."""
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def connect(self, address):
        guard_socket_address(address)
        return original_connect(self, address)

    def connect_ex(self, address):
        guard_socket_address(address)
        return original_connect_ex(self, address)

    monkeypatch.setattr(socket.socket, "connect", connect, raising=True)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex, raising=True)


register_workspace(tempfile.gettempdir())
