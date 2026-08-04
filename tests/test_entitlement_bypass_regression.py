# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""Regression tests for the Audit-2026-08-03 enterprise-licensing bypasses.

Every test here fails on the pre-fix tree:

C3.1  ``CUTCTX_LICENSE_API_URL`` pointed at an attacker-controlled server
      returning ``{"valid": true, "tier": "enterprise"}`` granted all 15
      ENTERPRISE features. The response was unsigned and the endpoint unpinned.
C3.2  A hand-written unsigned ``~/.cutctx/license_cache.json`` granted
      enterprise; a future-dated ``validated_at`` made the 7-day grace period
      never expire; a forged ``status: "trial"`` was accepted like ``active``.
C3.3  Seventeen of eighteen route modules had no entitlement check.
H1/H2 Stale ``.so`` artifacts shipped superseded code, and the integrity guard
      logged instead of aborting.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("cutctx_ee")

import httpx
from fastapi import APIRouter
from fastapi.testclient import TestClient

from cutctx.proxy.server import ProxyConfig, _load_entitlement_checker, create_app
from cutctx.telemetry.reporter import LicenseInfo, UsageReporter
from cutctx_ee.billing.license_token import (
    LicenseSignatureError,
    authoritative_tier,
    sign_license,
    verify_hmac_license_key,
    verify_license_token,
)

_PINNED_API = "https://udeekuvifncmqvoywhlg.supabase.co/functions/v1"
_ATTACKER_API = "http://127.0.0.1:9/evil"
_ADMIN_KEY = "test-entitlement-regression-key"


def _keypair() -> tuple[str, str, str]:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519

    private = ed25519.Ed25519PrivateKey.generate()
    priv_hex = private.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    ).hex()
    pub_hex = (
        private.public_key()
        .public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        .hex()
    )
    return "regression-kid", priv_hex, pub_hex


def _validate_with(api_url: str, body: dict, tmp_path: Path) -> LicenseInfo:
    """Run one ``validate_license`` round-trip against a canned response."""

    async def scenario() -> LicenseInfo:
        reporter = UsageReporter(
            license_key="I-NEVER-PAID-FOR-THIS",
            cloud_url=api_url,
            license_api_url=api_url,
            cache_path=tmp_path / "license_cache.json",
        )
        reporter._http_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _r: httpx.Response(200, json=body))
        )
        try:
            return await reporter.validate_license()
        finally:
            await reporter._http_client.aclose()

    return asyncio.run(scenario())


# ── C3.1 — licence endpoint is env-redirectable and unsigned ────────────


def test_redirected_license_api_cannot_grant_enterprise(tmp_path, monkeypatch) -> None:
    """VERIFY 1: a fake server claiming enterprise must not grant enterprise."""
    monkeypatch.setenv("CUTCTX_LICENSE_API_URL", _ATTACKER_API)
    info = _validate_with(_ATTACKER_API, {"valid": True, "tier": "enterprise"}, tmp_path)

    assert info.plan is None, "unsigned response from an unpinned origin granted a paid tier"
    checker = _load_entitlement_checker(info.plan)
    assert checker.plan_name == "builder"
    for feature in ("rbac", "sso_saml", "audit_logs", "air_gap", "scim"):
        assert checker.is_entitled(feature) is False


def test_wrongly_signed_response_is_not_authoritative(tmp_path, monkeypatch) -> None:
    """A token signed by a key that is not in the trust store proves nothing."""
    _, rogue_priv, _ = _keypair()
    _, _, honest_pub = _keypair()
    monkeypatch.setenv("CUTCTX_LICENSE_PUBLIC_KEYS", f"regression-kid={honest_pub}")
    forged = sign_license("enterprise", "regression-kid", rogue_priv)

    info = _validate_with(
        _ATTACKER_API,
        {"valid": True, "tier": "enterprise", "license_token": forged},
        tmp_path,
    )
    assert info.plan is None


def test_signed_response_from_unpinned_origin_is_honoured(tmp_path, monkeypatch) -> None:
    """Air-gapped/self-hosted deployments keep working — with a signature."""
    kid, priv, pub = _keypair()
    monkeypatch.setenv("CUTCTX_LICENSE_PUBLIC_KEYS", f"{kid}={pub}")
    token = sign_license("enterprise", kid, priv)

    info = _validate_with(
        "https://licenses.internal.example/fn",
        {"valid": True, "tier": "enterprise", "license_token": token},
        tmp_path,
    )
    assert info.plan == "enterprise"


def test_pinned_vendor_origin_still_authoritative(tmp_path, monkeypatch) -> None:
    """Regression guard: real hosted keys must not be downgraded."""
    monkeypatch.delenv("CUTCTX_LICENSE_PUBLIC_KEYS", raising=False)
    info = _validate_with(_PINNED_API, {"valid": True, "tier": "business"}, tmp_path)
    assert info.plan == "business"


def test_response_can_downgrade_but_never_upgrade_a_signed_tier(monkeypatch) -> None:
    kid, priv, pub = _keypair()
    monkeypatch.setenv("CUTCTX_LICENSE_PUBLIC_KEYS", f"{kid}={pub}")
    token = sign_license("team", kid, priv)

    assert authoritative_tier("enterprise", None, _ATTACKER_API, {"license_token": token}) == "team"
    assert authoritative_tier("team", None, _ATTACKER_API, {"license_token": token}) == "team"


def test_hmac_license_key_from_cli_generate_is_verified(monkeypatch) -> None:
    """`cutctx license generate` mints ent-* keys; they are now verified."""
    secret = "regression-hmac-secret"
    monkeypatch.setenv("CUTCTX_LICENSE_HMAC_SECRET", secret)
    payload = (
        base64.urlsafe_b64encode(
            json.dumps({"org": "acme", "seats": 5}, separators=(",", ":")).encode()
        )
        .rstrip(b"=")
        .decode()
    )
    unsigned = f"ent-{payload}"
    sig = hmac.new(secret.encode(), unsigned.encode(), hashlib.sha256).hexdigest()

    assert verify_hmac_license_key(f"{unsigned}.{sig}")["tier"] == "enterprise"
    with pytest.raises(LicenseSignatureError):
        verify_hmac_license_key(f"{unsigned}.{'0' * 64}")
    assert authoritative_tier("enterprise", f"{unsigned}.{sig}", _ATTACKER_API) == "enterprise"
    assert authoritative_tier("enterprise", f"{unsigned}.{'0' * 64}", _ATTACKER_API) is None


def test_expired_hrk1_token_is_rejected(monkeypatch) -> None:
    kid, priv, pub = _keypair()
    monkeypatch.setenv("CUTCTX_LICENSE_PUBLIC_KEYS", f"{kid}={pub}")
    expired = sign_license("enterprise", kid, priv, duration_days=0)
    # duration_days=0 puts exp at "now"; step past the skew window.
    with pytest.raises(LicenseSignatureError):
        verify_license_token(expired, now=time.time() + 3600)


# ── C3.2 — licence cache is forgeable ───────────────────────────────────


def _reporter(tmp_path: Path) -> UsageReporter:
    return UsageReporter(
        license_key="I-NEVER-PAID-FOR-THIS",
        cloud_url=_PINNED_API,
        license_api_url=_PINNED_API,
        cache_path=tmp_path / "license_cache.json",
    )


def test_forged_unsigned_cache_does_not_grant_enterprise(tmp_path) -> None:
    """VERIFY 2: a hand-written plain-JSON cache must not grant enterprise."""
    cache = tmp_path / "license_cache.json"
    cache.write_text(
        json.dumps(
            {
                "status": "active",
                "plan": "enterprise",
                "validated_at": datetime.now(timezone.utc).isoformat(),
            }
        ),
        encoding="utf-8",
    )

    info = _reporter(tmp_path)._load_cache_or_default()
    assert info.status == "expired"
    assert info.plan is None
    assert _load_entitlement_checker(info.plan).is_entitled("rbac") is False


def test_forged_signed_envelope_with_wrong_signature_rejected(tmp_path) -> None:
    cache = tmp_path / "license_cache.json"
    cache.write_text(
        json.dumps(
            {
                "payload": {
                    "status": "active",
                    "plan": "enterprise",
                    "validated_at": datetime.now(timezone.utc).isoformat(),
                },
                "signature": "0" * 64,
            }
        ),
        encoding="utf-8",
    )
    info = _reporter(tmp_path)._load_cache_or_default()
    assert info.status == "expired"
    assert info.plan is None


def test_future_dated_validated_at_does_not_extend_grace(tmp_path) -> None:
    """A cache stamped in the future used to have a negative age → eternal grace."""
    from cutctx.security.state_crypto import write_hmac_json

    cache = tmp_path / "license_cache.json"
    write_hmac_json(
        cache,
        {
            "status": "active",
            "plan": "enterprise",
            "validated_at": (datetime.now(timezone.utc) + timedelta(days=3650)).isoformat(),
        },
    )
    info = _reporter(tmp_path)._load_cache_or_default()
    assert info.status == "expired"


def test_forged_trial_status_requires_a_future_expiry(tmp_path) -> None:
    """`status: "trial"` was accepted identically to `active`, with no expiry."""
    from cutctx.security.state_crypto import write_hmac_json

    cache = tmp_path / "license_cache.json"
    write_hmac_json(
        cache,
        {
            "status": "trial",
            "plan": "enterprise",
            "validated_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    info = _reporter(tmp_path)._load_cache_or_default()
    assert info.status == "expired"
    assert info.plan is None


def test_reporter_writes_a_signed_cache(tmp_path) -> None:
    from cutctx.security.state_crypto import read_hmac_json

    reporter = _reporter(tmp_path)
    reporter._license_info = LicenseInfo(status="active", plan="business")
    reporter._save_cache()

    raw = json.loads((tmp_path / "license_cache.json").read_text())
    assert "payload" in raw and len(raw["signature"]) == 64
    assert read_hmac_json(tmp_path / "license_cache.json")["plan"] == "business"


# ── C3.3 — route modules had no entitlement checks ──────────────────────


@pytest.fixture
def builder_app(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CUTCTX_ADMIN_API_KEY", _ADMIN_KEY)
    return create_app(
        ProxyConfig(cache_enabled=False, rate_limit_enabled=False, log_requests=False)
    )


def _auth() -> dict[str, str]:
    return {"authorization": f"Bearer {_ADMIN_KEY}"}


@pytest.mark.parametrize(
    "path",
    [
        "/v1/airgap/status",
        "/v1/airgap/policy",
        "/v1/residency/proof",
        "/v1/rbac/assignments",
        "/v1/spend/dashboard",
    ],
)
def test_builder_tier_denied_on_enterprise_routes(builder_app, path: str) -> None:
    """VERIFY 3: these must be 403 at builder tier, matching their admin.py twins."""
    assert builder_app.state.proxy.entitlement_checker.plan_name == "builder"
    response = TestClient(builder_app).get(path, headers=_auth())
    assert response.status_code == 403, f"{path}: {response.status_code} {response.text}"


@pytest.mark.parametrize("path", ["/v1/airgap/status", "/v1/rbac/assignments"])
def test_gate_runs_after_auth_so_anonymous_callers_still_get_401(builder_app, path: str) -> None:
    assert TestClient(builder_app).get(path).status_code == 401


def test_new_ee_route_without_a_mapping_fails_closed(monkeypatch) -> None:
    """VERIFY 4: an unmapped enterprise route is denied, not exposed."""
    from cutctx.proxy.routes.entitlement_gate import install_entitlement_gate

    monkeypatch.setenv("CUTCTX_ADMIN_API_KEY", _ADMIN_KEY)
    app = create_app(ProxyConfig(cache_enabled=False, rate_limit_enabled=False, log_requests=False))

    router = APIRouter(prefix="/v1/brand-new-ee-surface")

    async def _handler() -> dict[str, str]:
        return {"secret": "enterprise data"}

    # Pretend the endpoint was contributed by a new route module.
    _handler.__module__ = "cutctx.proxy.routes.brand_new"
    router.add_api_route("/data", _handler, methods=["GET"])
    app.include_router(router)
    # create_app ends with a provider catch-all, so move the new route ahead of
    # it the way a real router registered inside create_app would be.
    app.router.routes.insert(0, app.router.routes.pop())
    install_entitlement_gate(app, app.state.proxy)

    response = TestClient(app).get("/v1/brand-new-ee-surface/data", headers=_auth())
    assert response.status_code == 403
    assert "feature_not_registered" in response.text


def test_every_mounted_enterprise_route_is_gated(builder_app) -> None:
    """No enterprise route may reach its handler ungated at builder tier."""
    from fastapi.routing import APIRoute

    from cutctx.proxy.routes.entitlement_gate import (
        _SELF_GATED_MODULES,
        EE_ROUTE_ENTITLEMENTS,
        resolve_required_feature,
    )

    ungated: list[str] = []
    for route in builder_app.routes:
        if not isinstance(route, APIRoute):
            continue
        module = getattr(route.endpoint, "__module__", "")
        if not module.startswith(("cutctx.proxy.routes.", "cutctx_ee.")):
            continue
        if module in _SELF_GATED_MODULES:
            continue
        if resolve_required_feature(route.path, module) is None:
            # Deliberately open — must be an explicit entry, not an omission.
            assert any(
                route.path == prefix or route.path.startswith(prefix + "/")
                for prefix, feature in EE_ROUTE_ENTITLEMENTS.items()
                if feature is None
            ), f"{route.path} ({module}) is ungated by omission"
        elif not any(
            getattr(d.call, "__name__", "") == "_gate" for d in route.dependant.dependencies
        ):
            ungated.append(f"{route.path} ({module})")
    assert not ungated, f"enterprise routes reachable without an entitlement gate: {ungated}"


def test_memory_routes_are_left_alone() -> None:
    """Tenant scoping for /v1/memory is owned elsewhere; the gate must not touch it."""
    from cutctx.proxy.routes.entitlement_gate import (
        EE_ROUTE_ENTITLEMENTS,
        resolve_required_feature,
    )

    assert EE_ROUTE_ENTITLEMENTS["/v1/memory"] is None
    assert resolve_required_feature("/v1/memory/search", "cutctx_ee.memory_service.api") is None


# ── H1 / H2 — stale binaries and the non-enforcing integrity guard ──────


def test_freshness_check_flags_a_stale_extension(tmp_path) -> None:
    """H1: a .py newer than its .so must be reported."""
    from scripts.check_ee_freshness import find_stale

    (tmp_path / "mod.py").write_text("x = 1\n")
    artifact = tmp_path / "mod.cpython-312-darwin.so"
    artifact.write_bytes(b"\x00")
    import os

    old = time.time() - 3600
    os.utime(artifact, (old, old))

    stale, compiled = find_stale(tmp_path)
    assert compiled == 1
    assert [p.name for p, _, _ in stale] == ["mod.py"]

    os.utime(artifact, None)
    assert find_stale(tmp_path)[0] == []


def test_tampered_extension_aborts_instead_of_logging(tmp_path, monkeypatch) -> None:
    """H2: verify_ee_manifest(strict=True) raises; it used to log and return."""
    from cutctx.security import integrity

    ee_dir = tmp_path / "cutctx_ee"
    ee_dir.mkdir()
    artifact = ee_dir / "widget.cpython-312-darwin.so"
    artifact.write_bytes(b"honest bytes")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    (ee_dir / "MANIFEST.sha256.json").write_text(
        json.dumps({"version": "1", "algorithm": "sha256", "files": {artifact.name: digest}})
    )
    monkeypatch.setattr(integrity, "_ee_dir", lambda: ee_dir)
    monkeypatch.delenv("CUTCTX_SKIP_INTEGRITY_CHECK", raising=False)
    monkeypatch.delenv("CUTCTX_LICENSE_HMAC_SECRET", raising=False)

    integrity.verify_ee_manifest(strict=True)  # clean tree: no raise

    artifact.write_bytes(artifact.read_bytes() + b"\x00")
    with pytest.raises(integrity.IntegrityError, match="Refusing to load EE modules"):
        integrity.verify_ee_manifest(strict=True)


def test_ee_entry_guard_runs_the_integrity_check_in_strict_mode(monkeypatch) -> None:
    """H2: cutctx_ee.__init__ must ask for enforcement, not warnings."""
    import cutctx.security.integrity as integrity
    import cutctx_ee

    seen: dict[str, object] = {}
    monkeypatch.setattr(
        integrity, "verify_ee_manifest", lambda strict=True: seen.update(strict=strict)
    )
    cutctx_ee._run_security_guards()
    assert seen == {"strict": True}
