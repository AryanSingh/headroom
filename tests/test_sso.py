"""Tests for SSO/OAuth2/OIDC middleware."""

from __future__ import annotations

import base64
import json
import os
import time
import unittest
from unittest.mock import patch

from cutctx.sso import (
    SsoClaims,
    SsoConfig,
    SsoDiscoveryError,
    SsoError,
    SsoTokenAudienceError,
    SsoTokenExpiredError,
    SsoTokenInvalidError,
    SsoTokenScopeError,
    SsoValidator,
    _JwksCache,
)


def _make_jwt(header: dict, payload: dict) -> str:
    """Create a JWT-like token from header and payload dicts."""
    h = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=").decode()
    p = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    s = base64.urlsafe_b64encode(b"fake-sig").rstrip(b"=").decode()
    return f"{h}.{p}.{s}"


class TestSsoConfig(unittest.TestCase):
    def test_defaults(self):
        cfg = SsoConfig()
        self.assertEqual(cfg.provider_type, "oidc")
        self.assertIsNone(cfg.discovery_url)
        self.assertFalse(cfg.enabled)

    def test_enabled_with_discovery_url(self):
        cfg = SsoConfig(discovery_url="https://idp.example.com/.well-known/openid-configuration")
        self.assertTrue(cfg.enabled)

    def test_enabled_with_jwks_uri(self):
        cfg = SsoConfig(jwks_uri="https://idp.example.com/.well-known/jwks.json")
        self.assertTrue(cfg.enabled)

    def test_enabled_with_introspection_url(self):
        cfg = SsoConfig(introspection_url="https://idp.example.com/introspect")
        self.assertTrue(cfg.enabled)

    def test_disabled_when_no_urls(self):
        cfg = SsoConfig()
        self.assertFalse(cfg.enabled)

    @patch.dict(
        os.environ,
        {
            "CUTCTX_SSO_PROVIDER_TYPE": "jwt",
            "CUTCTX_SSO_DISCOVERY_URL": "https://idp.example.com/.well-known/openid-configuration",
            "CUTCTX_SSO_ISSUER": "https://idp.example.com",
            "CUTCTX_SSO_AUDIENCE": "cutctx-api",
            "CUTCTX_SSO_ROLE_MAPPING": "groups=admin,roles=operator",
            "CUTCTX_SSO_REQUIRED_SCOPES": "openid,profile",
            "CUTCTX_SSO_DEFAULT_ROLE": "viewer",
            "CUTCTX_SSO_JWKS_CACHE_TTL": "7200",
            "CUTCTX_SSO_CLOCK_SKEW_TOLERANCE": "30",
            "CUTCTX_SSO_HTTP_TIMEOUT": "15",
        },
    )
    def test_from_env(self):
        cfg = SsoConfig.from_env()
        self.assertEqual(cfg.provider_type, "jwt")
        self.assertEqual(
            cfg.discovery_url, "https://idp.example.com/.well-known/openid-configuration"
        )
        self.assertEqual(cfg.issuer, "https://idp.example.com")
        self.assertEqual(cfg.audience, "cutctx-api")
        self.assertEqual(cfg.role_mapping, {"groups": "admin", "roles": "operator"})
        self.assertEqual(cfg.required_scopes, ["openid", "profile"])
        self.assertEqual(cfg.jwks_cache_ttl, 7200)
        self.assertEqual(cfg.clock_skew_tolerance, 30)
        self.assertEqual(cfg.http_timeout, 15)

    @patch.dict(os.environ, {}, clear=True)
    def test_from_env_defaults(self):
        cfg = SsoConfig.from_env()
        self.assertEqual(cfg.provider_type, "oidc")
        self.assertIsNone(cfg.discovery_url)
        self.assertEqual(cfg.required_scopes, [])


class TestSsoClaims(unittest.TestCase):
    def test_to_dict(self):
        claims = SsoClaims(
            subject="user-123",
            issuer="https://idp.example.com",
            audience="cutctx-api",
            expires_at=9999999999.0,
            issued_at=1000000000.0,
            scopes=["openid", "profile"],
            role="admin",
        )
        d = claims.to_dict()
        self.assertEqual(d["sub"], "user-123")
        self.assertEqual(d["role"], "admin")

    def test_is_expired(self):
        claims = SsoClaims(subject="u", issuer="i", expires_at=time.time() - 100)
        self.assertTrue(claims.is_expired)

    def test_not_expired(self):
        claims = SsoClaims(subject="u", issuer="i", expires_at=time.time() + 3600)
        self.assertFalse(claims.is_expired)

    def test_no_expiry(self):
        claims = SsoClaims(subject="u", issuer="i", expires_at=None)
        self.assertFalse(claims.is_expired)

    def test_default_role(self):
        claims = SsoClaims(subject="u", issuer="i")
        self.assertEqual(claims.role, "viewer")


class TestJwksCache(unittest.TestCase):
    def test_initially_stale(self):
        cache = _JwksCache(ttl=3600)
        self.assertTrue(cache.is_stale)

    def test_not_stale_after_fetch(self):
        cache = _JwksCache(ttl=3600)
        cache._keys = {"kid1": {"kty": "RSA"}}
        cache._fetched_at = time.time()
        self.assertFalse(cache.is_stale)

    def test_stale_after_ttl(self):
        cache = _JwksCache(ttl=1)
        cache._keys = {"kid1": {"kty": "RSA"}}
        cache._fetched_at = time.time() - 2
        self.assertTrue(cache.is_stale)


class TestSsoValidator(unittest.TestCase):
    def _make_validator(self, **cfg_kwargs) -> SsoValidator:
        cfg = SsoConfig(jwks_uri="https://example.com/jwks", **cfg_kwargs)
        validator = SsoValidator(cfg)
        # Pre-populate JWKS cache so we don't make HTTP calls
        validator._jwks_cache._keys = {"key1": {"kty": "RSA"}}
        validator._jwks_cache._fetched_at = time.time()

        # Skip real signature verification (stub keys have no key material)
        async def _no_sig_verify(token, key, algorithm):
            import base64
            import json
            import time
            from cutctx_ee.sso import SsoTokenExpiredError

            parts = token.split(".")
            if len(parts) == 3:
                payload_json = base64.urlsafe_b64decode(parts[1] + "===").decode()
                payload = json.loads(payload_json)
                exp = payload.get("exp")
                if exp and time.time() > exp:
                    raise SsoTokenExpiredError("Token expired")

        validator._verify_signature = _no_sig_verify
        return validator

    def test_not_configured_raises(self):
        cfg = SsoConfig()  # enabled=False
        validator = SsoValidator(cfg)
        with self.assertRaises(SsoError):
            import asyncio

            asyncio.run(validator.validate_token("anything"))

    def test_invalid_jwt_format(self):
        validator = self._make_validator()
        with self.assertRaises(SsoTokenInvalidError):
            import asyncio

            asyncio.run(validator.validate_token("not-a-jwt"))

    def test_too_few_jwt_parts(self):
        validator = self._make_validator()
        with self.assertRaises(SsoTokenInvalidError):
            import asyncio

            asyncio.run(validator.validate_token("only.two"))

    def test_unsupported_algorithm(self):
        validator = self._make_validator()
        token = _make_jwt({"alg": "HS256", "typ": "JWT"}, {"sub": "user"})
        with self.assertRaises(SsoTokenInvalidError):
            import asyncio

            asyncio.run(validator.validate_token(token))

    def test_expired_token(self):
        validator = self._make_validator(issuer="https://idp.example.com")
        token = _make_jwt(
            {"alg": "RS256", "typ": "JWT", "kid": "key1"},
            {"sub": "user", "iss": "https://idp.example.com", "exp": int(time.time()) - 3600},
        )
        with self.assertRaises(SsoTokenExpiredError):
            import asyncio

            asyncio.run(validator.validate_token(token))

    def test_issuer_mismatch(self):
        validator = self._make_validator(issuer="https://expected-issuer.com")
        token = _make_jwt(
            {"alg": "RS256", "typ": "JWT", "kid": "key1"},
            {"sub": "user", "iss": "https://wrong-issuer.com", "exp": int(time.time()) + 3600},
        )
        with self.assertRaises(SsoTokenInvalidError):
            import asyncio

            asyncio.run(validator.validate_token(token))

    def test_audience_mismatch(self):
        validator = self._make_validator(audience="expected-api")
        token = _make_jwt(
            {"alg": "RS256", "typ": "JWT", "kid": "key1"},
            {"sub": "user", "aud": "wrong-api", "exp": int(time.time()) + 3600},
        )
        with self.assertRaises(SsoTokenAudienceError):
            import asyncio

            asyncio.run(validator.validate_token(token))

    def test_missing_kid_in_jwks(self):
        validator = self._make_validator()
        token = _make_jwt(
            {"alg": "RS256", "typ": "JWT", "kid": "nonexistent-key"},
            {"sub": "user", "exp": int(time.time()) + 3600},
        )
        with self.assertRaises(SsoTokenInvalidError):
            import asyncio

            asyncio.run(validator.validate_token(token))

    def test_audience_list_match(self):
        validator = self._make_validator(audience="expected-api")
        token = _make_jwt(
            {"alg": "RS256", "typ": "JWT", "kid": "key1"},
            {"sub": "user", "aud": ["expected-api", "other-api"], "exp": int(time.time()) + 3600},
        )
        import asyncio

        claims = asyncio.run(validator.validate_token(token))
        self.assertEqual(claims.subject, "user")

    def test_scope_check(self):
        validator = self._make_validator(required_scopes=["admin", "write"])
        token = _make_jwt(
            {"alg": "RS256", "typ": "JWT", "kid": "key1"},
            {"sub": "user", "scope": "openid read", "exp": int(time.time()) + 3600},
        )
        with self.assertRaises(SsoTokenScopeError):
            import asyncio

            asyncio.run(validator.validate_token(token))


class TestSsoErrors(unittest.TestCase):
    def test_hierarchy(self):
        self.assertTrue(issubclass(SsoTokenExpiredError, SsoError))
        self.assertTrue(issubclass(SsoTokenInvalidError, SsoError))
        self.assertTrue(issubclass(SsoTokenAudienceError, SsoError))
        self.assertTrue(issubclass(SsoTokenScopeError, SsoError))
        self.assertTrue(issubclass(SsoDiscoveryError, SsoError))

    def test_can_catch_all_as_sso_error(self):
        for exc_cls in [SsoTokenExpiredError, SsoTokenInvalidError, SsoDiscoveryError]:
            with self.assertRaises(SsoError):
                raise exc_cls("test")


if __name__ == "__main__":
    unittest.main()
