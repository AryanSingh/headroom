"""Client for interacting with the Headroom license portal."""

# SPDX-License-Identifier: LicenseRef-Headroom-Commercial
# Copyright (c) 2025-2026 Headroom Labs. All rights reserved.
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

import os
import time

import httpx

_CRL_CACHE: dict[str, set[str] | float] = {"revoked": set(), "expires_at": 0.0}


def get_portal_url() -> str:
    """Get the base URL for the license portal."""
    return os.environ.get("HEADROOM_LICENSE_API_URL", "https://api.cutctx.dev")


def is_revoked(license_key: str) -> bool:
    """Check if a license key is revoked, using a 5-minute local cache. Fails open."""
    now = time.time()
    if now > _CRL_CACHE["expires_at"]:
        try:
            resp = httpx.get(f"{get_portal_url()}/v1/license/crl", timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                _CRL_CACHE["revoked"] = set(data.get("revoked", []))
                _CRL_CACHE["expires_at"] = now + 300  # Cache for 5 mins
        except Exception:
            pass  # Fail open on network errors

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
        return resp.status_code == 200
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
        return True
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
        return resp.status_code == 200
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
        if resp.status_code == 200:
            return resp.json().get("active", True)
        return True  # Fail open
    except Exception:
        return True  # Fail open
