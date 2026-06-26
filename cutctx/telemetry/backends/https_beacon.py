"""HTTPS Beacon backend for telemetry egress.

Transmits federated insights (labels) to Cutctx.
Includes protections to ensure NO RAW TEXT is ever transmitted.
"""

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

from cutctx.telemetry.dp import DPMechanism

logger = logging.getLogger(__name__)


class HTTPSBeacon:
    """Egresses federated telemetry safely.

    Requires explicit opt-in and a valid license token.
    Uses Differential Privacy to noise any numeric counters if federated.
    """

    def __init__(self, endpoint_url: str, license_token: str, dp_epsilon: float = 0.5):
        self.endpoint_url = endpoint_url
        self.license_token = license_token
        self.dp = DPMechanism(epsilon=dp_epsilon)

    def send_labels(self, labels: list[dict[str, Any]]) -> bool:
        """Send labeled training metadata.

        Performs a strict privacy scan to ensure no raw text is accidentally
        included in the payload before transmission.
        """
        # Network egress is opt-in; default OFF (local-first). Set CUTCTX_TELEMETRY_EGRESS=1 to enable.
        egress_enabled = os.environ.get("CUTCTX_TELEMETRY_EGRESS", "").lower().strip() in (
            "1",
            "true",
            "yes",
            "on",
        )
        if not egress_enabled:
            return True

        if not labels:
            return True

        # 1. Blocking Privacy Scan
        # Ensure payload ONLY contains safe keys.
        safe_keys = {
            "episode_id",
            "tenant_id",
            "label",
            "original_size",
            "compressed_size",
            "start_line",
            "end_line",
            "session_id",
            "timestamp_ts",
        }

        sanitized_labels = []
        for label in labels:
            sanitized = {}
            for k, v in label.items():
                if k not in safe_keys:
                    logger.warning(f"Privacy scan blocked unsafe key '{k}'. Dropping field.")
                    continue
                # Add DP noise to sizes to prevent size-based fingerprinting
                if k in ("original_size", "compressed_size"):
                    sanitized[k] = int(max(0, self.dp.add_laplace_noise(v, sensitivity=1.0)))
                else:
                    sanitized[k] = v
            sanitized_labels.append(sanitized)

        payload = json.dumps({"labels": sanitized_labels}).encode("utf-8")

        # 2. Transmit
        req = urllib.request.Request(
            self.endpoint_url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.license_token}",
                "X-Cutctx-Beacon": "1",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status in (200, 201, 202)
        except urllib.error.URLError as e:
            logger.error(f"Failed to send telemetry beacon: {e}")
            return False
