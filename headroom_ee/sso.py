# SPDX-License-Identifier: LicenseRef-Headroom-Commercial
# Copyright (c) 2025-2026 Headroom Labs. All rights reserved.
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

"""SSO/OAuth2/OIDC middleware for enterprise identity providers.

Validates JWT tokens issued by enterprise IdPs (Okta, Azure AD, Auth0,
Google Workspace) and maps claims to Headroom roles. Supports:
- JWKS-based JWT validation with automatic key rotation
- OIDC discovery (.well-known/openid-configuration)
- Role mapping from configurable claim paths
- Token introspection (RFC 7662) for opaque tokens

Enterprise feature — gated on entitlement_tier >= ENTERPRISE.

Usage:
    from headroom.sso import SsoConfig, SsoValidator

    config = SsoConfig.from_env()
    validator = SsoValidator(config)
    # In FastAPI dependency:
    claims = await validator.validate_token(request)
"""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("headroom.sso")


@dataclass
class SsoConfig:
    """SSO/OIDC configuration."""

    # Provider type: "oidc" (standard OIDC), "jwt" (static JWKS), or "introspect"
    provider_type: str = "oidc"

    # OIDC discovery URL (e.g., https://company.okta.com/.well-known/openid-configuration)
    # When set, jwks_uri and issuer are auto-discovered
    discovery_url: str | None = None

    # JWKS endpoint URL (manual override or when discovery is not used)
    jwks_uri: str | None = None

    # Token issuer — must match the `iss` claim in the JWT
    issuer: str | None = None

    # Expected audience (aud claim). When set, tokens must include this audience.
    audience: str | None = None

    # Token introspection endpoint (RFC 7662) for opaque tokens
    introspection_url: str | None = None
    introspection_client_id: str | None = None
    introspection_client_secret: str | None = None

    # Required scopes/claims for access. Empty = no scope check.
    required_scopes: list[str] = field(default_factory=list)

    # Role mapping: claim path → role. E.g., {"realm_access.roles": "admin"}
    # Supported formats:
    #   - "claim_name" → top-level claim
    #   - "nested.claim" → nested claim (dot-separated)
    #   - "claim_name:value=admin" → match specific value
    role_mapping: dict[str, str] = field(default_factory=dict)

    # Default role for authenticated users with no matching role claim
    default_role: str = "viewer"

    # JWKS cache TTL in seconds (auto-refresh keys)
    jwks_cache_ttl: int = 3600

    # Token validation clock skew tolerance in seconds
    clock_skew_tolerance: int = 60

    # HTTP timeout for discovery/JWKS/introspection requests
    http_timeout: int = 10

    @classmethod
    def from_env(cls) -> SsoConfig:
        """Create SSO config from HEADROOM_SSO_* environment variables."""
        import os

        role_mapping_raw = os.environ.get("HEADROOM_SSO_ROLE_MAPPING", "")
        role_mapping: dict[str, str] = {}
        if role_mapping_raw:
            for pair in role_mapping_raw.split(","):
                if "=" in pair:
                    claim, role = pair.split("=", 1)
                    role_mapping[claim.strip()] = role.strip()

        required_scopes_raw = os.environ.get("HEADROOM_SSO_REQUIRED_SCOPES", "")
        required_scopes = [
            s.strip() for s in required_scopes_raw.split(",") if s.strip()
        ]

        return cls(
            provider_type=os.environ.get("HEADROOM_SSO_PROVIDER_TYPE", "oidc"),
            discovery_url=os.environ.get("HEADROOM_SSO_DISCOVERY_URL"),
            jwks_uri=os.environ.get("HEADROOM_SSO_JWKS_URI"),
            issuer=os.environ.get("HEADROOM_SSO_ISSUER"),
            audience=os.environ.get("HEADROOM_SSO_AUDIENCE"),
            introspection_url=os.environ.get("HEADROOM_SSO_INTROSPECTION_URL"),
            introspection_client_id=os.environ.get("HEADROOM_SSO_INTROSPECTION_CLIENT_ID"),
            introspection_client_secret=os.environ.get(
                "HEADROOM_SSO_INTROSPECTION_CLIENT_SECRET"
            ),
            required_scopes=required_scopes,
            role_mapping=role_mapping,
            default_role=os.environ.get("HEADROOM_SSO_DEFAULT_ROLE", "viewer"),
            jwks_cache_ttl=int(os.environ.get("HEADROOM_SSO_JWKS_CACHE_TTL", "3600")),
            clock_skew_tolerance=int(
                os.environ.get("HEADROOM_SSO_CLOCK_SKEW_TOLERANCE", "60")
            ),
            http_timeout=int(os.environ.get("HEADROOM_SSO_HTTP_TIMEOUT", "10")),
        )

    @classmethod
    def from_proxy_config(cls, config: Any) -> SsoConfig:
        """Create SSO config from a ProxyConfig-like object.

        Falls back to the environment-derived defaults for fields the config
        does not explicitly populate so existing deployments keep working.
        """
        env_cfg = cls.from_env()
        role_mapping = getattr(config, "sso_role_mapping", None)
        if role_mapping is None:
            role_mapping = dict(env_cfg.role_mapping)
        return cls(
            provider_type=getattr(config, "sso_provider_type", None) or env_cfg.provider_type,
            discovery_url=getattr(config, "sso_discovery_url", None) or env_cfg.discovery_url,
            jwks_uri=getattr(config, "sso_jwks_uri", None) or env_cfg.jwks_uri,
            issuer=getattr(config, "sso_issuer", None) or env_cfg.issuer,
            audience=getattr(config, "sso_audience", None) or env_cfg.audience,
            introspection_url=getattr(config, "sso_introspection_url", None)
            or env_cfg.introspection_url,
            introspection_client_id=env_cfg.introspection_client_id,
            introspection_client_secret=env_cfg.introspection_client_secret,
            required_scopes=list(env_cfg.required_scopes),
            role_mapping=dict(role_mapping),
            default_role=getattr(config, "sso_default_role", None) or env_cfg.default_role,
            jwks_cache_ttl=env_cfg.jwks_cache_ttl,
            clock_skew_tolerance=env_cfg.clock_skew_tolerance,
            http_timeout=env_cfg.http_timeout,
        )

    @property
    def enabled(self) -> bool:
        """SSO is enabled when a discovery URL or JWKS URI is configured."""
        return bool(self.discovery_url or self.jwks_uri or self.introspection_url)


@dataclass
class SsoClaims:
    """Extracted claims from a validated SSO token."""

    subject: str
    issuer: str
    audience: str | None = None
    expires_at: float | None = None
    issued_at: float | None = None
    scopes: list[str] = field(default_factory=list)
    role: str = "viewer"
    raw_claims: dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "sub": self.subject,
            "iss": self.issuer,
            "aud": self.audience,
            "exp": self.expires_at,
            "iat": self.issued_at,
            "scopes": self.scopes,
            "role": self.role,
        }


class SsoError(Exception):
    """Base SSO validation error."""

    pass


class SsoTokenExpiredError(SsoError):
    """Token has expired."""

    pass


class SsoTokenInvalidError(SsoError):
    """Token signature verification failed or token is malformed."""

    pass


class SsoTokenAudienceError(SsoError):
    """Token audience does not match expected audience."""

    pass


class SsoTokenScopeError(SsoError):
    """Token lacks required scopes."""

    pass


class SsoDiscoveryError(SsoError):
    """OIDC discovery or JWKS fetch failed."""

    pass


class _JwksCache:
    """Thread-safe JWKS cache with TTL."""

    def __init__(self, ttl: int = 3600):
        self._ttl = ttl
        self._keys: dict[str, Any] = {}
        self._fetched_at: float = 0.0
        self._lock = asyncio.Lock()

    @property
    def is_stale(self) -> bool:
        return time.time() - self._fetched_at > self._ttl

    async def get_or_fetch(
        self, jwks_uri: str, http_timeout: int = 10
    ) -> dict[str, Any]:
        if not self.is_stale and self._keys:
            return self._keys
        async with self._lock:
            # Double-check after acquiring lock
            if not self.is_stale and self._keys:
                return self._keys
            return await self._fetch(jwks_uri, http_timeout)

    async def _fetch(self, jwks_uri: str, http_timeout: int) -> dict[str, Any]:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=http_timeout) as client:
                resp = await client.get(jwks_uri)
                resp.raise_for_status()
                data = resp.json()
                self._keys = {k["kid"]: k for k in data.get("keys", [])}
                self._fetched_at = time.time()
                logger.info(
                    "JWKS fetched: %d keys from %s", len(self._keys), jwks_uri
                )
                return self._keys
        except Exception as e:
            logger.error("Failed to fetch JWKS from %s: %s", jwks_uri, e)
            # Return stale keys if available
            if self._keys:
                logger.warning("Using stale JWKS cache")
                return self._keys
            raise SsoDiscoveryError(f"JWKS fetch failed: {e}") from e


class SsoValidator:
    """Validates JWT tokens against an enterprise IdP."""

    def __init__(self, config: SsoConfig):
        self.config = config
        self._jwks_cache = _JwksCache(ttl=config.jwks_cache_ttl)
        self._discovery_cache: dict[str, str] | None = None
        self._discovery_fetched_at: float = 0.0

    async def validate_token(self, token: str) -> SsoClaims:
        """Validate a JWT token and return extracted claims.

        Args:
            token: Raw JWT string (without "Bearer " prefix).

        Returns:
            SsoClaims with validated claims.

        Raises:
            SsoTokenExpiredError: Token expired.
            SsoTokenInvalidError: Signature invalid or token malformed.
            SsoTokenAudienceError: Audience mismatch.
            SsoTokenScopeError: Missing required scopes.
            SsoDiscoveryError: Could not fetch JWKS or discovery document.
        """
        if not self.config.enabled:
            raise SsoError("SSO is not configured")

        # Try JWT validation first
        try:
            return await self._validate_jwt(token)
        except SsoTokenInvalidError:
            # Token might be opaque — try introspection
            if self.config.introspection_url:
                return await self._validate_introspection(token)
            raise

    async def _validate_jwt(self, token: str) -> SsoClaims:
        """Validate a JWT token using JWKS."""
        import base64

        # Split JWT into header, payload, signature
        parts = token.split(".")
        if len(parts) != 3:
            raise SsoTokenInvalidError("Invalid JWT format: expected 3 parts")

        try:
            header_b64 = parts[0]
            payload_b64 = parts[1]

            # Decode header
            header_padded = header_b64 + "=" * (4 - len(header_b64) % 4)
            header = json.loads(base64.urlsafe_b64decode(header_padded))

            # Decode payload
            payload_padded = payload_b64 + "=" * (4 - len(payload_b64) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_padded))

        except Exception as e:
            raise SsoTokenInvalidError(f"Failed to decode JWT: {e}") from e

        kid = header.get("kid")
        alg = header.get("alg", "")

        # Validate algorithm
        if alg not in ("RS256", "RS384", "RS512", "ES256", "ES384", "ES512", "PS256"):
            raise SsoTokenInvalidError(f"Unsupported JWT algorithm: {alg}")

        # Fetch JWKS and verify signature
        jwks_uri = await self._get_jwks_uri()
        keys = await self._jwks_cache.get_or_fetch(jwks_uri, self.config.http_timeout)

        if kid and kid not in keys:
            raise SsoTokenInvalidError(f"Key ID {kid} not found in JWKS")

        # For now, validate the key exists. Full cryptographic verification
        # requires PyJWT or python-jose. Log a warning.
        if kid:
            key = keys[kid]
            # Verify signature using the public key
            try:
                await self._verify_signature(token, key, alg)
            except Exception as e:
                logger.warning("JWT signature verification failed: %s", e)
                # In production, this should raise. For now, log and continue
                # so the system works even without full crypto deps.
                raise SsoTokenInvalidError(f"Signature verification failed: {e}") from e

        # Validate claims
        now = time.time()
        skew = self.config.clock_skew_tolerance

        # Expiry check
        exp = payload.get("exp")
        if exp and now > exp + skew:
            raise SsoTokenExpiredError(
                f"Token expired at {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(exp))}"
            )

        # Issuer check (timing-safe to prevent timing side-channels)
        if self.config.issuer:
            iss = payload.get("iss", "")
            if not hmac.compare_digest(iss, self.config.issuer):
                raise SsoTokenInvalidError(
                    f"Issuer mismatch: expected {self.config.issuer}, got {iss}"
                )

        # Audience check (timing-safe to prevent timing side-channels)
        if self.config.audience:
            aud = payload.get("aud")
            if isinstance(aud, list):
                if not any(hmac.compare_digest(self.config.audience, a) for a in aud):
                    raise SsoTokenAudienceError(
                        f"Expected audience {self.config.audience} not in {aud}"
                    )
            elif not hmac.compare_digest(str(aud or ""), self.config.audience):
                raise SsoTokenAudienceError(
                    f"Expected audience {self.config.audience}, got {aud}"
                )

        # Scope check
        scopes = self._extract_scopes(payload)
        if self.config.required_scopes:
            missing = set(self.config.required_scopes) - set(scopes)
            if missing:
                raise SsoTokenScopeError(f"Missing required scopes: {missing}")

        # Role mapping
        role = self._map_role(payload)

        return SsoClaims(
            subject=payload.get("sub", "unknown"),
            issuer=payload.get("iss", ""),
            audience=payload.get("aud"),
            expires_at=exp,
            issued_at=payload.get("iat"),
            scopes=scopes,
            role=role,
            raw_claims=payload,
        )

    async def _validate_introspection(self, token: str) -> SsoClaims:
        """Validate an opaque token via RFC 7662 introspection."""
        import httpx

        if not self.config.introspection_url:
            raise SsoError("No introspection endpoint configured")

        try:
            auth = None
            if self.config.introspection_client_id:
                auth = (self.config.introspection_client_id, self.config.introspection_client_secret or "")

            async with httpx.AsyncClient(timeout=self.config.http_timeout) as client:
                resp = await client.post(
                    self.config.introspection_url,
                    data={"token": token, "token_type_hint": "access_token"},
                    auth=auth,
                )
                resp.raise_for_status()
                data = resp.json()

            if not data.get("active"):
                raise SsoTokenInvalidError("Token is not active")

            # Map introspection response to SsoClaims
            scopes = data.get("scope", "").split() if data.get("scope") else []
            if self.config.required_scopes:
                missing = set(self.config.required_scopes) - set(scopes)
                if missing:
                    raise SsoTokenScopeError(f"Missing required scopes: {missing}")

            role = self._map_role(data)

            return SsoClaims(
                subject=data.get("sub", "unknown"),
                issuer=data.get("iss", ""),
                audience=data.get("aud"),
                expires_at=data.get("exp"),
                issued_at=data.get("iat"),
                scopes=scopes,
                role=role,
                raw_claims=data,
            )
        except SsoError:
            raise
        except Exception as e:
            raise SsoDiscoveryError(f"Token introspection failed: {e}") from e

    async def _verify_signature(self, token: str, key: dict, algorithm: str) -> None:
        """Verify JWT signature using PyJWT if available, else warn."""
        try:
            import jwt as pyjwt  # noqa: F811

            pyjwt.decode(
                token,
                key,
                algorithms=[algorithm],
                audience=self.config.audience,
                issuer=self.config.issuer,
                options={"verify_exp": False},  # We check expiry ourselves
            )
        except ImportError:
            logger.warning(
                "PyJWT not installed — JWT signature verification skipped. "
                "Install with: pip install PyJWT[crypto]"
            )
        except Exception as e:
            raise SsoTokenInvalidError(f"Signature verification failed: {e}") from e

    async def _get_jwks_uri(self) -> str:
        """Get JWKS URI, discovering from OIDC if needed."""
        if self.config.jwks_uri:
            return self.config.jwks_uri

        if not self.config.discovery_url:
            raise SsoDiscoveryError("No JWKS URI or discovery URL configured")

        return await self._discover_jwks_uri()

    async def _discover_jwks_uri(self) -> str:
        """Fetch OIDC discovery document and extract JWKS URI."""
        import httpx

        now = time.time()
        if self._discovery_cache and now - self._discovery_fetched_at < 3600:
            return self._discovery_cache["jwks_uri"]

        try:
            async with httpx.AsyncClient(timeout=self.config.http_timeout) as client:
                resp = await client.get(self.config.discovery_url)
                resp.raise_for_status()
                data = resp.json()

            self._discovery_cache = {
                "jwks_uri": data["jwks_uri"],
                "issuer": data.get("issuer", ""),
            }
            self._discovery_fetched_at = now

            if not self.config.issuer and data.get("issuer"):
                self.config.issuer = data["issuer"]

            logger.info("OIDC discovery: JWKS URI = %s", data["jwks_uri"])
            return data["jwks_uri"]
        except Exception as e:
            raise SsoDiscoveryError(f"OIDC discovery failed: {e}") from e

    def _extract_scopes(self, payload: dict) -> list[str]:
        """Extract scopes from JWT payload (handles multiple claim formats)."""
        # Standard scope claim
        if "scope" in payload:
            scope = payload["scope"]
            return scope.split() if isinstance(scope, str) else scope

        # OAuth2 scope as array
        if "scp" in payload:
            scp = payload["scp"]
            return scp if isinstance(scp, list) else [scp]

        # Resource access (Keycloak format)
        if "realm_access" in payload:
            return payload["realm_access"].get("roles", [])

        return []

    def _map_role(self, claims: dict) -> str:
        """Map claims to a Headroom role using the configured role mapping."""
        if not self.config.role_mapping:
            return self.config.default_role

        for claim_path, role in self.config.role_mapping.items():
            # Handle "claim_name:value=role" format
            if ":value=" in claim_path:
                claim_name, expected_value = claim_path.split(":value=", 1)
                claim_value = self._get_nested_claim(claims, claim_name)
                if claim_value == expected_value:
                    return role
            else:
                # Direct claim-to-role mapping
                claim_value = self._get_nested_claim(claims, claim_path)
                if claim_value:
                    if isinstance(claim_value, list):
                        # Check if any of the claim values match a known role
                        for v in claim_value:
                            if v in ("admin", "operator", "viewer"):
                                return v
                    elif isinstance(claim_value, str) and claim_value in (
                        "admin",
                        "operator",
                        "viewer",
                    ):
                        return claim_value

        return self.config.default_role

    def _get_nested_claim(self, claims: dict, path: str) -> Any:
        """Get a nested claim value using dot-separated path."""
        parts = path.split(".")
        current = claims
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current


# Module-level singleton
_validator: SsoValidator | None = None


def get_sso_validator() -> SsoValidator | None:
    """Get or create the global SSO validator."""
    global _validator  # noqa: PLW0603
    if _validator is None:
        config = SsoConfig.from_env()
        if config.enabled:
            _validator = SsoValidator(config)
            logger.info("SSO validator enabled (provider: %s)", config.provider_type)
    return _validator


def reset_sso_validator() -> None:
    """Reset the global SSO validator (for testing)."""
    global _validator  # noqa: PLW0603
    _validator = None
