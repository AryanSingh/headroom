"""Durable desired state for Governance feature flags.

The running proxy remains the authority for *active* state.  This module stores
operator-requested state separately so restart-required changes never masquerade
as live, while the next CLI-managed proxy process can apply the requested state.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from cutctx import paths

logger = logging.getLogger("cutctx.proxy.feature_flags")

_FILE_NAME = "feature_flags.json"
_VERSION = 1

BOOL_FLAG_CONFIG_ATTRS: dict[str, str] = {
    "cache_enabled": "cache_enabled",
    "rate_limit_enabled": "rate_limit_enabled",
    "firewall_enabled": "firewall_enabled",
    "text_compression_engine_enabled": "use_llmlingua",
    "log_template_mining_enabled": "drain3_enabled",
    "audit_enabled": "audit_enabled",
}


def desired_feature_flags_path() -> Path:
    """Return the canonical desired-state file path."""

    return paths.config_dir() / _FILE_NAME


def _validated_flags(value: Any) -> dict[str, bool | str]:
    if not isinstance(value, dict):
        return {}
    validated: dict[str, bool | str] = {}
    for key, flag_value in value.items():
        if key in BOOL_FLAG_CONFIG_ATTRS and isinstance(flag_value, bool):
            validated[key] = flag_value
    return validated


def load_desired_feature_flags() -> dict[str, bool | str]:
    """Load valid desired flags, ignoring malformed or unsupported entries."""

    path = desired_feature_flags_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError, TypeError):
        logger.warning("Ignoring unreadable Governance desired-state file: %s", path)
        return {}
    if not isinstance(payload, dict) or payload.get("version") != _VERSION:
        logger.warning("Ignoring unsupported Governance desired-state file: %s", path)
        return {}
    return _validated_flags(payload.get("flags"))


def persist_desired_feature_flags(
    updates: dict[str, bool | str],
) -> dict[str, bool | str]:
    """Atomically merge validated desired-state updates and return all flags."""

    validated = _validated_flags(updates)
    if set(validated) != set(updates):
        invalid = sorted(set(updates) - set(validated))
        raise ValueError(f"invalid desired feature flags: {', '.join(invalid)}")

    merged = load_desired_feature_flags()
    merged.update(validated)
    path = desired_feature_flags_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"version": _VERSION, "flags": merged}, indent=2, sort_keys=True) + "\n"

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            os.chmod(temp_path, 0o600)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        os.chmod(path, 0o600)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()
    return merged


def apply_desired_feature_flags(config: Any) -> dict[str, bool | str]:
    """Apply durable desired state to a newly constructed proxy config."""

    flags = load_desired_feature_flags()
    for key, value in flags.items():
        attr_name = BOOL_FLAG_CONFIG_ATTRS.get(key)
        if attr_name is not None:
            setattr(config, attr_name, value)
    return flags
