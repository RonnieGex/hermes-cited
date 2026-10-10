"""The delivery policy of cited mode: a snapshot of the surfaces that could have been seen (H9, D13).

Hermes v0.21.6+387 delivers every text delta to the screen or to the messaging surface before
``transform_llm_output`` runs, and no plugin hook can retain those deltas. Round 3 read the effective
streaming configuration, but it read it *at the end* of the turn and it left three surfaces out: the
``api_server`` route (the SSE stream of the desktop app), streaming TTS and the interim assistant
commentary. Round 4 (D13) fixes both halves:

- the plugin takes a **snapshot at the start of the cited turn** and freezes it in the turn object, so a
  configuration change during the turn cannot change the decision taken for it (M-R3-4);
- the snapshot covers every surface of the host that delivers text or voice: ``streaming`` with the
  platform override, ``display.streaming`` for the CLI, ``interim_assistant_messages`` (global and per
  platform), ``tts.auto_tts``, ``api_server`` and ``desktop``.

The seal is granted only when the snapshot affirmatively shows that nothing else could have been visible.
When the configuration cannot be read, or the platform is unknown, the seal is withheld: the plugin never
promises a verified-only delivery it cannot prove. The promise of H12 is about the **final message**; the
temporary deltas of the surfaces this module withholds on are the limit that ``docs/upstream-proposal.md``
asks Hermes to close with a synchronous retention contract.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:  # the real resolver of the host, when the plugin runs inside Hermes
    from gateway.config import StreamingConfig as HOST_STREAMING

    HOST_STREAMING_VERSION = "dce1e9b37581dd62e480a9064dc04a709c2940d3"
except Exception:  # the plugin venv of a plain test run has no host on the path
    HOST_STREAMING = None
    HOST_STREAMING_VERSION = ""

#: The platforms whose delivery the host streams through its own route rather than through the plugin's
#: configuration. ``api_server`` is the SSE route of the desktop app (M-R3-4): it always withholds.
SSE_PLATFORMS = ("api_server", "desktop")

#: A webhook is inbound only: it never delivers a draft to a user.
NON_MESSAGING_PLATFORMS = ("local", "webhook", "msgraph_webhook")

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

#: The platform defaults of ``gateway/display_config.py`` of the pinned host, for the one key this module
#: resolves. ``True`` is the global default; the low tiers opt out.
INTERIM_DEFAULTS = {
    "signal": False,
    "whatsapp_cloud": False,
    "photon": False,
    "bluebubbles": False,
    "weixin": False,
    "wecom": False,
    "wecom_callback": False,
    "dingtalk": False,
    "qqbot": False,
}
INTERIM_GLOBAL_DEFAULT = True

WITHHELD_NOTE = (
    "Note on delivery: {reason} The verified seal is withheld here because something else may have been "
    "visible before this answer was verified. The text above is still copied from the documents of this "
    "turn."
)

#: The desktop app wires its own SSE stream, which no configuration reaches (D1). Kept as a constant for
#: the callers and the fixtures of round 3; the note of round 4 is ``withheld_note(snapshot)``.
DESKTOP_NOTE = (
    "Note on delivery: the desktop app wires its own SSE stream, which no configuration here reaches, "
    "so a draft may be visible while the answer is written and the verified seal is withheld here. The "
    "text above is still copied from the documents of this turn."
)

REASONS = {
    "sse": (
        "the desktop app streams this surface through its own SSE route, which no plugin can retain."
    ),
    "streaming": (
        "streaming is on for this platform, so a draft may have been visible before this answer was "
        "verified. Turn streaming off (gateway: `streaming.enabled: false`, or "
        "`display.platforms.{platform}.streaming: false`; CLI: `display.streaming: false`)."
    ),
    "commentary": (
        "interim assistant messages are on for this platform, so commentary may have been visible before "
        "this answer was verified. Turn them off with "
        "`display.platforms.{platform}.interim_assistant_messages: false` (or "
        "`display.interim_assistant_messages: false`)."
    ),
    "tts": "streaming text to speech is on (`tts.auto_tts`), so the answer may have been spoken before it was verified.",
    "unknown": "this platform is not one the plugin can resolve, so it cannot prove that nothing else was visible.",
    "unreadable": "the delivery configuration could not be read, so the plugin cannot prove that nothing else was visible.",
}


@dataclass(frozen=True)
class Snapshot:
    """The effective delivery configuration of one turn, frozen at its start (H9)."""

    platform: str = ""
    readable: bool = False
    streaming: bool = False
    commentary: bool = False
    tts: bool = False
    sse: bool = False
    known_platform: bool = False
    reasons: tuple = field(default_factory=tuple)
    seal: bool = False

    def as_dict(self) -> dict:
        return {
            "platform": self.platform,
            "readable": self.readable,
            "streaming": self.streaming,
            "commentary": self.commentary,
            "tts": self.tts,
            "sse": self.sse,
            "known_platform": self.known_platform,
            "reasons": list(self.reasons),
            "seal": self.seal,
            "host_streaming_version": HOST_STREAMING_VERSION,
        }


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

    Pinned to ``gateway/config.py:487-541`` of ``dce1e9b``: ``mode`` is a transport alias that also
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


def commentary_enabled(config: dict, platform: str) -> bool:
    """The host's resolution of ``interim_assistant_messages`` for one platform.

    Order of ``gateway/display_config.py``: ``display.platforms.<p>.interim_assistant_messages`` →
    ``display.interim_assistant_messages`` → the platform default → the global default.
    """
    name = str(platform or "").strip().lower()
    display = _mapping(config.get("display"))
    per_platform = _mapping(_mapping(display.get("platforms")).get(name))
    if "interim_assistant_messages" in per_platform:
        return _coerce_bool(per_platform.get("interim_assistant_messages"), INTERIM_GLOBAL_DEFAULT)
    if "interim_assistant_messages" in display:
        return _coerce_bool(display.get("interim_assistant_messages"), INTERIM_GLOBAL_DEFAULT)
    return bool(INTERIM_DEFAULTS.get(name, INTERIM_GLOBAL_DEFAULT))


def tts_streaming_enabled(config: dict) -> bool:
    """True when the host may speak the answer while it is written (``tts.auto_tts``)."""
    tts = _mapping(config.get("tts"))
    if "auto_tts" not in tts:
        return False
    return _coerce_bool(tts.get("auto_tts"), False)


def is_messaging(platform: str) -> bool:
    """A conversational chat surface. An unknown platform is messaging: no seal by default (D7)."""
    name = str(platform or "").strip().lower()
    if not name or name in ("cli",) or name in SSE_PLATFORMS:
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


def snapshot(platform: str, home=None, config: dict = None) -> Snapshot:
    """The frozen delivery snapshot of one turn, taken at its start (H9, D13).

    It never raises: an unreadable or unparseable configuration produces a snapshot that withholds.
    """
    name = str(platform or "").strip().lower()
    try:
        values = config if config is not None else read_config(home)
        if not isinstance(values, dict):
            raise ValueError("the configuration is not a mapping")
    except Exception:
        return Snapshot(
            platform=name,
            readable=False,
            sse=name in SSE_PLATFORMS,
            known_platform=name in MESSAGING_PLATFORMS or name in ("cli",) or name in SSE_PLATFORMS,
            reasons=("unreadable",),
            seal=False,
        )

    known = name in MESSAGING_PLATFORMS or name in ("cli",) or name in SSE_PLATFORMS or name in NON_MESSAGING_PLATFORMS or not name
    sse = name in SSE_PLATFORMS
    reasons = []
    if sse:
        reasons.append("sse")
    if not known:
        reasons.append("unknown")
    if name not in SSE_PLATFORMS:
        if name in ("cli", ""):
            if cli_streaming(values):
                reasons.append("streaming")
        elif is_messaging(name) and effective_streaming(name, values):
            reasons.append("streaming")
        if name in ("cli", "") or is_messaging(name):
            if commentary_enabled(values, name):
                reasons.append("commentary")
    if tts_streaming_enabled(values):
        reasons.append("tts")
    streaming = "streaming" in reasons
    commentary = "commentary" in reasons
    tts = "tts" in reasons
    return Snapshot(
        platform=name,
        readable=True,
        streaming=streaming,
        commentary=commentary,
        tts=tts,
        sse=sse,
        known_platform=known,
        reasons=tuple(reasons),
        seal=not reasons,
    )


def seal_allowed(platform: str, config: dict = None, home=None, snap: Snapshot = None) -> bool:
    """False unless the snapshot shows that nothing else can have been visible (H9)."""
    if snap is not None:
        return bool(snap.seal) and str(snap.platform) == str(platform or "").strip().lower()
    return bool(snapshot(platform, home=home, config=config).seal)


def withheld_note(snap) -> str:
    """The fixed note that names why the seal was withheld, in the configured language."""
    if isinstance(snap, Snapshot):
        reasons, platform = snap.reasons, snap.platform
    else:
        platform = str(snap or "").strip().lower()
        reasons = tuple(snapshot(platform).reasons) or ("unknown",)
    parts = []
    for reason in reasons:
        template = REASONS.get(reason, REASONS["unknown"])
        parts.append(template.format(platform=platform or "this platform"))
    return WITHHELD_NOTE.format(reason=" ".join(parts))
