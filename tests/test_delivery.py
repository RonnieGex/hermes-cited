"""The delivery policy: the snapshot of the surfaces that could have been seen (D13, H9).

Round 4 freezes the effective configuration at the start of the turn and covers every surface of the host
that delivers text or voice: ``streaming`` with the platform override, ``display.streaming`` for the CLI,
``interim_assistant_messages`` (global and per platform), ``tts.auto_tts``, ``api_server`` and ``desktop``.
The compatibility copy of ``gateway.config.StreamingConfig`` is still pinned to the host's semantics, read
at ``gateway/config.py:487`` and ``:509``; the commentary resolver is pinned to
``gateway/display_config.py:11``.
"""

from __future__ import annotations

from hermes_cited import delivery

HOST_MATRIX = [
    ({"mode": "edit"}, True),
    ({"enabled": True}, True),
    ({"enabled": True, "transport": False}, False),
    ({"enabled": False}, False),
    ({"mode": "off"}, False),
    ({"transport": "off"}, False),
    ({"mode": "auto"}, True),
    ({"enabled": "yes"}, True),
    ({"enabled": "false"}, False),
    ({}, False),
]

#: Nothing else can have been seen: streaming off for that platform and no commentary elsewhere.
QUIET = {
    "streaming": {"enabled": False},
    "display": {"platforms": {"telegram": {"interim_assistant_messages": False}}},
}


def test_simple_yaml_reads_the_nested_streaming_config():
    config = delivery.simple_yaml(
        "streaming:\n  enabled: true\ndisplay:\n  platforms:\n    telegram:\n      streaming: false\n"
    )
    assert config["streaming"]["enabled"] is True
    assert config["display"]["platforms"]["telegram"]["streaming"] is False


def test_the_compatibility_copy_reproduces_the_host_mode_alias_and_yaml_booleans():
    for raw, expected in HOST_MATRIX:
        built = delivery.CompatStreamingConfig.from_dict(raw)
        assert built.globally_enabled is expected, raw


def test_a_yaml_boolean_transport_is_normalised_not_treated_as_auto():
    built = delivery.CompatStreamingConfig.from_dict({"enabled": True, "transport": False})
    assert built.transport == "off"
    assert built.globally_enabled is False


def test_the_compatibility_copy_narrows_by_platform_override():
    built = delivery.CompatStreamingConfig.from_dict({"enabled": True})
    assert built.enabled_for(None) is True
    assert built.enabled_for(False) is False
    assert built.enabled_for(True) is True


def test_an_unknown_messaging_platform_is_not_exempt():
    on = {"streaming": {"enabled": True}}
    for platform in ("wecom", "feishu", "dingtalk", "qqbot", "acme-chat"):
        assert delivery.is_messaging(platform) is True
        assert delivery.seal_allowed(platform, on) is False


def test_the_host_platforms_of_the_release_are_messaging_unless_documented_otherwise():
    for platform in ("telegram", "slack", "discord", "whatsapp", "signal", "matrix", "email", "relay"):
        assert delivery.is_messaging(platform) is True
    for platform in ("webhook", "msgraph_webhook", "local"):
        assert delivery.is_messaging(platform) is False
    for platform in ("api_server", "desktop"):
        assert delivery.is_messaging(platform) is False
        assert delivery.snapshot(platform, config=QUIET).sse is True


def test_the_seal_follows_the_host_streaming_matrix():
    """D11/H16: the readable surfaces follow the host; the seal itself is never emitted today."""
    expected = {
        "mode_edit": False,
        "enabled": False,
        "transport_off_bool": True,
        "explicit_off": True,
    }
    raw = {
        "mode_edit": {"mode": "edit"},
        "enabled": {"enabled": True},
        "transport_off_bool": {"enabled": True, "transport": False},
        "explicit_off": {"enabled": False},
    }
    for name, streaming in raw.items():
        config = {
            "streaming": streaming,
            "display": {"platforms": {"telegram": {"interim_assistant_messages": False}}},
        }
        snap = delivery.snapshot("telegram", config=config)
        assert snap.surface_clear is expected[name], name
        assert snap.accredited is False
        assert snap.seal is False, name


def test_a_platform_override_only_narrows():
    overridden = {
        "streaming": {"enabled": True},
        "display": {"platforms": {"telegram": {"streaming": False, "interim_assistant_messages": False}}},
    }
    assert delivery.snapshot("telegram", config=overridden).surface_clear is True
    assert delivery.snapshot("discord", config=overridden).surface_clear is False
    plain_off = {"streaming": {"enabled": False}, "display": {"interim_assistant_messages": False}}
    assert delivery.snapshot("discord", config=plain_off).surface_clear is True


def test_the_cli_uses_display_streaming_and_commentary():
    quiet = {"display": {"streaming": False, "interim_assistant_messages": False}}
    assert delivery.snapshot("cli", config=quiet).surface_clear is True
    assert delivery.snapshot("cli", config={"display": {"streaming": True, "interim_assistant_messages": False}}).surface_clear is False
    assert delivery.snapshot("cli", config={}).surface_clear is False
    assert delivery.effective_streaming("cli", {"display": {"streaming": True}}) is True
    assert delivery.commentary_enabled({}, "cli") is True


def test_the_desktop_and_the_api_server_always_withhold():
    """M-R3-4: ``api_server`` is the SSE route of the desktop app, not an exception."""
    quiet = {"streaming": {"enabled": False}, "display": {"interim_assistant_messages": False}}
    for platform in ("desktop", "api_server"):
        snap = delivery.snapshot(platform, config=quiet)
        assert snap.seal is False
        assert snap.sse is True
        assert "sse" in snap.reasons


def test_interim_commentary_withholds_even_with_streaming_off():
    """M-R3-4: the real stream consumer still delivers ``MODEL_COMMENTARY_999``."""
    config = {"streaming": {"enabled": False}}
    snap = delivery.snapshot("telegram", config=config)
    assert snap.streaming is False
    assert snap.commentary is True
    assert snap.seal is False
    assert "commentary" in snap.reasons


def test_the_commentary_resolver_follows_the_host_order():
    global_on = {"display": {"interim_assistant_messages": True}}
    assert delivery.commentary_enabled(global_on, "telegram") is True
    per_platform_off = {"display": {"interim_assistant_messages": True, "platforms": {"telegram": {"interim_assistant_messages": False}}}}
    assert delivery.commentary_enabled(per_platform_off, "telegram") is False
    assert delivery.commentary_enabled({}, "signal") is False
    assert delivery.commentary_enabled({}, "telegram") is True


def test_streaming_tts_withholds():
    config = {"streaming": {"enabled": False}, "tts": {"auto_tts": True}, "display": {"interim_assistant_messages": False}}
    snap = delivery.snapshot("telegram", config=config)
    assert snap.tts is True
    assert snap.seal is False
    assert "tts" in snap.reasons
    assert delivery.snapshot("telegram", config={"tts": {"auto_tts": "false"}}).tts is False


def test_webhook_and_local_are_not_user_surfaces():
    config = {"streaming": {"enabled": False}}
    for platform in ("webhook", "msgraph_webhook", "local"):
        snap = delivery.snapshot(platform, config=config)
        assert snap.surface_clear is True
        assert snap.seal is False


def test_an_unreadable_configuration_withholds():
    assert delivery.snapshot("telegram", config="not a mapping").seal is False
    snap = delivery.snapshot("telegram", config="not a mapping")
    assert snap.readable is False
    assert "unreadable" in snap.reasons


def test_the_snapshot_is_frozen_and_does_not_follow_a_later_change(tmp_path):
    home = tmp_path
    (home / "config.yaml").write_text("streaming:\n  enabled: false\ndisplay:\n  interim_assistant_messages: false\n", encoding="utf-8")
    snap = delivery.snapshot("telegram", home=home)
    assert snap.surface_clear is True
    (home / "config.yaml").write_text("streaming:\n  enabled: true\n", encoding="utf-8")
    assert snap.surface_clear is True
    assert delivery.snapshot("telegram", home=home).surface_clear is False
    assert delivery.seal_allowed("telegram", snap=snap) is False


def test_the_withheld_note_names_the_platform_and_the_fix_without_claiming_the_seal():
    snap = delivery.snapshot("telegram", config={"streaming": {"enabled": True}})
    note = delivery.withheld_note(snap)
    assert "telegram" in note
    assert "streaming.enabled" in note
    assert "withheld" in note
    assert "Verified by Cited" not in note


def test_the_withheld_note_explains_the_sse_and_the_commentary():
    note = delivery.withheld_note(delivery.snapshot("api_server", config={}))
    assert "SSE" in note
    commentary = delivery.withheld_note(delivery.snapshot("telegram", config={"streaming": {"enabled": False}}))
    assert "interim_assistant_messages" in commentary
