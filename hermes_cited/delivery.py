"""The delivery policy of cited mode, where Hermes can actually enforce it (D1, H9).

Hermes v0.21.6+387 delivers every text delta to the screen or to the messaging surface before
``transform_llm_output`` runs, and no plugin hook can retain those deltas. What the plugin *can* do
is read the effective streaming configuration of the run and refuse to promise a verified-only
delivery on a surface that is streaming: there it withholds the seal and says so. The surfaces whose
configuration the plugin can read are the CLI (``display.streaming``) and the gateway messaging
platforms (``streaming.enabled`` plus ``display.platforms.<platform>.streaming``). The desktop app
wires its own SSE stream and cannot be configured from here; that limitation is documented instead.
"""

from __future__ import annotations

import os
from pathlib import Path

MESSAGING_PLATFORMS = (
    "telegram",
    "slack",
    "discord",
    "whatsapp",
    "signal",
    "matrix",
    "teams",
    "msteams",
    "sms",
    "imessage",
    "mattermost",
    "rocketchat",
    "zulip",
    "line",
    "wechat",
    "messenger",
    "googlechat",
    "email",
)

WITHHELD_NOTE = (
    "Note on delivery: streaming is on for this platform, so a draft may have been visible before "
    "this answer was verified, and the verified seal is withheld here. Turn streaming off for cited "
    "mode (gateway: `streaming.enabled: false`, or `display.platforms.{0}.streaming: false`; CLI: "
    "`display.streaming: false`) to receive the seal."
)


def _scalar(value: str):
    text = str(value).strip().strip('"').strip("'")
    lowered = text.lower()
    if lowered in ("true", "yes", "on"):
        return True
    if lowered in ("false", "no", "off"):
        return False
    return text


def simple_yaml(text: str) -> dict:
    """A tiny reader for the small nested mapping Hermes writes in ``config.yaml``.

    It is only used when PyYAML is not importable (the plugin must not depend on it): the plugin
    venv of a plain test run has no ``yaml`` module, while the Hermes venv does.
    """
    root: dict = {}
    stack = [(-1, root)]
    for raw in str(text or "").splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        content = line.strip()
        if ":" not in content:
            continue
        key, _, value = content.partition(":")
        key = key.strip().strip('"').strip("'")
        if not key:
            continue
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        value = value.strip()
        if value:
            parent[key] = _scalar(value)
        else:
            node: dict = {}
            parent[key] = node
            stack.append((indent, node))
    return root


def read_config(home=None) -> dict:
    path = Path(home) / "config.yaml" if home else _default_home() / "config.yaml"
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        import yaml

        loaded = yaml.safe_load(text)
        return loaded if isinstance(loaded, dict) else {}
    except Exception:
        return simple_yaml(text)


def _default_home() -> Path:
    value = os.environ.get("HERMES_HOME", "").strip()
    return Path(value) if value else Path.home() / ".hermes"


def _mapping(value) -> dict:
    return value if isinstance(value, dict) else {}


def global_streaming(config: dict) -> bool:
    streaming = _mapping(config.get("streaming"))
    enabled = bool(streaming.get("enabled", False))
    transport = streaming.get("transport", streaming.get("mode"))
    return enabled and str(transport or "auto").strip().lower() != "off"


def cli_streaming(config: dict) -> bool:
    display = _mapping(config.get("display"))
    return bool(display.get("streaming", False))


def platform_override(config: dict, platform: str):
    display = _mapping(config.get("display"))
    platforms = _mapping(display.get("platforms"))
    entry = _mapping(platforms.get(str(platform or "").strip().lower()))
    return entry.get("streaming")


def is_messaging(platform: str) -> bool:
    return str(platform or "").strip().lower() in MESSAGING_PLATFORMS


def streaming_surface(platform: str) -> bool:
    """The surfaces whose effective streaming the plugin can read *and* enforce.

    Messaging is the product channel: there the plugin withholds the seal when streaming is on.
    The CLI and the desktop app are documented instead — the CLI streams by default and its
    ``--format stream-json`` consumer is told to show only the terminal ``result`` record, and the
    desktop app wires its own SSE stream that no configuration here can reach.
    """
    return is_messaging(platform)


def effective_streaming(platform: str, config: dict = None, home=None) -> bool:
    """The effective streaming of one surface, from the configuration Hermes itself reads."""
    name = str(platform or "").strip().lower()
    values = config if config is not None else read_config(home)
    if is_messaging(name):
        return global_streaming(values) and (platform_override(values, name) is None or bool(platform_override(values, name)))
    if name in ("cli", ""):
        return cli_streaming(values)
    return global_streaming(values)


def seal_allowed(platform: str, config: dict = None, home=None) -> bool:
    """False when streaming is on for a surface whose configuration the plugin can read."""
    if not streaming_surface(platform):
        return True
    return not effective_streaming(platform, config, home)


def withheld_note(platform: str) -> str:
    return WITHHELD_NOTE.format(str(platform or "this platform").strip() or "this platform")
