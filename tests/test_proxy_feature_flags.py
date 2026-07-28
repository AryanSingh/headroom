"""Durable desired-state contract for Governance feature toggles."""

from __future__ import annotations

import json
import stat

from cutctx.proxy.feature_flags import (
    apply_desired_feature_flags,
    load_desired_feature_flags,
    persist_desired_feature_flags,
)
from cutctx.proxy.models import ProxyConfig


def test_persisted_feature_flags_round_trip_atomically_with_private_permissions(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("CUTCTX_CONFIG_DIR", str(tmp_path / "config"))

    persisted = persist_desired_feature_flags(
        {"firewall_enabled": True, "rate_limit_enabled": False}
    )

    path = tmp_path / "config" / "feature_flags.json"
    assert persisted == {"firewall_enabled": True, "rate_limit_enabled": False}
    assert load_desired_feature_flags() == persisted
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "version": 1,
        "flags": persisted,
    }
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert list(path.parent.glob(".feature_flags.json.*.tmp")) == []


def test_loading_malformed_or_unknown_desired_flags_fails_closed(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    monkeypatch.setenv("CUTCTX_CONFIG_DIR", str(config_dir))
    (config_dir / "feature_flags.json").write_text(
        json.dumps(
            {
                "version": 1,
                "flags": {
                    "firewall_enabled": "yes",
                    "not_a_real_flag": True,
                    "rate_limit_enabled": False,
                },
            }
        ),
        encoding="utf-8",
    )

    assert load_desired_feature_flags() == {"rate_limit_enabled": False}


def test_apply_desired_feature_flags_configures_the_next_proxy_start(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CUTCTX_CONFIG_DIR", str(tmp_path / "config"))
    persist_desired_feature_flags(
        {
            "firewall_enabled": True,
            "rate_limit_enabled": False,
            "audit_enabled": False,
        }
    )
    config = ProxyConfig(
        firewall_enabled=False,
        rate_limit_enabled=True,
        audit_enabled=True,
    )

    applied = apply_desired_feature_flags(config)

    assert applied["firewall_enabled"] is True
    assert config.firewall_enabled is True
    assert config.rate_limit_enabled is False
    assert config.audit_enabled is False
