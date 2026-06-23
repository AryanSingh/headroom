"""Air-gap mode support for offline deployments."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def _env_truthy(name: str) -> bool:
    """Check if an env var is set to a truthy value."""
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def is_offline() -> bool:
    """Check if running in offline/air-gap mode.

    Recognises HEADROOM_OFFLINE_MODE=1 (primary) and
    HEADROOM_AIR_GAP=1 (alias for backward compatibility).
    """
    return _env_truthy("HEADROOM_OFFLINE_MODE") or _env_truthy("HEADROOM_AIR_GAP")


def check_offline_compat() -> None:
    """Verify all required resources are available for offline operation."""
    if not is_offline():
        return
    if not os.environ.get("HF_HUB_OFFLINE"):
        logger.warning(
            "HEADROOM_OFFLINE_MODE / HEADROOM_AIR_GAP is set but HF_HUB_OFFLINE "
            "not set. Model downloads may fail."
        )
    if not os.environ.get("HEADROOM_LICENSE_HMAC_SECRET"):
        raise RuntimeError(
            "HEADROOM_LICENSE_HMAC_SECRET is required in offline/air-gap mode "
            "for offline license validation."
        )
    logger.info("Offline/air-gap mode: external network calls disabled.")
