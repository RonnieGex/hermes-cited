"""The delivery policy of cited mode, resolved the way Hermes itself resolves it (D7, H9).

Hermes v0.21.6+387 delivers every text delta to the screen or to the messaging surface before
``transform_llm_output`` runs, and no plugin hook can retain those deltas. What the plugin *can* do is
read the effective streaming configuration of the run with the host's own resolver —
``gateway.config.StreamingConfig.from_dict`` plus ``enabled_for``, which understand the ``mode``
transport alias, the YAML booleans and the per-platform override — and refuse to promise a
verified-only delivery where streaming is on. Only when that import is unavailable does the plugin use
the versioned compatibility copy below, pinned to the host of the release.

The seal is granted when the plugin can positively read that streaming is off. The CLI without
streaming is the only explicit exception; the desktop app withholds the seal with the D1 warning; a
messaging platform, and any platform the plugin does not know, follows the host's effective
configuration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:  # the real resolver of the host, when the plugin runs inside Hermes
    from gateway.config import StreamingConfig as HOST_STREAMING

    HOST_STREAMING_VERSION = "dce1e9b37581dd62e480a9064dc04a709c2940d3"
except Exception:  # the plugin venv of a plain test run has no host on the path
    HOST_STREAMING = None
    HOST_STREAMING_VERSION = ""

#: The surfaces of the host that are not a conversational chat surface. ``api_server`` keeps its
#: documented SSE exception; a webhook is inbound only.
NON_MESSAGING_PLATFORMS = ("local", "api_server", "webhook", "msgraph_webhook")

#: The messaging platforms of the release plus the ones round 1 listed, so an installation with an
#: older host still withholds on the platform it names.
MESSAGING_PLATFORMS = (
    "telegram",
    "slack",
    "discord",
    "whatsapp",
    "whatsapp_cloud",
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
    "weixin",
    "wecom",
    "wecom_callback",
    "feishu",
    "dingtalk",
    "qqbot",
    "yuanbao",
    "bluebubbles",
    "messenger",
    "googlechat",
    "email",
    "relay",
)

WITHHELD_NOTE = (
    "Note on delivery: streaming is on for this platform, so a draft may have been visible before "
    "this answer was verified, and the verified seal is withheld here. Turn streaming off for cited "
    "mode (gateway: `streaming.enabled: false`, or `display.platforms.{0}.streaming: false`; CLI: "
    "`display.streaming: false`) to receive the seal."
)

DESKTOP_NOTE = (
    "Note on delivery: the desktop app wires its own SSE stream, which no configuration here reaches, "
    "so a draft may be visible while the answer is written and the verified seal is withheld here. The "
    "text above is still copied from the documents of this turn."
)


def _coerce_bool(value, default: bool = True) -> bool:
    """The host's coercion of a bool-ish configuration value, including YAML strings."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        token = value.strip().lower()
        if token in ("true", "yes", "on", "1"):
            return True
        if token in ("false", "no", "off", "0"):
            return False
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def _normalize_transport_token(value) -> str:
    """The host's canonical transport token: a YAML ``off`` (``False``) really is ``off``."""
    if value is None:
        return "auto"
    if isinstance(value, bool):
        return "auto" if value else "off"
    return str(value).strip().lower() or "auto"


@dataclass
class CompatStreamingConfig:
    """A versioned copy of ``gateway.config.StreamingConfig`` for the release of this plugin.

    Pinned to ``gateway/config.py:486-541`` of ``dce1e9b``: ``mode`` is a transport alias that also
    implies ``enabled``, an explicit ``enabled`` wins, a bare ``transport`` does not imply enabled, and
    a per-platform value can only narrow the global switch.
    """

    enabled: bool = False
    transport: str = "auto"

    @property
    def globally_enabled(self) -> bool:
        return bool(self.enabled) and self.transport != "off"

    def enabled_for(self, platform_override) -> bool:
        return self.globally_enabled and (platform_override is None or bool(platform_override))

    @classmethod
    def from_dict(cls, data) -> "CompatStreamingConfig":
        if not isinstance(data, dict) or not data:
            return cls()
        raw_transport = data.get("transport")
        raw_mode = data.get("mode")
        if "enabled" in data:
            enabled = _coerce_bool(data.get("enabled"), False)
        else:
            enabled = raw_mode is not None and _normalize_transport_token(raw_mode) != "off"
        return cls(
            enabled=enabled,
            transport=_normalize_transport_token(raw_transport if raw_transport is not None else raw_mode),
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


def streaming_config(values: dict):
    """The host's ``StreamingConfig`` when it is importable, the pinned copy otherwise."""
    raw = _mapping(_mapping(values).get("streaming"))
    if HOST_STREAMING is not None:
        try:
            return HOST_STREAMING.from_dict(raw)
        except Exception:
            pass
    return CompatStreamingConfig.from_dict(raw)


def global_streaming(config: dict) -> bool:
    return bool(streaming_config(config).globally_enabled)


def cli_streaming(config: dict) -> bool:
    display = _mapping(config.get("display"))
    return bool(display.get("streaming", False))


def platform_override(config: dict, platform: str):
    display = _mapping(config.get("display"))
    platforms = _mapping(display.get("platforms"))
    entry = _mapping(platforms.get(str(platform or "").strip().lower()))
    return entry.get("streaming")


def is_messaging(platform: str) -> bool:
    """A conversational chat surface. An unknown platform is messaging: no seal by default (D7)."""
    name = str(platform or "").strip().lower()
    if not name or name in ("cli", "desktop"):
        return False
    if name in NON_MESSAGING_PLATFORMS:
        return False
    return True


def streaming_surface(platform: str) -> bool:
    """The surfaces whose effective streaming the plugin withholds the seal on."""
    return is_messaging(platform)


def effective_streaming(platform: str, config: dict = None, home=None) -> bool:
    """The effective streaming of one surface, from the resolution Hermes itself uses."""
    name = str(platform or "").strip().lower()
    values = config if config is not None else read_config(home)
    if name in ("cli", ""):
        return cli_streaming(values)
    return streaming_config(values).enabled_for(platform_override(values, name))


def seal_allowed(platform: str, config: dict = None, home=None) -> bool:
    """False when streaming is on for a surface whose configuration the plugin can read."""
    name = str(platform or "").strip().lower()
    values = config if config is not None else read_config(home)
    if name in ("cli", ""):
        return not cli_streaming(values)
    if name == "desktop":
        return False
    if not is_messaging(name):
        return True
    return not effective_streaming(name, values)


def withheld_note(platform: str) -> str:
    name = str(platform or "").strip().lower()
    if name == "desktop":
        return DESKTOP_NOTE
    return WITHHELD_NOTE.format(name or "this platform")
