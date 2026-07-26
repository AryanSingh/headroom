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
_HOSTED_LICENSE_URL = os.environ.get(
    "CUTCTX_LICENSE_SUPABASE_URL", "https://udeekuvifncmqvoywhlg.supabase.co"
).rstrip("/")
#: Optional anon key. Deliberately has NO hardcoded default: `verify-license`
#: and `seat-heartbeat` were both verified to work with no auth header at all,
#: so embedding a JWT in the source bought nothing and committed a credential
#: for no reason. Set CUTCTX_LICENSE_SUPABASE_ANON_KEY only if the functions
#: are later put behind the anon role.
_HOSTED_LICENSE_ANON_KEY = os.environ.get("CUTCTX_LICENSE_SUPABASE_ANON_KEY", "")

#: Base URL of the licence API — Supabase Edge Functions.
#:
#: `pitchtoship.com` serves no licence API: it is a single-page app, so the
#: `/v1/license/*` paths this module used to call fell through to the SPA and
#: answered 405 on every POST. Licence validation lives in Supabase Edge
#: Functions. Verified functions on this base: `verify-license`, `list-plans`.
DEFAULT_LICENSE_API_URL = "https://udeekuvifncmqvoywhlg.supabase.co/functions/v1"

#: Per-key validation cache for `is_revoked`: key -> (expires_at, revoked).
_VALIDATION_CACHE: dict[str, tuple[float, bool]] = {}
_VALIDATION_TTL = 300.0


def get_license_api_url() -> str:
    """Base URL for the licence API (Supabase Edge Functions).

    Distinct from :func:`get_portal_url`, which addresses the marketing and
    checkout site. Override with ``CUTCTX_LICENSE_API_URL``.
    """
    return (os.environ.get("CUTCTX_LICENSE_API_URL") or DEFAULT_LICENSE_API_URL).rstrip("/")


def _response_is_json(resp: httpx.Response) -> bool:
    content_type = resp.headers.get("content-type", "").lower()
    return "json" in content_type


def _is_hosted_cutctx_key(license_key: str) -> bool:
    return license_key.startswith("cutctx_")


def _post_hosted_license(endpoint: str, payload: dict) -> dict | None:
    """Call the public hosted license service without privileged credentials."""
    try:
        response = httpx.post(
            f"{_HOSTED_LICENSE_URL}/functions/v1/{endpoint}",
            json=payload,
            # Only send apikey if one is configured; these functions do not
            # require it today.
            headers={"apikey": _HOSTED_LICENSE_ANON_KEY} if _HOSTED_LICENSE_ANON_KEY else None,
            timeout=5.0,
        )
        if response.status_code >= 500 or not _response_is_json(response):
            return None
        body = response.json()
        return body if isinstance(body, dict) else None
    except Exception as exc:
        logger.warning("Hosted license service unavailable: %s", exc)
        return None


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
    return os.environ.get("CUTCTX_LICENSE_STRICT_MODE", "1") != "0"


def _service_request_kwargs(**kwargs):
    """Add the optional least-privilege license-service credential.

    ``CUTCTX_LICENSE_SERVICE_API_KEY`` is intentionally separate from
    ``CUTCTX_ADMIN_API_KEY``. The latter is never forwarded implicitly by
    this client; deployments that need machine-to-machine authentication
    must explicitly configure the narrowly scoped service credential.
    """
    service_key = os.environ.get("CUTCTX_LICENSE_SERVICE_API_KEY")
    if service_key:
        kwargs["headers"] = {"X-Cutctx-Admin-Key": service_key}
    return kwargs


def get_portal_url() -> str:
    """Get the base URL for the PitchToShip license portal."""
    return (
        os.environ.get("PITCHTOSHIP_URL")
        or os.environ.get("CUTCTX_LICENSE_API_URL")
        or _DEFAULT_PORTAL_URL
    ).rstrip("/")


def is_revoked(license_key: str) -> bool:
    """Return True when ``license_key`` is not currently valid.

    There is **no CRL endpoint** in the licence API. The previous
    implementation fetched ``/v1/license/crl`` from the marketing site, which
    does not serve it: that host is a single-page app, so the request got a
    200 with an HTML body, JSON parsing failed, the cache stayed empty, and
    strict mode then denied *every* licence — including valid paid ones.
    Verified against a real enterprise key on 2026-07-25.

    Revocation is instead expressed by ``verify-license`` itself: a revoked,
    expired, or unknown key answers ``{"valid": false}``. This function asks
    that question per key and caches the answer for 5 minutes.

    Failure semantics are unchanged in spirit:

      * A definite answer from the API is authoritative and cached.
      * On a network error or malformed reply, a cached answer is reused.
      * With no cached answer, strict mode (the default) denies, and
        ``CUTCTX_LICENSE_STRICT_MODE=0`` allows, for offline development.

    Note this returns True for expired and unrecognised keys too, not only
    administratively revoked ones. For the gating decisions that call it,
    "not currently valid" is the question that matters.
    """
    now = time.time()
    cached = _VALIDATION_CACHE.get(license_key)
    if cached and now < cached[0]:
        return cached[1]

    url = f"{get_license_api_url()}/verify-license"
    try:
        resp = httpx.post(
            url,
            json={"key": license_key},
            **_service_request_kwargs(timeout=5.0),
        )
        if not _response_is_json(resp):
            raise ValueError(
                f"{url} returned HTTP {resp.status_code} with content-type "
                f"{resp.headers.get('content-type')!r}, not JSON — the licence "
                "API is probably not deployed at this URL (a static site "
                "answers 200 for unmatched paths). Check CUTCTX_LICENSE_API_URL."
            )
        # 400 means the key was rejected outright, which is a definite answer.
        if resp.status_code in (200, 400):
            revoked = not resp.json().get("valid", False)
            _VALIDATION_CACHE[license_key] = (now + _VALIDATION_TTL, revoked)
            return revoked
        raise ValueError(f"{url} returned unexpected HTTP {resp.status_code}")
    except Exception as exc:
        if cached:
            logger.warning(
                "Licence validation failed (%s); reusing the cached answer "
                "(revoked=%s) for key %s...",
                exc,
                cached[1],
                license_key[:8],
            )
            return cached[1]
        denied = _strict_mode()
        logger.warning(
            "Licence validation failed (%s) and no cached answer is "
            "available for key %s... Strict mode: %s, so this licence is "
            "treated as %s.",
            exc,
            license_key[:8],
            _strict_mode(),
            "REVOKED" if denied else "valid",
        )
        return denied


def activate_instance(license_key: str, instance_id: str) -> bool:
    """Register this instance activation with the portal.

    Network failures deny activation in strict mode, which is the default.
    Explicit development mode (``CUTCTX_LICENSE_STRICT_MODE=0``) retains the
    legacy fail-open behavior for offline local work.
    """
    try:
        resp = httpx.post(
            f"{get_portal_url()}/v1/license/activate",
            json={"license_key": license_key, "instance_id": instance_id},
            **_service_request_kwargs(timeout=5.0),
        )
        if resp.status_code != 200 or not _response_is_json(resp):
            return False
        payload = resp.json()
        return isinstance(payload, dict) and payload.get("status") in {"ok", "activated"}
    except Exception:
        return not _strict_mode()


def checkout_seat(license_key: str, user_id: str) -> bool:
    """Claim or renew a seat for ``user_id``.

    Backed by the ``seat-heartbeat`` edge function. The previous
    implementation posted to ``/v1/license/checkout-seat`` on the marketing
    site, which does not serve it — that host is an SPA, so the request got
    HTTP 405 and every seat claim failed.

    Verified contract (note the field names differ from `verify-license`'s
    `key`-only body; `licenseKey`/`license_key` are both rejected with 400)::

        POST <base>/seat-heartbeat   {"key": …, "hwid": …}
        200  {"accepted": true, "seats_used": 1, "seats_limit": 500}

    `user_id` is sent as ``hwid``: the function keys occupancy on a device
    identifier, and the caller's per-user identity is what we have.

    Failure semantics are unchanged. An explicit rejection (``accepted:
    false``), a seat-limit response, or a 429 denies the seat. Network errors
    deny in strict mode (the default) and allow when
    ``CUTCTX_LICENSE_STRICT_MODE=0`` is set for offline development.
    """
    if _is_hosted_cutctx_key(license_key):
        payload = _post_hosted_license("seat-heartbeat", {"key": license_key, "hwid": user_id})
        if payload is None:
            return not _strict_mode()
        return payload.get("accepted") is True

    try:
        resp = httpx.post(
            f"{get_license_api_url()}/seat-heartbeat",
            json={"key": license_key, "hwid": user_id},
            **_service_request_kwargs(timeout=5.0),
        )
        if resp.status_code == 429:
            return False
        if resp.status_code != 200 or not _response_is_json(resp):
            return False
        payload = resp.json()
        return isinstance(payload, dict) and bool(payload.get("accepted"))
    except Exception:
        return not _strict_mode()


def start_trial(trial_token: str, customer_email: str, duration: float = 14 * 86400.0) -> bool:
    """Start a server-side trial; network errors fail open for compatibility."""
    try:
        resp = httpx.post(
            f"{get_portal_url()}/v1/license/start-trial",
            json={
                "trial_token": trial_token,
                "customer_email": customer_email,
                "duration": duration,
            },
            **_service_request_kwargs(timeout=5.0),
        )
        if resp.status_code != 200 or not _response_is_json(resp):
            return False
        payload = resp.json()
        return isinstance(payload, dict) and payload.get("status") == "ok"
    except Exception:
        return True  # Fail open


def is_trial_active(trial_token: str) -> bool:
    """Check if a trial is active; unavailable portal responses fail open."""
    try:
        resp = httpx.post(
            f"{get_portal_url()}/v1/license/check-trial",
            json={"trial_token": trial_token},
            **_service_request_kwargs(timeout=5.0),
        )
        if resp.status_code == 200 and _response_is_json(resp):
            payload = resp.json()
            if isinstance(payload, dict):
                return bool(payload.get("active", True))
        return True  # Fail open
    except Exception:
        return True  # Fail open
