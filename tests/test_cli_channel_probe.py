"""Tests for the `evosci channel probe` command."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import typer

from EvoScientist.cli import commands


def _base_config(**kwargs):
    data = {
        "channel_enabled": "",
        "telegram_bot_token": "",
        "discord_bot_token": "",
        "slack_bot_token": "",
        "slack_app_token": "",
        "wechat_wecom_corp_id": "",
        "wechat_wecom_agent_id": "",
        "wechat_wecom_secret": "",
        "feishu_app_id": "",
        "feishu_app_secret": "",
        "dingtalk_client_id": "",
        "dingtalk_client_secret": "",
        "email_imap_host": "",
        "email_imap_username": "",
        "email_imap_password": "",
        "email_smtp_host": "",
        "email_smtp_username": "",
        "email_smtp_password": "",
        "email_from_address": "",
        "qq_app_id": "",
        "qq_app_secret": "",
        "signal_phone_number": "",
    }
    data.update(kwargs)
    return SimpleNamespace(**data)


def test_channel_probe_requires_target_or_config(monkeypatch):
    import EvoScientist.config as config_mod

    monkeypatch.setattr(config_mod, "load_config", lambda: _base_config())
    with pytest.raises(typer.Exit) as exc:
        commands.channel_probe(None)
    assert exc.value.exit_code == 1


def test_channel_probe_rejects_unsupported_channel(monkeypatch):
    import EvoScientist.config as config_mod

    monkeypatch.setattr(config_mod, "load_config", lambda: _base_config())
    with pytest.raises(typer.Exit) as exc:
        commands.channel_probe("not-a-channel")
    assert exc.value.exit_code == 1


def test_channel_probe_fails_when_required_fields_missing(monkeypatch):
    import EvoScientist.config as config_mod
    import EvoScientist.config.onboard as onboard_mod

    called = {"count": 0}

    def _fake_probe(_ch, _cfg, _updates):
        called["count"] += 1
        return True

    monkeypatch.setattr(config_mod, "load_config", lambda: _base_config())
    monkeypatch.setattr(onboard_mod, "_probe_channel", _fake_probe)

    with pytest.raises(typer.Exit) as exc:
        commands.channel_probe("feishu")
    assert exc.value.exit_code == 1
    assert called["count"] == 0


def test_channel_probe_uses_configured_channels_and_succeeds(monkeypatch):
    import EvoScientist.config as config_mod
    import EvoScientist.config.onboard as onboard_mod

    calls: list[str] = []

    def _fake_probe(ch, _cfg, _updates):
        calls.append(ch)
        return True

    cfg = _base_config(
        channel_enabled="feishu",
        feishu_app_id="cli_test",
        feishu_app_secret="secret",
    )
    monkeypatch.setattr(config_mod, "load_config", lambda: cfg)
    monkeypatch.setattr(onboard_mod, "_probe_channel", _fake_probe)

    commands.channel_probe(None)
    assert calls == ["feishu"]


def test_channel_probe_bubbles_probe_failure(monkeypatch):
    import EvoScientist.config as config_mod
    import EvoScientist.config.onboard as onboard_mod

    cfg = _base_config(
        channel_enabled="feishu",
        feishu_app_id="cli_test",
        feishu_app_secret="secret",
    )
    monkeypatch.setattr(config_mod, "load_config", lambda: cfg)
    monkeypatch.setattr(onboard_mod, "_probe_channel", lambda *_a, **_k: False)

    with pytest.raises(typer.Exit) as exc:
        commands.channel_probe(None)
    assert exc.value.exit_code == 1
