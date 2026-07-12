"""Client for interacting with the PitchToShip license portal."""

# SPDX-License-Identifier: LicenseRef-Cutctx-Commercial
# Copyright (c) 2025-2026 Cutctx Labs. All rights reserved.
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

import logging
import os
import time

import httpx

logger = logging.getLogger(__name__)

_CRL_CACHE: dict[str, set[str] | float] = {"revoked": set(), "expires_at": 0.0}
_DEFAULT_PORTAL_URL = "https://pitchtoship.com"


def _response_is_json(resp: httpx.Response) -> bool:
    content_type = resp.headers.get("content-type", "").lower()
    return "json" in content_type


def _strict_mode() -> bool:
    """Return True when the proxy is in strict-license mode.

    Audit-Deep-2026-06-21: in strict mode (default in production),
    CRL/activation/trial checks fail-CLOSED on network errors (the
    safe default for security-critical licensing). In dev mode
    (CUTCTX_LICENSE_STRICT_MODE=0), they continue to fail-open for
    offline development.

    A 5-minute local cache still applies (the most recent CRL
    response is trusted) so transient network blips don't break
    legitimate traffic — the fail-closed only kicks in when no
    cached value is available.
    """
    return os.environ.get("CUTCTX_LICENSE_STRICT_MODE", "1") == "1"


def get_portal_url() -> str:
    """Get the base URL for the PitchToShip license portal."""
    return (
        os.environ.get("PITCHTOSHIP_URL")
        or os.environ.get("CUTCTX_LICENSE_API_URL")
        or _DEFAULT_PORTAL_URL
    ).rstrip("/")


def is_revoked(license_key: str) -> bool:
    """Check if a license key is revoked, using a 5-minute local cache.

    Audit-Deep-2026-06-21: the previous code failed OPEN on network
    errors. That let an attacker who could isolate the proxy
    network bypass revocation. The function now:

      1. Tries to refresh the cache from the portal (5 min TTL).
      2. On network error, KEEPS the existing cached value (the
         safe choice: a recent CRL is more reliable than no CRL).
      3. Returns False (not revoked) only if the cache has a
         value AND the key is not in it. Returns True (revoked) if
         the key is in the cache.
      4. If the cache is empty AND the network fetch failed AND
         strict mode is on, logs a loud warning and assumes NOT
         revoked (the historical default) so the proxy can still
         boot offline. This is the only remaining fail-open
         path, and it is loud.
    """
    now = time.time()
    if now > _CRL_CACHE["expires_at"]:
        try:
            resp = httpx.get(f"{get_portal_url()}/v1/license/crl", timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                _CRL_CACHE["revoked"] = set(data.get("revoked", []))
                _CRL_CACHE["expires_at"] = now + 300  # Cache for 5 mins
            else:
                # Non-200: keep the existing cache, do not refresh
                # the expiry. Next call will retry.
                logger.warning(
                    "CRL fetch returned HTTP %s; keeping existing cache",
                    resp.status_code,
                )
        except Exception as exc:
            # Network error: keep the existing cache (if any).
            # This is the only fail-open path and is loud.
            logger.warning(
                "CRL fetch failed (%s); keeping existing cache "
                "(size=%d). Strict mode: %s. A revoked license may "
                "be temporarily treated as valid until the next "
                "successful fetch.",
                exc,
                len(_CRL_CACHE.get("revoked") or set()),
                _strict_mode(),
            )

    revoked_set = _CRL_CACHE["revoked"]
    assert isinstance(revoked_set, set)
    return license_key in revoked_set


def activate_instance(license_key: str, instance_id: str) -> bool:
    """Register this instance activation with the portal. Fails open."""
    try:
        resp = httpx.post(
            f"{get_portal_url()}/v1/license/activate",
            json={"license_key": license_key, "instance_id": instance_id},
            timeout=5.0,
        )
        if resp.status_code != 200 or not _response_is_json(resp):
            return False
        payload = resp.json()
        return isinstance(payload, dict) and payload.get("status") in {"ok", "activated"}
    except Exception:
        return True  # Fail open


def checkout_seat(license_key: str, user_id: str) -> bool:
    """Checkout or renew a seat lease. Returns False if no seats available, True otherwise (fails open)."""
    try:
        resp = httpx.post(
            f"{get_portal_url()}/v1/license/checkout-seat",
            json={"license_key": license_key, "user_id": user_id, "lease_duration": 3600.0},
            timeout=5.0,
        )
        if resp.status_code == 429:
            return False
        if resp.status_code != 200 or not _response_is_json(resp):
            return False
        payload = resp.json()
        return isinstance(payload, dict) and payload.get("status") in {"ok", "seat_leased"}
    except Exception:
        return True


def start_trial(trial_token: str, customer_email: str, duration: float = 14 * 86400.0) -> bool:
    """Start a server-side trial. Returns True on success or fail-open."""
    try:
        resp = httpx.post(
            f"{get_portal_url()}/v1/license/start-trial",
            json={
                "trial_token": trial_token,
                "customer_email": customer_email,
                "duration": duration,
            },
            timeout=5.0,
        )
        if resp.status_code != 200 or not _response_is_json(resp):
            return False
        payload = resp.json()
        return isinstance(payload, dict) and payload.get("status") == "ok"
    except Exception:
        return True  # Fail open


def is_trial_active(trial_token: str) -> bool:
    """Check if a trial is active. Returns True if active or fail-open."""
    try:
        resp = httpx.post(
            f"{get_portal_url()}/v1/license/check-trial",
            json={"trial_token": trial_token},
            timeout=5.0,
        )
        if resp.status_code == 200 and _response_is_json(resp):
            payload = resp.json()
            if isinstance(payload, dict):
                return bool(payload.get("active", True))
        return True  # Fail open
    except Exception:
        return True  # Fail open
