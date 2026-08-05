# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""Central entitlement gate for every mounted enterprise route.

Audit-2026-08-03 C3.3: entitlement enforcement lived in per-route
``Depends(require_entitlement(...))`` decorators, and only ``admin.py`` used
them. The other seventeen route modules mounted their enterprise surfaces
with admin auth + RBAC but *no* tier check, so a builder-tier deployment got
HTTP 200 from ``/v1/airgap/status``, ``/v1/residency/proof``,
``/v1/rbac/assignments`` and ``/v1/spend/dashboard`` while their ``admin.py``
twins correctly answered 403.

The fix moves the decision out of the decorators:

* :data:`EE_ROUTE_ENTITLEMENTS` is an explicit path-prefix -> feature map.
* :func:`install_entitlement_gate` walks **every** route the app ended up
  with and attaches the gate itself. Nothing has to be remembered at the
  call site, so a capability cannot be exposed by forgetting a decorator.
* Any route contributed by an enterprise route module that the map does not
  cover is mounted **denied** (:data:`_UNMAPPED`), not open. Adding a new EE
  route without registering it fails closed.

The gate is appended to ``route.dependant.dependencies`` (rather than passed
to ``include_router``) so it runs *after* the route's own auth and RBAC
dependencies. Unauthenticated callers keep getting 401, not a tier error.

``cutctx/proxy/routes/memory.py`` and the EE memory service are deliberately
left ungated here — tenant scoping for those endpoints is owned elsewhere and
is being changed in parallel.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Depends, HTTPException, Request

logger = logging.getLogger("cutctx.proxy.routes.entitlement_gate")

#: Sentinel: the path belongs to an enterprise surface but has no registered
#: feature. Fail closed.
class _UnmappedFeature:
    pass


_UNMAPPED = _UnmappedFeature()

#: Path prefix -> required feature name from ``cutctx.entitlements.FEATURE_TIERS``.
#: ``None`` means "deliberately reachable at every tier" and must carry a
#: reason. Longest matching prefix wins.
EE_ROUTE_ENTITLEMENTS: dict[str, str | None] = {
    # ── Enterprise capabilities ──────────────────────────────────────
    "/v1/airgap": "air_gap",
    "/v1/residency": "compliance",
    "/v1/dsr": "compliance",
    "/v1/rbac": "rbac",
    "/v1/audit": "audit_logs",
    "/v1/sso": "sso_saml",
    "/v1/scim": "scim",
    "/v1/fleet": "fleet_management",
    # ── Business capabilities ────────────────────────────────────────
    "/v1/rate_limit": "rate_limiting",
    # ── Team capabilities ────────────────────────────────────────────
    "/v1/spend": "usage_reports",
    "/v1/policies": "policy_presets",
    # ── Deliberately ungated ─────────────────────────────────────────
    #: Licence activation/validation must work before any tier exists.
    "/v1/license": None,
    #: Billing webhook; authenticated by the Stripe signature, not by tier.
    "/webhooks/stripe": None,
    #: Admin MFA hardens the admin credential itself — locking it behind a
    #: paid tier would lock operators out of their own proxy.
    "/v1/admin/mfa": None,
    #: Local secret store for provider credentials; core proxy plumbing.
    "/v1/secrets": None,
    #: Provider health/failover controls, available at every tier alongside
    #: multi-provider support.
    "/v1/providers": None,
    #: Deterministic orchestration is Apache-2.0: it lives in ``cutctx/``, not
    #: ``cutctx_ee/`` (LICENSING.md §A), has no ``FEATURE_TIERS`` entry, and its
    #: ``orchestrator`` config flag is ungated in ``admin.py``'s
    #: ``_FLAG_ENTITLEMENTS``. Gating it would be a licensing misclassification,
    #: not a revenue fix. Flip to a feature name if product decides otherwise.
    "/v1/orchestration": None,
    #: Owned by the memory/tenant-scoping work — not gated from here.
    "/v1/memory": None,
}

#: Route modules whose endpoints are enterprise surfaces subject to the
#: default-deny rule above. Anything else (core proxy, provider routes) is
#: untouched by the gate.
_EE_MODULE_PREFIXES = ("cutctx.proxy.routes.", "cutctx_ee.")

#: ``admin.py`` already carries explicit ``require_entitlement`` dependencies
#: on every paid route and also serves unprefixed builder-tier endpoints
#: (``/metrics``, ``/status``, ``/entitlements``), so it opts out of the
#: default-deny sweep. ``memory.py`` is owned by the tenant-scoping work.
_SELF_GATED_MODULES = frozenset(
    {
        "cutctx.proxy.routes.admin",
        "cutctx.proxy.routes.memory",
        "cutctx.proxy.routes.entitlement_gate",
    }
)


def resolve_required_feature(
    path: str, endpoint_module: str
) -> str | None | _UnmappedFeature:
    """Return the feature a path needs, ``None`` if open, ``_UNMAPPED`` if denied.

    Routes outside an enterprise route module return ``None`` (not gated).
    """
    match: str | None = None
    for prefix in EE_ROUTE_ENTITLEMENTS:
        if (path == prefix or path.startswith(prefix + "/")) and (
            match is None or len(prefix) > len(match)
        ):
            match = prefix
    if match is not None:
        return EE_ROUTE_ENTITLEMENTS[match]

    if endpoint_module in _SELF_GATED_MODULES:
        return None
    if endpoint_module.startswith(_EE_MODULE_PREFIXES):
        return _UNMAPPED
    return None


def make_entitlement_gate(
    proxy: Any, feature: str | _UnmappedFeature
) -> Callable[[Request], Awaitable[None]]:
    """Build the dependency that enforces ``feature`` for one route."""

    async def _gate(request: Request) -> None:  # noqa: ARG001
        if isinstance(feature, _UnmappedFeature):
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "feature_not_registered",
                    "message": (
                        "This enterprise endpoint has no entry in "
                        "EE_ROUTE_ENTITLEMENTS, so it is denied by default. "
                        "Register it in cutctx/proxy/routes/entitlement_gate.py."
                    ),
                },
            )
        checker = getattr(proxy, "entitlement_checker", None)
        if checker is None or checker.is_entitled(feature):
            return
        feature_tiers = getattr(checker, "feature_tiers", None) or {}
        if not feature_tiers:
            try:
                from cutctx.entitlements import FEATURE_TIERS

                feature_tiers = FEATURE_TIERS
            except ImportError:
                feature_tiers = {}
        required = feature_tiers.get(feature)
        raise HTTPException(
            status_code=403,
            detail={
                "error": "feature_not_available",
                "feature": feature,
                "required_tier": required.name.lower() if required else "unknown",
                "current_tier": getattr(checker, "plan_name", "builder"),
            },
        )

    _gate._cutctx_entitlement_gate = True  # type: ignore[attr-defined]
    return _gate


def install_entitlement_gate(app: Any, proxy: Any) -> int:
    """Attach the entitlement gate to every enterprise route on ``app``.

    Returns the number of routes gated. Called once from ``create_app`` after
    all routers are mounted, so route modules cannot opt out by omission.
    """
    from fastapi.dependencies.utils import get_parameterless_sub_dependant
    from fastapi.routing import APIRoute, request_response

    gated = 0
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        endpoint_module = getattr(route.endpoint, "__module__", "")
        feature = resolve_required_feature(route.path, endpoint_module)
        if feature is None:
            continue
        if any(
            getattr(dependency.call, "_cutctx_entitlement_gate", False)
            for dependency in route.dependant.dependencies
        ):
            continue
        dependency = Depends(make_entitlement_gate(proxy, feature))
        route.dependencies.append(dependency)
        # Appended last so admin auth / RBAC still answer first (401 before 403).
        route.dependant.dependencies.append(
            get_parameterless_sub_dependant(depends=dependency, path=route.path_format)
        )
        # APIRoute builds its ASGI request handler during construction. Updating
        # ``route.dependant`` alone only changes introspection; the already-built
        # handler keeps the old dependency graph and silently bypasses the gate.
        route.app = request_response(route.get_route_handler())
        gated += 1
        if feature is _UNMAPPED:
            logger.warning(
                "Route %s (%s) is an enterprise surface with no entitlement mapping — "
                "denying by default.",
                route.path,
                endpoint_module,
            )
    logger.info("Entitlement gate installed on %d route(s).", gated)
    return gated


__all__ = [
    "EE_ROUTE_ENTITLEMENTS",
    "install_entitlement_gate",
    "resolve_required_feature",
]
