"""The delivery policy: the host's own StreamingConfig resolution (D7, H9).

The plugin runs inside the Hermes process, so it uses ``gateway.config.StreamingConfig`` when the import
works and the versioned compatibility copy when it does not. These cases pin the copy to the host's
semantics, read at ``gateway/config.py:521`` and ``:509``.
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
    for platform in ("api_server", "webhook", "msgraph_webhook", "local"):
        assert delivery.is_messaging(platform) is False


def test_the_seal_follows_the_host_matrix():
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
        assert delivery.seal_allowed("telegram", {"streaming": streaming}) is expected[name], name


def test_a_platform_override_only_narrows():
    overridden = {
        "streaming": {"enabled": True},
        "display": {"platforms": {"telegram": {"streaming": False}}},
    }
    assert delivery.seal_allowed("telegram", overridden) is True
    assert delivery.seal_allowed("discord", overridden) is False
    plain_off = {"streaming": {"enabled": False}, "display": {"platforms": {"discord": {"streaming": True}}}}
    assert delivery.seal_allowed("discord", plain_off) is True


def test_the_cli_uses_display_streaming_and_is_the_only_exception():
    assert delivery.seal_allowed("cli", {"display": {"streaming": False}}) is True
    assert delivery.seal_allowed("cli", {"display": {"streaming": True}}) is False
    assert delivery.seal_allowed("cli", {}) is True
    assert delivery.effective_streaming("cli", {"display": {"streaming": True}}) is True


def test_the_desktop_app_withholds_the_seal():
    """D7: it keeps the D1 warning instead of an exception."""
    assert delivery.seal_allowed("desktop", {"streaming": {"enabled": False}}) is False
    assert "draft may be visible" in delivery.withheld_note("desktop")


def test_the_api_server_keeps_its_documented_sse_exception():
    on = {"streaming": {"enabled": True}}
    assert delivery.seal_allowed("api_server", on) is True
    assert delivery.seal_allowed("webhook", on) is True


def test_the_withheld_note_names_the_platform_and_the_fix_without_claiming_the_seal():
    note = delivery.withheld_note("telegram")
    assert "telegram" in note
    assert "streaming.enabled" in note
    assert "seal is withheld" in note
    assert "Verified by Cited" not in note
