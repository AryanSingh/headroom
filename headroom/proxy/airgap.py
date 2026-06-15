"""Air-gap mode support for offline deployments."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def is_offline() -> bool:
    """Check if running in offline/air-gap mode."""
    return os.environ.get("HEADROOM_OFFLINE_MODE", "0") == "1"


def check_offline_compat() -> None:
    """Verify all required resources are available for offline operation."""
    if not is_offline():
        return
    if not os.environ.get("HF_HUB_OFFLINE"):
        logger.warning(
            "HEADROOM_OFFLINE_MODE=1 but HF_HUB_OFFLINE not set. "
            "Model downloads may fail."
        )
    if not os.environ.get("HEADROOM_LICENSE_HMAC_SECRET"):
        raise RuntimeError(
            "HEADROOM_OFFLINE_MODE=1 requires HEADROOM_LICENSE_HMAC_SECRET "
            "for offline license validation."
        )
    logger.info("Offline mode: external network calls disabled.")
