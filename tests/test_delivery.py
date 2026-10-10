"""The delivery policy of cited mode: reading the effective streaming config (D1, H9)."""

from __future__ import annotations

from hermes_cited import delivery


def test_simple_yaml_reads_the_nested_streaming_config():
    config = delivery.simple_yaml(
        "streaming:\n  enabled: true\ndisplay:\n  platforms:\n    telegram:\n      streaming: false\n"
    )
    assert config["streaming"]["enabled"] is True
    assert config["display"]["platforms"]["telegram"]["streaming"] is False


def test_global_streaming_understands_the_transport_off_alias():
    assert delivery.global_streaming({"streaming": {"enabled": True}}) is True
    assert delivery.global_streaming({"streaming": {"enabled": True, "transport": "off"}}) is False
    assert delivery.global_streaming({"streaming": {"enabled": False}}) is False
    assert delivery.global_streaming({}) is False


def test_effective_streaming_of_a_messaging_platform():
    on = {"streaming": {"enabled": True}}
    assert delivery.effective_streaming("telegram", on) is True
    assert delivery.effective_streaming("slack", on) is True
    overridden = {
        "streaming": {"enabled": True},
        "display": {"platforms": {"telegram": {"streaming": False}}},
    }
    assert delivery.effective_streaming("telegram", overridden) is False
    assert delivery.effective_streaming("discord", overridden) is True
    assert delivery.effective_streaming("telegram", {"streaming": {"enabled": False}}) is False


def test_effective_streaming_of_the_cli_uses_display_streaming():
    assert delivery.effective_streaming("cli", {"display": {"streaming": True}}) is True
    assert delivery.effective_streaming("cli", {"display": {"streaming": False}}) is False
    assert delivery.effective_streaming("cli", {}) is False


def test_the_seal_is_withheld_only_on_a_streaming_messaging_surface():
    streaming = {"streaming": {"enabled": True}}
    assert delivery.seal_allowed("telegram", streaming) is False
    assert delivery.seal_allowed("telegram", {"streaming": {"enabled": False}}) is True
    assert delivery.seal_allowed("cli", {"display": {"streaming": True}}) is True
    assert delivery.seal_allowed("cli", {}) is True


def test_the_cli_streaming_is_still_read_for_the_documentation():
    assert delivery.effective_streaming("cli", {"display": {"streaming": True}}) is True
    assert delivery.effective_streaming("cli", {}) is False


def test_the_desktop_surface_is_not_configurable_from_the_plugin():
    """The SSE route of the API server is out of reach; the plugin keeps the seal and documents it."""
    assert delivery.seal_allowed("desktop", {"streaming": {"enabled": True}}) is True


def test_the_withheld_note_names_the_platform_and_the_fix_without_claiming_the_seal():
    note = delivery.withheld_note("telegram")
    assert "telegram" in note
    assert "streaming.enabled" in note
    assert "seal is withheld" in note
    assert "Verified by Cited" not in note
