"""Enterprise admin route module.

Extracts ~50 admin/management routes from the server.py monolith into
a standalone module.  ``create_admin_router`` returns a populated
``APIRouter`` that ``server.py`` mounts via ``app.include_router()``.
"""

from __future__ import annotations

import csv
import io
import json
import logging
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse

logger = logging.getLogger("cutctx.proxy.routes.admin")


# ── Helpers ──────────────────────────────────────────────────────────────


def _iso_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _resolve_audit_actor(request: Request) -> str:
    """Resolve the audit ``actor`` field for a request.

    Medium-33 (production-audit-progress-2026-06-20.md) and
    Audit-Deep-2026-06-21 Blocker 6: the previous code took the actor
    from a client-controllable ``X-Cutctx-User-Id`` header when no
    SSO state was set, which let a caller with a valid admin key
    forge audit attribution. The hierarchy is now:

      1. SSO-resolved subject (``request.state.cutctx_user_id``,
         set by the SSO validator). The only trusted source.
      2. Admin-key fingerprint (first 8 hex chars of the API key
         SHA-256, prefixed ``key:``). A stable, non-secret
         identifier for the key holder.
      3. ``"admin"`` — only when neither is available (should
         never happen since both auth methods gate this path).

    This helper is shared with ``server.py`` (e.g. ``/stats/reset``
    audit event) so all admin paths use the same actor resolution.
    """
    sso_user = getattr(request.state, "cutctx_user_id", None)
    if sso_user:
        return f"sso:{sso_user}"

    auth_header = request.headers.get("authorization", "")
    admin_header = request.headers.get("x-cutctx-admin-key", "")
    token = ""
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif admin_header:
        token = admin_header
    if token:
        import hashlib as _h

        fp = _h.sha256(token.encode("utf-8")).hexdigest()[:8]
        return f"key:{fp}"

    return "admin"


async def _audit_admin_action(
    proxy: Any,
    request: Request,
    *,
    action: str,
    detail: dict[str, Any],
    org_id: str | None = None,
    workspace_id: str | None = None,
    project_id: str | None = None,
    success: bool = True,
) -> None:
    if not proxy.audit_logger:
        return
    try:
        from cutctx.audit import AuditEvent

        # Medium-33 (production-audit-progress-2026-06-20.md) and
        # Audit-Deep-2026-06-21 Blocker 6: resolve actor via the shared
        # helper so all admin paths (including /stats/reset in
        # server.py) use the same hierarchy.
        # The previous code took the actor from a client-controllable
        # X-Cutctx-User-Id header when no SSO state was set,
        # which let a caller with a valid admin key forge audit
        # attribution. The new hierarchy is:
        #   1. SSO-resolved subject (request.state.cutctx_user_id,
        #      set by the SSO validator). This is the only trusted
        #      source.
        #   2. Admin-key fingerprint (the first 8 chars of the API
        #      key SHA-256, prefixed "key:"). This is a stable,
        #      non-secret identifier for the key holder.
        #   3. "admin" — only when neither is available (which
        #      should never happen since both auth methods gate
        #      this path).
        # Audit-Deep-2026-06-21 Blocker 6: use the shared helper so the
        # same hierarchy applies to all admin paths (including
        # /stats/reset in server.py).
        actor = _resolve_audit_actor(request)

        await proxy.audit_logger.async_log(
            AuditEvent(
                action=action,
                actor=actor,
                detail=detail,
                org_id=org_id,
                workspace_id=workspace_id,
                project_id=project_id,
                success=success,
                ip_address=getattr(request.client, "host", None),
                user_agent=request.headers.get("user-agent"),
            )
        )
    except Exception:
        logger.debug("Failed to write admin audit event", exc_info=True)


def _scim_user_resource(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
        "id": user["id"],
        "userName": user["user_name"],
        "displayName": user.get("display_name"),
        "externalId": user.get("external_id"),
        "active": user.get("active", True),
        "emails": user.get("emails", []),
        "meta": {
            **(user.get("meta") or {}),
            "resourceType": "User",
            "created": user.get("created_at"),
            "lastModified": user.get("updated_at"),
        },
    }


def _scim_group_resource(group: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
        "id": group["id"],
        "displayName": group["display_name"],
        "externalId": group.get("external_id"),
        "members": group.get("members", []),
        "meta": {
            **(group.get("meta") or {}),
            "resourceType": "Group",
            "created": group.get("created_at"),
            "lastModified": group.get("updated_at"),
        },
    }


def _scim_list_response(resources: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
        "totalResults": len(resources),
        "startIndex": 1,
        "itemsPerPage": len(resources),
        "Resources": resources,
    }


def _extract_scim_updates(body: dict[str, Any], mapping: dict[str, str]) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    operations = body.get("Operations")
    if isinstance(operations, list):
        for operation in operations:
            if not isinstance(operation, dict):
                continue
            path = operation.get("path")
            value = operation.get("value")
            if path and path in mapping:
                updates[mapping[path]] = value
                continue
            if isinstance(value, dict):
                for key, field_name in mapping.items():
                    if key in value:
                        updates[field_name] = value[key]
        return updates

    for key, field_name in mapping.items():
        if key in body:
            updates[field_name] = body[key]
    return updates


# ── Router factory ───────────────────────────────────────────────────────


def create_admin_router(
    proxy: Any,
    config: Any,
    *,
    require_admin_auth: Any,
    require_rbac_permission: Any,
    require_entitlement: Any,
    firewall_scanner: Any = None,
) -> APIRouter:
    """Create and return the enterprise admin APIRouter.

    Parameters
    ----------
    proxy : CutctxProxy
        The main proxy instance holding metrics, stores, etc.
    config : ProxyConfig
        The proxy configuration.
    require_admin_auth, require_rbac_permission, require_entitlement
        FastAPI dependency callables (from server.py).
    firewall_scanner : FirewallScanner | None
        Optional initialised firewall scanner instance.
    """
    router = APIRouter(tags=["enterprise"])

    # Local aliases for readability
    _proxy = proxy
    _config = config
    _firewall_scanner = firewall_scanner
    _Dep = Depends

    # ── Enterprise Admin Dashboard ────────────────────────────────────
    from pathlib import Path as _Path

    from fastapi.responses import HTMLResponse as _HTMLResponse

    # Blocker-6 (production-audit-2026-06-20.md): the EE admin
    # dashboard route previously read
    # `dashboard/dist/index.html` which does not exist. The
    # actual dashboard is at `cutctx/dashboard/templates/dashboard.html`.
    # The fix tries the EE build path first, then falls back to
    # the OSS dashboard, then to a friendly 404 with a link to
    # the working /dashboard route.
    _ADMIN_DASHBOARD_CANDIDATES = [
        _Path(__file__).resolve().parent.parent.parent.parent / "dashboard" / "dist" / "index.html",
        _Path(__file__).resolve().parent.parent.parent.parent
        / "dashboard"
        / "templates"
        / "dashboard.html",
    ]

    @router.get(
        "/admin",
        response_class=_HTMLResponse,
        include_in_schema=False,
        dependencies=[_Dep(require_admin_auth), _Dep(require_rbac_permission("dashboard.read"))],
    )
    async def admin_dashboard():
        """Serve the enterprise admin dashboard UI.

        Tries the EE build first, then falls back to the OSS
        dashboard. If neither file is present, returns a
        friendly HTML page that points the operator at the
        working ``/dashboard`` route instead of an opaque 404.
        """
        for candidate in _ADMIN_DASHBOARD_CANDIDATES:
            try:
                content = candidate.read_text(encoding="utf-8")
                return _HTMLResponse(content=content)
            except FileNotFoundError:
                continue
        # Neither file is present — return a helpful HTML page
        # that links to the working /dashboard route. The
        # enterprise admin surface (spend, audit, policy, RBAC)
        # is still accessible via the API endpoints below; this
        # page is the UI for those features.
        return _HTMLResponse(
            content=(
                "<!DOCTYPE html>"
                "<html><head><title>Cutctx Admin</title></head><body>"
                "<h1>Cutctx Admin Dashboard</h1>"
                "<p>The enterprise admin UI is not built. The OSS dashboard is "
                "available at <a href='/dashboard'>/dashboard</a> and the JSON "
                "admin API is documented in the OpenAPI schema.</p>"
                "<h2>Available API endpoints</h2>"
                "<ul>"
                "<li><code>GET /entitlements</code> — current tier + features</li>"
                "<li><code>GET /audit/events</code> — audit log query</li>"
                "<li><code>GET /reports/savings</code> — savings report</li>"
                "<li><code>GET /reports/usage</code> — usage report</li>"
                "<li><code>GET /rbac/roles</code> — RBAC role assignments</li>"
                "<li><code>POST /cache/clear</code> — clear response cache</li>"
                "<li><code>GET /webhooks/subscriptions</code> — list webhook subscribers</li>"
                "<li><code>POST /webhooks/subscriptions</code> — add a subscriber</li>"
                "<li><code>DELETE /webhooks/subscriptions</code> — remove a subscriber</li>"
                "<li><code>POST /webhooks/test</code> — fire a synthetic test event</li>"
                "</ul></body></html>"
            ),
            status_code=200,
        )

    # ── Webhook subscription management ────────────────────────────
    # High-15 (production-audit-progress-2026-06-20.md): expose the
    # new production-grade webhook dispatcher behind a set of
    # admin endpoints. Operators can list, add, remove, and
    # test subscriptions from the same /admin surface that
    # already serves the dashboard.

    from pydantic import BaseModel
    from pydantic import Field as _Field

    class _WebhookSubIn(BaseModel):
        url: str = _Field(..., min_length=1, max_length=2048)
        secret: str = _Field(..., min_length=8, max_length=256)
        event_types: list[str] | None = _Field(
            default=None,
            description="If null, all events. Else, only listed types.",
        )
        org_id: str | None = _Field(
            default=None,
            description="If set, only events for this org are delivered.",
        )
        enabled: bool = _Field(default=True)

    @router.get(
        "/webhooks/subscriptions",
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("webhooks.read")),
        ],
    )
    async def webhooks_list():
        """List configured webhook subscriptions."""
        from cutctx.proxy.webhooks import get_webhook_dispatcher

        d = get_webhook_dispatcher()
        return {"subscriptions": d.list_subscriptions()}

    @router.post(
        "/webhooks/subscriptions",
        status_code=201,
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("webhooks.write")),
        ],
    )
    async def webhooks_subscribe(body: _WebhookSubIn):
        """Register a new webhook subscription (idempotent on URL)."""
        from cutctx.proxy.webhooks import (
            WebhookEventType,
            WebhookSubscription,
            get_webhook_dispatcher,
        )

        # Validate event types against the known enum.
        et_set: set[str] | None = None
        if body.event_types is not None:
            unknown = set(body.event_types) - {e.value for e in WebhookEventType}
            if unknown:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "unknown_event_types",
                        "unknown": sorted(unknown),
                        "valid": sorted(e.value for e in WebhookEventType),
                    },
                )
            et_set = set(body.event_types)
        sub = WebhookSubscription(
            url=body.url,
            secret=body.secret,
            event_types=et_set,
            org_id=body.org_id,
            enabled=body.enabled,
        )
        d = get_webhook_dispatcher()
        d.subscribe(sub)
        return {"ok": True, "subscription": d.list_subscriptions()[-1]}

    @router.delete(
        "/webhooks/subscriptions",
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("webhooks.write")),
        ],
    )
    async def webhooks_unsubscribe(url: str):
        """Remove a subscription by URL."""
        from cutctx.proxy.webhooks import get_webhook_dispatcher

        d = get_webhook_dispatcher()
        removed = d.unsubscribe(url)
        if not removed:
            raise HTTPException(
                status_code=404,
                detail=f"No subscription for url={url!r}",
            )
        return {"ok": True, "removed": url}

    @router.post(
        "/webhooks/test",
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("webhooks.write")),
        ],
    )
    async def webhooks_test(
        event_type: str = "spend.threshold_exceeded",
        org_id: str | None = None,
    ):
        """Fire a synthetic test event for end-to-end verification."""
        from cutctx.proxy.webhooks import get_webhook_dispatcher

        d = get_webhook_dispatcher()
        n = await d.fire(
            event_type,
            {
                "test": True,
                "message": "This is a synthetic test event from cutctx admin",
            },
            org_id=org_id,
        )
        return {"enqueued_for": n, "event_type": event_type}

    # ── Entitlement Status ────────────────────────────────────────────

    @router.get(
        "/entitlements",
        dependencies=[_Dep(require_admin_auth), _Dep(require_rbac_permission("entitlements.read"))],
    )
    async def entitlements_status():
        """Current entitlement tier and available features."""
        checker = _proxy.entitlement_checker
        if checker is None:
            return {"error": "Entitlement checker not initialized"}
        from cutctx.entitlements import FEATURE_TIERS

        available = checker.list_features()
        all_features = sorted(FEATURE_TIERS.items(), key=lambda x: x[1].value)
        return {
            "current_tier": checker.plan_name,
            "available_count": len(available),
            "total_features": len(FEATURE_TIERS),
            "features": {
                name: {
                    "available": checker.is_entitled(name),
                    "required_tier": tier.name.lower(),
                }
                for name, tier in all_features
            },
        }

    # ── Audit Log Query ───────────────────────────────────────────────

    @router.get(
        "/audit/events",
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("audit.read")),
            _Dep(require_entitlement("audit_logs")),
        ],
    )
    async def audit_events(
        action: str | None = None,
        actor: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ):
        """Query audit events."""
        if not _proxy.audit_logger:
            raise HTTPException(status_code=503, detail="Audit logging not available")
        events = _proxy.audit_logger.query(
            action=action,
            actor=actor,
            since=since,
            until=until,
            limit=min(limit, 500),
            offset=offset,
        )
        total = _proxy.audit_logger.count(action=action)
        return {"events": events, "total": total, "limit": limit, "offset": offset}

    @router.get(
        "/audit/export",
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("audit.export")),
            _Dep(require_entitlement("audit_logs")),
        ],
    )
    async def audit_export(format: Literal["jsonl", "json"] = "jsonl", limit: int = 1000):
        """Export audit events as JSONL or JSON array."""
        if not _proxy.audit_logger:
            raise HTTPException(status_code=503, detail="Audit logging not available")
        if format == "jsonl":
            content = _proxy.audit_logger.export_jsonl(limit=limit)
            return Response(
                content=content,
                media_type="application/x-ndjson",
                headers={"Content-Disposition": 'attachment; filename="audit-events.jsonl"'},
            )
        events = _proxy.audit_logger.query(limit=limit)
        return {"events": events, "count": len(events)}

    @router.get(
        "/audit/verify",
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("audit.read")),
            _Dep(require_entitlement("audit_logs")),
        ],
    )
    async def audit_verify(tenant_id: str | None = None):
        """Lightweight integrity check for the audit log.

        Medium-32 (production-audit-progress-2026-06-20.md): the simple
        SQLite audit log is not tamper-evident on its own. This
        endpoint exposes a monotonicity + schema check via
        ``AuditLogger.verify_chain`` (lightweight) and also tries
        the hash-chain store's ``verify_chain`` for full
        cryptographic integrity when one is configured. Returns
        200 if the lightweight check passes; returns 503 if no
        audit log is configured; returns 500 if the lightweight
        check fails (so the operator's monitoring catches it).
        """
        if not _proxy.audit_logger:
            raise HTTPException(status_code=503, detail="Audit logging not available")
        light = _proxy.audit_logger.verify_chain(tenant_id=tenant_id)
        # Best-effort: if a hash-chain store is configured, run it too.
        chain_result: dict[str, Any] | None = None
        try:
            chain_store = getattr(_proxy, "audit_chain_store", None)
            if chain_store is not None and hasattr(chain_store, "verify_chain"):
                chain_ok = chain_store.verify_chain(tenant_id or "default")
                chain_result = {"ok": chain_ok}
        except Exception:  # noqa: BLE001
            chain_result = {"ok": False, "error": "Health check failed"}
        if not light.get("ok", False):
            raise HTTPException(
                status_code=500,
                detail={
                    "lightweight": light,
                    "hash_chain": chain_result,
                },
            )
        return {"ok": True, "lightweight": light, "hash_chain": chain_result}

    @router.get(
        "/audit/stats",
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("audit.read")),
            _Dep(require_entitlement("audit_logs")),
        ],
    )
    async def audit_stats():
        """Return audit statistics (event counts, recent activity summary).

        Returns a JSON object with:
        - ``total_events``: total audit event count.
        - ``by_action``: event counts grouped by action (top 20).
        - ``recent_events``: last 10 events (most recent first).
        """
        if not _proxy.audit_logger:
            raise HTTPException(status_code=503, detail="Audit logging not available")
        total = _proxy.audit_logger.count()
        # Aggregate action counts — query with a generous limit so
        # we capture a realistic sample, then collapse by action.
        recent = _proxy.audit_logger.query(limit=10)
        events_sample = _proxy.audit_logger.query(limit=2000)
        by_action: dict[str, int] = {}
        for event in events_sample:
            action = event.get("action", "unknown")
            by_action[action] = by_action.get(action, 0) + 1
        # Sort descending by count
        sorted_actions = sorted(by_action.items(), key=lambda x: -x[1])[:20]
        return {
            "total_events": total,
            "by_action": dict(sorted_actions),
            "recent_events": recent,
        }

    # ── Org / Workspace / Project Management ──────────────────────────

    @router.get(
        "/orgs",
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("orgs.read")),
            _Dep(require_entitlement("workspace_model")),
        ],
    )
    async def list_orgs():
        """List all organizations."""
        if not _proxy.org_store:
            raise HTTPException(status_code=503, detail="Org store not available")
        return {"orgs": _proxy.org_store.list_orgs()}

    @router.post(
        "/orgs",
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("orgs.write")),
            _Dep(require_entitlement("workspace_model")),
        ],
    )
    async def create_org(request: Request):
        """Create a new organization."""
        if not _proxy.org_store:
            raise HTTPException(status_code=503, detail="Org store not available")
        body = await request.json()
        name = body.get("name")
        if not name:
            raise HTTPException(status_code=400, detail="name is required")
        org = _proxy.org_store.create_org(
            name=name,
            admin_email=body.get("admin_email"),
            slug=body.get("slug"),
            settings=body.get("settings"),
        )
        await _audit_admin_action(
            _proxy,
            request,
            action="config.changed",
            detail={"action": "org_created", "org_id": org["id"], "name": name},
        )
        return {"org": org}

    @router.get(
        "/orgs/{org_id}",
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("orgs.read")),
            _Dep(require_entitlement("workspace_model")),
        ],
    )
    async def get_org(org_id: str):
        """Get organization with full hierarchy."""
        if not _proxy.org_store:
            raise HTTPException(status_code=503, detail="Org store not available")
        hierarchy = _proxy.org_store.get_org_hierarchy(org_id)
        if not hierarchy:
            raise HTTPException(status_code=404, detail="Organization not found")
        return {"org": hierarchy}

    @router.post(
        "/orgs/{org_id}/workspaces",
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("workspaces.write")),
            _Dep(require_entitlement("workspace_model")),
        ],
    )
    async def create_workspace(org_id: str, request: Request):
        """Create a workspace in an organization."""
        if not _proxy.org_store:
            raise HTTPException(status_code=503, detail="Org store not available")
        body = await request.json()
        name = body.get("name")
        if not name:
            raise HTTPException(status_code=400, detail="name is required")
        ws = _proxy.org_store.create_workspace(
            org_id=org_id,
            name=name,
            slug=body.get("slug"),
            settings=body.get("settings"),
        )
        return {"workspace": ws}

    @router.get(
        "/workspaces/{workspace_id}/projects",
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("orgs.read")),
            _Dep(require_entitlement("project_model")),
        ],
    )
    async def list_projects(workspace_id: str):
        """List projects in a workspace."""
        if not _proxy.org_store:
            raise HTTPException(status_code=503, detail="Org store not available")
        return {"projects": _proxy.org_store.list_projects(workspace_id)}

    @router.post(
        "/workspaces/{workspace_id}/projects",
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("projects.write")),
            _Dep(require_entitlement("project_model")),
        ],
    )
    async def create_project(workspace_id: str, request: Request):
        """Create a project in a workspace."""
        if not _proxy.org_store:
            raise HTTPException(status_code=503, detail="Org store not available")
        body = await request.json()
        name = body.get("name")
        if not name:
            raise HTTPException(status_code=400, detail="name is required")
        proj = _proxy.org_store.create_project(
            workspace_id=workspace_id,
            name=name,
            slug=body.get("slug"),
            path=body.get("path"),
            settings=body.get("settings"),
        )
        return {"project": proj}

    # ── License Status ────────────────────────────────────────────────

    @router.get(
        "/license-status",
        dependencies=[_Dep(require_admin_auth), _Dep(require_rbac_permission("license.read"))],
    )
    async def license_status():
        """Current license status and usage reporting state."""
        reporter = _proxy.usage_reporter
        result: dict[str, Any] = {
            "has_license_key": bool(_config.license_key),
            "reporting_enabled": reporter is not None,
            "reporting_interval_seconds": _config.license_report_interval,
        }
        if reporter and reporter._license_info:
            li = reporter._license_info
            result.update(
                {
                    "status": li.status,
                    "plan": li.plan,
                    "org_id": li.org_id,
                    "quota_tokens": li.quota_tokens,
                    "used_tokens": getattr(li, "used_tokens", None),
                    "trial_expires_at": (
                        li.trial_expires_at.isoformat() if li.trial_expires_at else None
                    ),
                    "last_validated_at": getattr(reporter, "_last_validated_at", None),
                }
            )
        elif _config.license_key:
            result["status"] = "unvalidated"
        else:
            result["status"] = "no_license"
        return result

    # ── Reports ───────────────────────────────────────────────────────

    @router.get(
        "/reports/savings",
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("reports.read")),
            _Dep(require_entitlement("usage_reports")),
        ],
    )
    async def reports_savings(format: Literal["json", "csv"] = "json"):
        """ROI summary report: tokens saved, cost saved, compression ratios."""
        m = _proxy.metrics
        total_tokens_before = m.tokens_input_total + m.tokens_saved_total
        savings_pct = (
            round(m.tokens_saved_total / total_tokens_before * 100, 2)
            if total_tokens_before > 0
            else 0
        )

        cost_stats = _proxy.cost_tracker.stats() if _proxy.cost_tracker else {}
        cost_saved = cost_stats.get("total_savings_usd", 0.0)

        report = {
            "report_type": "savings_summary",
            "generated_at": _iso_utc_now(),
            "period": "all_time",
            "tokens": {
                "input_total": m.tokens_input_total,
                "output_total": m.tokens_output_total,
                "saved_total": m.tokens_saved_total,
                "before_compression": total_tokens_before,
                "savings_percent": savings_pct,
            },
            "cost": {
                "total_usd": cost_stats.get("total_cost_usd", 0.0),
                "saved_usd": cost_saved,
                "by_model": cost_stats.get("by_model", {}),
            },
            "compression": {
                "requests_total": m.requests_total,
                "requests_cached": m.requests_cached,
                "cache_hit_rate": (round(m.requests_cached / max(1, m.requests_total) * 100, 2)),
                "by_strategy": dict(m.compressions_by_strategy),
                "tokens_by_strategy": dict(m.tokens_saved_by_strategy),
            },
        }

        if format == "csv":
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(["Metric", "Value"])
            writer.writerow(["Input Tokens", m.tokens_input_total])
            writer.writerow(["Output Tokens", m.tokens_output_total])
            writer.writerow(["Tokens Saved", m.tokens_saved_total])
            writer.writerow(["Savings Percent", savings_pct])
            writer.writerow(["Total Cost USD", report["cost"]["total_usd"]])
            writer.writerow(["Cost Saved USD", cost_saved])
            writer.writerow(["Cache Hit Rate", report["compression"]["cache_hit_rate"]])
            filename = f"cutctx-savings-{_iso_utc_now()[:10]}.csv"
            return Response(
                content=buf.getvalue(),
                media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        return report

    @router.get(
        "/reports/usage",
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("reports.read")),
            _Dep(require_entitlement("usage_reports")),
        ],
    )
    async def reports_usage(format: Literal["json", "csv"] = "json"):
        """Usage report: requests by provider, model, stack, and time."""
        m = _proxy.metrics
        report = {
            "report_type": "usage_summary",
            "generated_at": _iso_utc_now(),
            "requests": {
                "total": m.requests_total,
                "cached": m.requests_cached,
                "rate_limited": m.requests_rate_limited,
                "failed": m.requests_failed,
                "by_provider": dict(m.requests_by_provider),
                "by_model": dict(m.requests_by_model),
                "by_stack": dict(m.requests_by_stack),
            },
            "latency": {
                "average_ms": round(m.latency_sum_ms / max(1, m.latency_count), 2),
                "min_ms": round(m.latency_min_ms, 2) if m.latency_min_ms != float("inf") else 0,
                "max_ms": round(m.latency_max_ms, 2),
            },
            "transformations": {
                "by_strategy": dict(m.compressions_by_strategy),
            },
        }

        if format == "csv":
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(["Provider", "Requests"])
            for provider, count in m.requests_by_provider.items():
                writer.writerow([provider, count])
            writer.writerow([])
            writer.writerow(["Model", "Requests"])
            for model, count in m.requests_by_model.items():
                writer.writerow([model, count])
            filename = f"cutctx-usage-{_iso_utc_now()[:10]}.csv"
            return Response(
                content=buf.getvalue(),
                media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        return report

    # ── Retention Controls ────────────────────────────────────────────

    @router.get(
        "/retention/stats",
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("stats.read")),
            _Dep(require_entitlement("retention_controls")),
        ],
    )
    async def retention_stats():
        """Retention policy configuration and cleanup statistics."""
        from cutctx.retention import get_retention_manager

        manager = get_retention_manager()
        return {"retention": manager.get_stats()}

    @router.post(
        "/retention/cleanup",
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("retention.write")),
            _Dep(require_entitlement("retention_controls")),
        ],
    )
    async def retention_cleanup(request: Request):
        """Trigger an immediate retention cleanup cycle."""
        from cutctx.retention import get_retention_manager

        manager = get_retention_manager()
        results = await manager.run_cleanup()
        await _audit_admin_action(
            _proxy,
            request,
            action="retention.cleanup",
            detail=results,
        )
        return {"status": "completed", "results": results}

    # ── RBAC Management ───────────────────────────────────────────────

    @router.get(
        "/rbac/roles",
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("dashboard.read")),
            _Dep(require_entitlement("rbac")),
        ],
    )
    async def rbac_list_roles():
        """List all role assignments."""
        from cutctx.rbac import get_rbac_checker

        checker = get_rbac_checker()
        return {"assignments": checker.list_assignments()}

    @router.post(
        "/rbac/roles",
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("rbac.write")),
            _Dep(require_entitlement("rbac")),
        ],
    )
    async def rbac_assign_role(request: Request):
        """Assign a role to a user."""
        from cutctx.rbac import AdminRole, get_rbac_checker

        body = await request.json()
        user_id = body.get("user_id")
        role_str = body.get("role")
        if not user_id or not role_str:
            raise HTTPException(status_code=400, detail="user_id and role are required")
        try:
            role = AdminRole(role_str)
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid role: {role_str}. Must be: admin, operator, viewer",
            ) from e
        checker = get_rbac_checker()
        checker.assign_role(user_id, role)
        await _audit_admin_action(
            _proxy,
            request,
            action="rbac.role_assigned",
            detail={"target_user": user_id, "role": role.value},
        )
        return {"status": "assigned", "user_id": user_id, "role": role.value}

    @router.delete(
        "/rbac/roles/{user_id}",
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("rbac.write")),
            _Dep(require_entitlement("rbac")),
        ],
    )
    async def rbac_revoke_role(user_id: str, request: Request):
        """Revoke a user's role assignment."""
        from cutctx.rbac import get_rbac_checker

        checker = get_rbac_checker()
        revoked = checker.revoke_role(user_id)
        await _audit_admin_action(
            _proxy,
            request,
            action="rbac.role_revoked",
            detail={"target_user": user_id, "revoked": revoked},
        )
        return {"status": "revoked" if revoked else "not_found", "user_id": user_id}

    # ── Fleet Management ──────────────────────────────────────────────

    @router.get(
        "/fleet/deployments",
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("fleet.read")),
            _Dep(require_entitlement("fleet_management")),
        ],
    )
    async def fleet_deployments(org_id: str | None = None, status: str | None = None):
        """List registered deployments with optional org/status filters."""
        if not _proxy.fleet_store:
            raise HTTPException(status_code=503, detail="Fleet store not available")
        return {
            "deployments": _proxy.fleet_store.list_deployments(org_id=org_id, status=status),
        }

    @router.post(
        "/fleet/deployments/heartbeat",
        status_code=201,
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("fleet.write")),
            _Dep(require_entitlement("fleet_management")),
        ],
    )
    async def fleet_heartbeat(request: Request):
        """Create or refresh a deployment heartbeat record."""
        if not _proxy.fleet_store:
            raise HTTPException(status_code=503, detail="Fleet store not available")
        body = await request.json()
        deployment = _proxy.fleet_store.upsert_heartbeat(
            deployment_id=body.get("deployment_id"),
            name=body.get("name"),
            org_id=body.get("org_id"),
            workspace_id=body.get("workspace_id"),
            project_id=body.get("project_id"),
            environment=body.get("environment"),
            region=body.get("region"),
            version=body.get("version"),
            status=body.get("status", "healthy"),
            metadata=body.get("metadata"),
        )
        await _audit_admin_action(
            _proxy,
            request,
            action="fleet.heartbeat",
            detail={
                "deployment_id": deployment["deployment_id"],
                "name": deployment.get("name"),
                "status": deployment.get("status"),
            },
            org_id=deployment.get("org_id"),
            workspace_id=deployment.get("workspace_id"),
            project_id=deployment.get("project_id"),
        )
        return {"deployment": deployment}

    @router.get(
        "/fleet/deployments/{deployment_id}",
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("fleet.read")),
            _Dep(require_entitlement("fleet_management")),
        ],
    )
    async def fleet_deployment(deployment_id: str):
        """Fetch a single deployment by ID."""
        if not _proxy.fleet_store:
            raise HTTPException(status_code=503, detail="Fleet store not available")
        deployment = _proxy.fleet_store.get_deployment(deployment_id)
        if not deployment:
            raise HTTPException(status_code=404, detail="Deployment not found")
        return {"deployment": deployment}

    @router.delete(
        "/fleet/deployments/{deployment_id}",
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("fleet.write")),
            _Dep(require_entitlement("fleet_management")),
        ],
    )
    async def fleet_delete_deployment(deployment_id: str, request: Request):
        """Delete a deployment record."""
        if not _proxy.fleet_store:
            raise HTTPException(status_code=503, detail="Fleet store not available")
        deleted = _proxy.fleet_store.delete_deployment(deployment_id)
        await _audit_admin_action(
            _proxy,
            request,
            action="fleet.deleted",
            detail={"deployment_id": deployment_id, "deleted": deleted},
            success=deleted,
        )
        if not deleted:
            raise HTTPException(status_code=404, detail="Deployment not found")
        return {"status": "deleted", "deployment_id": deployment_id}

    @router.get(
        "/fleet/summary",
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("fleet.read")),
            _Dep(require_entitlement("fleet_management")),
        ],
    )
    async def fleet_summary():
        """Return fleet-wide health summary."""
        if not _proxy.fleet_store:
            raise HTTPException(status_code=503, detail="Fleet store not available")
        return {"summary": _proxy.fleet_store.summarize()}

    # ── SCIM Provisioning ─────────────────────────────────────────────

    @router.get(
        "/scim/v2/ServiceProviderConfig",
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("scim.read")),
            _Dep(require_entitlement("scim")),
        ],
    )
    async def scim_service_provider_config():
        """Minimal SCIM capability descriptor for IdP integrations."""
        return {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig"],
            "patch": {"supported": True},
            "bulk": {"supported": False},
            "filter": {"supported": True, "maxResults": 200},
            "changePassword": {"supported": False},
            "sort": {"supported": False},
            "etag": {"supported": False},
            "authenticationSchemes": [
                {
                    "name": "Bearer Token",
                    "description": "Use SSO bearer tokens or the admin API key",
                    "type": "oauthbearertoken",
                    "primary": True,
                }
            ],
        }

    @router.get(
        "/scim/v2/ResourceTypes",
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("scim.read")),
            _Dep(require_entitlement("scim")),
        ],
    )
    async def scim_resource_types():
        """Advertise supported SCIM resource types."""
        return {
            "Resources": [
                {"id": "User", "name": "User", "endpoint": "/scim/v2/Users"},
                {"id": "Group", "name": "Group", "endpoint": "/scim/v2/Groups"},
            ]
        }

    @router.get(
        "/scim/v2/Users",
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("scim.read")),
            _Dep(require_entitlement("scim")),
        ],
    )
    async def scim_list_users(userName: str | None = None):
        """List provisioned users."""
        if not _proxy.scim_store:
            raise HTTPException(status_code=503, detail="SCIM store not available")
        users = _proxy.scim_store.list_users(user_name=userName)
        return _scim_list_response([_scim_user_resource(user) for user in users])

    @router.post(
        "/scim/v2/Users",
        status_code=201,
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("scim.write")),
            _Dep(require_entitlement("scim")),
        ],
    )
    async def scim_create_user(request: Request):
        """Create a provisioned user."""
        if not _proxy.scim_store:
            raise HTTPException(status_code=503, detail="SCIM store not available")
        body = await request.json()
        user_name = body.get("userName") or body.get("user_name")
        if not user_name:
            raise HTTPException(status_code=400, detail="userName is required")
        user = _proxy.scim_store.create_user(
            user_name=user_name,
            display_name=body.get("displayName") or body.get("display_name"),
            external_id=body.get("externalId") or body.get("external_id"),
            active=body.get("active", True),
            emails=body.get("emails"),
            meta=body.get("meta"),
        )
        await _audit_admin_action(
            _proxy,
            request,
            action="scim.user_created",
            detail={"user_id": user["id"], "user_name": user["user_name"]},
        )
        return _scim_user_resource(user)

    @router.get(
        "/scim/v2/Users/{user_id}",
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("scim.read")),
            _Dep(require_entitlement("scim")),
        ],
    )
    async def scim_get_user(user_id: str):
        """Fetch a provisioned user."""
        if not _proxy.scim_store:
            raise HTTPException(status_code=503, detail="SCIM store not available")
        user = _proxy.scim_store.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return _scim_user_resource(user)

    @router.put(
        "/scim/v2/Users/{user_id}",
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("scim.write")),
            _Dep(require_entitlement("scim")),
        ],
    )
    @router.patch(
        "/scim/v2/Users/{user_id}",
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("scim.write")),
            _Dep(require_entitlement("scim")),
        ],
    )
    async def scim_update_user(user_id: str, request: Request):
        """Update a provisioned user using simple SCIM patch semantics."""
        if not _proxy.scim_store:
            raise HTTPException(status_code=503, detail="SCIM store not available")
        body = await request.json()
        updates = _extract_scim_updates(
            body,
            {
                "userName": "user_name",
                "user_name": "user_name",
                "displayName": "display_name",
                "display_name": "display_name",
                "externalId": "external_id",
                "external_id": "external_id",
                "active": "active",
                "emails": "emails",
                "meta": "meta",
            },
        )
        user = _proxy.scim_store.update_user(user_id, **updates)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        await _audit_admin_action(
            _proxy,
            request,
            action="scim.user_updated",
            detail={"user_id": user_id, "fields": sorted(updates)},
        )
        return _scim_user_resource(user)

    @router.delete(
        "/scim/v2/Users/{user_id}",
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("scim.write")),
            _Dep(require_entitlement("scim")),
        ],
    )
    async def scim_delete_user(user_id: str, request: Request):
        """Delete a provisioned user."""
        if not _proxy.scim_store:
            raise HTTPException(status_code=503, detail="SCIM store not available")
        deleted = _proxy.scim_store.delete_user(user_id)
        await _audit_admin_action(
            _proxy,
            request,
            action="scim.user_deleted",
            detail={"user_id": user_id, "deleted": deleted},
            success=deleted,
        )
        if not deleted:
            raise HTTPException(status_code=404, detail="User not found")
        return {"status": "deleted", "id": user_id}

    @router.get(
        "/scim/v2/Groups",
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("scim.read")),
            _Dep(require_entitlement("scim")),
        ],
    )
    async def scim_list_groups():
        """List provisioned groups."""
        if not _proxy.scim_store:
            raise HTTPException(status_code=503, detail="SCIM store not available")
        groups = _proxy.scim_store.list_groups()
        return _scim_list_response([_scim_group_resource(group) for group in groups])

    @router.post(
        "/scim/v2/Groups",
        status_code=201,
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("scim.write")),
            _Dep(require_entitlement("scim")),
        ],
    )
    async def scim_create_group(request: Request):
        """Create a provisioned group."""
        if not _proxy.scim_store:
            raise HTTPException(status_code=503, detail="SCIM store not available")
        body = await request.json()
        display_name = body.get("displayName") or body.get("display_name")
        if not display_name:
            raise HTTPException(status_code=400, detail="displayName is required")
        group = _proxy.scim_store.create_group(
            display_name=display_name,
            external_id=body.get("externalId") or body.get("external_id"),
            members=body.get("members"),
            meta=body.get("meta"),
        )
        await _audit_admin_action(
            _proxy,
            request,
            action="scim.group_created",
            detail={"group_id": group["id"], "display_name": group["display_name"]},
        )
        return _scim_group_resource(group)

    @router.get(
        "/scim/v2/Groups/{group_id}",
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("scim.read")),
            _Dep(require_entitlement("scim")),
        ],
    )
    async def scim_get_group(group_id: str):
        """Fetch a provisioned group."""
        if not _proxy.scim_store:
            raise HTTPException(status_code=503, detail="SCIM store not available")
        group = _proxy.scim_store.get_group(group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        return _scim_group_resource(group)

    @router.put(
        "/scim/v2/Groups/{group_id}",
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("scim.write")),
            _Dep(require_entitlement("scim")),
        ],
    )
    @router.patch(
        "/scim/v2/Groups/{group_id}",
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("scim.write")),
            _Dep(require_entitlement("scim")),
        ],
    )
    async def scim_update_group(group_id: str, request: Request):
        """Update a provisioned group using simple SCIM patch semantics."""
        if not _proxy.scim_store:
            raise HTTPException(status_code=503, detail="SCIM store not available")
        body = await request.json()
        updates = _extract_scim_updates(
            body,
            {
                "displayName": "display_name",
                "display_name": "display_name",
                "externalId": "external_id",
                "external_id": "external_id",
                "members": "members",
                "meta": "meta",
            },
        )
        group = _proxy.scim_store.update_group(group_id, **updates)
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        await _audit_admin_action(
            _proxy,
            request,
            action="scim.group_updated",
            detail={"group_id": group_id, "fields": sorted(updates)},
        )
        return _scim_group_resource(group)

    @router.delete(
        "/scim/v2/Groups/{group_id}",
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("scim.write")),
            _Dep(require_entitlement("scim")),
        ],
    )
    async def scim_delete_group(group_id: str, request: Request):
        """Delete a provisioned group."""
        if not _proxy.scim_store:
            raise HTTPException(status_code=503, detail="SCIM store not available")
        deleted = _proxy.scim_store.delete_group(group_id)
        await _audit_admin_action(
            _proxy,
            request,
            action="scim.group_deleted",
            detail={"group_id": group_id, "deleted": deleted},
            success=deleted,
        )
        if not deleted:
            raise HTTPException(status_code=404, detail="Group not found")
        return {"status": "deleted", "id": group_id}

    # ── Firewall ──────────────────────────────────────────────────────

    @router.get(
        "/firewall/status",
        dependencies=[_Dep(require_admin_auth), _Dep(require_rbac_permission("stats.read"))],
    )
    async def firewall_status():
        """Get LLM firewall status and scan statistics."""
        if _firewall_scanner is None:
            return {
                "enabled": False,
                "message": "Firewall not initialized",
                "patterns_loaded": None,
                "blocks": None,
                "blocks_today": None,
                "telemetry_available": False,
            }

        from cutctx.security.firewall import (
            _EXFIL_PATTERNS,
            _INJECTION_PATTERNS,
            _JAILBREAK_PATTERNS,
            _PII_PATTERNS,
        )

        patterns_loaded = len(_EXFIL_PATTERNS) + len(_firewall_scanner.config.custom_patterns)
        if _firewall_scanner.config.block_injection:
            patterns_loaded += len(_INJECTION_PATTERNS)
        if _firewall_scanner.config.block_jailbreak:
            patterns_loaded += len(_JAILBREAK_PATTERNS)
        if _firewall_scanner.config.block_pii:
            patterns_loaded += len(_PII_PATTERNS)

        return {
            "enabled": _firewall_scanner.enabled,
            "patterns_loaded": patterns_loaded,
            "blocks": None,
            "blocks_today": None,
            "telemetry_available": False,
            "config": {
                "block_pii": _firewall_scanner.config.block_pii,
                "block_injection": _firewall_scanner.config.block_injection,
                "block_jailbreak": _firewall_scanner.config.block_jailbreak,
                "redact_streaming": _firewall_scanner.config.redact_streaming,
                "custom_patterns": len(_firewall_scanner.config.custom_patterns),
                "allowed_domains": len(_firewall_scanner.config.allowed_domains),
            },
        }

    @router.post(
        "/firewall/scan",
        dependencies=[_Dep(require_admin_auth), _Dep(require_rbac_permission("stats.read"))],
    )
    async def firewall_scan_text(request: Request):
        """Scan a text string for security violations."""
        if _firewall_scanner is None:
            raise HTTPException(status_code=503, detail="Firewall not initialized")
        body = await request.json()
        text = body.get("text", "")
        messages = body.get("messages", [])
        if text:
            violations = _firewall_scanner.scan_text(text)
        elif messages:
            violations = _firewall_scanner.scan_messages(messages)
        else:
            raise HTTPException(status_code=400, detail="Provide 'text' or 'messages'")
        return {
            "violations": [
                {"kind": v.kind.value, "description": v.description, "confidence": v.confidence}
                for v in violations
            ],
            "block": _firewall_scanner.should_block(violations),
        }

    # ── Structured Output ─────────────────────────────────────────────

    @router.get(
        "/structured-output/status",
        dependencies=[_Dep(require_admin_auth), _Dep(require_rbac_permission("stats.read"))],
    )
    async def structured_output_status():
        """Get structured output enforcement status."""
        try:
            from cutctx.proxy.structured_output import (
                JSONSCHEMA_AVAILABLE,
                StructuredOutputConfig,
            )

            cfg = StructuredOutputConfig.from_env()
            return {
                "enabled": cfg.enabled and JSONSCHEMA_AVAILABLE,
                "jsonschema_available": JSONSCHEMA_AVAILABLE,
                "max_retries": cfg.max_retries,
                "strict_mode": cfg.strict_mode,
            }
        except Exception:
            return {"enabled": False, "error": "Unable to check structured output support"}

    @router.post(
        "/structured-output/validate",
        dependencies=[_Dep(require_admin_auth), _Dep(require_rbac_permission("stats.read"))],
    )
    async def structured_output_validate(request: Request):
        """Validate a JSON string against a schema."""
        from cutctx.proxy.structured_output import StructuredOutputValidator

        body = await request.json()
        text = body.get("text", "")
        schema = body.get("schema", {})
        if not text or not schema:
            raise HTTPException(status_code=400, detail="Provide 'text' and 'schema'")
        validator = StructuredOutputValidator()
        result = validator.validate(text, schema)
        return {
            "valid": result.valid,
            "errors": result.errors,
            "validation_time_ms": result.validation_time_ms,
        }

    # ── Ensemble ──────────────────────────────────────────────────────

    @router.get(
        "/ensemble/status",
        dependencies=[_Dep(require_admin_auth), _Dep(require_rbac_permission("stats.read"))],
    )
    async def ensemble_status():
        """Get multi-model ensemble configuration status."""
        try:
            from cutctx.proxy.ensemble import EnsembleConfig

            cfg = EnsembleConfig.from_env()
            return {
                "enabled": cfg.enabled,
                "default_models": cfg.default_models,
                "evaluator_model": cfg.evaluator_model,
                "timeout_seconds": cfg.timeout_seconds,
            }
        except Exception:
            return {"enabled": False, "error": "Unable to validate structured output"}

    # ── Budget ────────────────────────────────────────────────────────

    @router.get(
        "/budget/status",
        dependencies=[_Dep(require_admin_auth), _Dep(require_rbac_permission("stats.read"))],
    )
    async def budget_status():
        """Get streaming budget cut-off configuration status."""
        from cutctx.proxy.budget import BudgetConfig

        cfg = BudgetConfig.from_env()
        return {
            "enabled": cfg.enabled,
            "default_budget_tokens": cfg.default_budget_tokens,
            "default_budget_usd": cfg.default_budget_usd,
            "warning_threshold_percent": cfg.warning_threshold_percent,
            "hard_limit": cfg.hard_limit,
        }

    # ── Intelligence Layer Status ─────────────────────────────────────

    @router.get(
        "/intelligence/task-aware/status",
        dependencies=[_Dep(require_admin_auth), _Dep(require_rbac_permission("stats.read"))],
    )
    async def task_aware_status():
        """Get task-aware compression status."""
        return {
            "enabled": getattr(_config, "task_aware_enabled", False),
            "description": "Modulate compression based on relevance to current task",
        }

    @router.get(
        "/intelligence/dedup/status",
        dependencies=[_Dep(require_admin_auth), _Dep(require_rbac_permission("stats.read"))],
    )
    async def dedup_status():
        """Get semantic deduplication status."""
        from cutctx.dedup import MIN_DEDUP_TOKENS

        return {
            "enabled": getattr(_config, "dedup_enabled", False),
            "min_dedup_tokens": MIN_DEDUP_TOKENS,
            "description": "Replace repeated content with CCR pointer references",
        }

    @router.get(
        "/intelligence/context-budget/status",
        dependencies=[_Dep(require_admin_auth), _Dep(require_rbac_permission("stats.read"))],
    )
    async def context_budget_status():
        """Get context budget controller status."""
        return {
            "enabled": getattr(_config, "context_budget_enabled", False),
            "max_tokens": getattr(_config, "context_budget_max_tokens", 100_000),
            "policy": getattr(_config, "context_budget_policy", "balanced"),
            "description": "Progressive compression as token budget fills",
        }

    @router.get(
        "/intelligence/profiles/status",
        dependencies=[_Dep(require_admin_auth), _Dep(require_rbac_permission("stats.read"))],
    )
    async def profiles_status():
        """Get cross-session compression profiles status."""
        return {
            "enabled": getattr(_config, "profiles_enabled", False),
            "description": "Learn compression patterns per workspace across sessions",
        }

    @router.get(
        "/intelligence/shared-context/status",
        dependencies=[_Dep(require_admin_auth), _Dep(require_rbac_permission("stats.read"))],
    )
    async def shared_context_status():
        """Get multi-agent shared compression state status."""
        return {
            "enabled": getattr(_config, "shared_context_enabled", False),
            "description": "Shared compression cache across multiple agents",
        }

    @router.get(
        "/intelligence/cost-forecast/status",
        dependencies=[_Dep(require_admin_auth), _Dep(require_rbac_permission("stats.read"))],
    )
    async def cost_forecast_status():
        """Get cost forecasting + policy engine status."""
        try:
            from cutctx.cost_forecast import MODEL_PRICING

            return {
                "enabled": getattr(_config, "cost_forecast_enabled", False),
                "models_priced": len(MODEL_PRICING),
                "description": "Pre-task cost estimation and policy-driven compression",
            }
        except Exception:
            return {"enabled": False, "error": "Unable to retrieve policy status"}

    @router.get(
        "/intelligence/autopilot/status",
        dependencies=[_Dep(require_admin_auth), _Dep(require_rbac_permission("stats.read"))],
    )
    async def autopilot_status():
        """Get WS19 autopilot status."""
        return {
            "enabled": getattr(_config, "autopilot_enabled", False),
            "min_level": getattr(_config, "autopilot_min_level", 1),
            "max_level": getattr(_config, "autopilot_max_level", 5),
            "hysteresis_window": getattr(_config, "autopilot_hysteresis_window", 10),
            "description": "Auto-tune compression aggressiveness per task type from recent quality signals",
        }

    @router.get(
        "/savings-canary/report",
        dependencies=[_Dep(require_admin_auth), _Dep(require_rbac_permission("stats.read"))],
    )
    async def savings_canary_report():
        from cutctx.proxy.savings_canary import get_savings_canary_coordinator

        return get_savings_canary_coordinator().report()

    @router.post(
        "/savings-canary/feedback",
        dependencies=[_Dep(require_admin_auth), _Dep(require_rbac_permission("stats.read"))],
    )
    async def savings_canary_feedback(body: dict[str, Any]):
        from cutctx.proxy.savings_canary import TREATMENT_ARMS, get_savings_canary_coordinator

        if not str(body.get("event_id") or "").strip():
            raise HTTPException(status_code=422, detail="event_id is required")
        if not str(body.get("arm") or "").strip():
            raise HTTPException(status_code=422, detail="arm is required")
        arm = str(body["arm"])
        if arm not in ("control", *TREATMENT_ARMS):
            raise HTTPException(status_code=422, detail="unknown savings canary arm")
        if "quality_success" not in body:
            raise HTTPException(status_code=422, detail="quality_success is required")
        if not isinstance(body["quality_success"], bool):
            raise HTTPException(status_code=422, detail="quality_success must be boolean")
        request_id = str(body.get("request_id") or "").strip()
        if request_id:
            trace = (
                _proxy.logger.get_request_with_messages(request_id)
                if getattr(_proxy, "logger", None) is not None
                else None
            )
            if trace is None:
                raise HTTPException(status_code=422, detail="request_id trace was not found")
            trace_arm = str((trace.get("canary") or {}).get("arm") or "control")
            if trace_arm != arm:
                raise HTTPException(
                    status_code=422,
                    detail=f"request trace arm is {trace_arm}, not {arm}",
                )
        coordinator = get_savings_canary_coordinator()
        duplicate = coordinator.record_feedback(
            arm,
            event_id=str(body["event_id"]),
            quality_success=bool(body["quality_success"]),
            retries=int(body.get("retries") or 0),
            user_corrections=int(body.get("user_corrections") or 0),
        )
        return {**coordinator.report(), "duplicate": duplicate}

    @router.post(
        "/savings-canary/promote",
        dependencies=[_Dep(require_admin_auth), _Dep(require_rbac_permission("stats.read"))],
    )
    async def savings_canary_promote(body: dict[str, Any]):
        from cutctx.proxy.savings_canary import TREATMENT_ARMS, get_savings_canary_coordinator

        arm = str(body.get("arm") or "")
        if arm not in TREATMENT_ARMS:
            raise HTTPException(status_code=422, detail="a treatment arm is required")
        try:
            return get_savings_canary_coordinator().promote(
                arm,
                int(body.get("percent") or 0),
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    # ── Runtime feature flag toggle API ──────────────────────────────────────
    # The dashboard uses this route as the canonical config surface. Keep it
    # compatible with both the newer *_enabled feature keys and the legacy
    # /admin/config/flags payload shape used by older dashboard cards.

    _LIVE_TOGGLE_KEYS = {
        "task_aware_enabled",
        "dedup_enabled",
        "context_budget_enabled",
        "profiles_enabled",
        "shared_context_enabled",
        "cost_forecast_enabled",
        "autopilot_enabled",
        "episodic_memory_enabled",
        "orchestrator",
        "ccr_context_tracking",
    }
    _RESTART_REQUIRED_KEYS = {
        "cache_enabled",
        "rate_limit_enabled",
        "firewall_enabled",
        "text_compression_engine_enabled",
        "log_template_mining_enabled",
        "audit_enabled",
    }
    _LEGACY_FLAG_ALIASES = {
        "cache": "cache_enabled",
        "ccr": "ccr_context_tracking",
        "memory": "episodic_memory_enabled",
        "firewall": "firewall_enabled",
        "rate_limiter": "rate_limit_enabled",
    }
    _CONFIG_ATTR_ALIASES = {
        "text_compression_engine_enabled": "use_llmlingua",
        "log_template_mining_enabled": "drain3_enabled",
    }
    _RESTART_ENV_VARS = {
        "cache_enabled": "CUTCTX_CACHE_ENABLED",
        "rate_limit_enabled": "CUTCTX_RATE_LIMIT_ENABLED",
        "firewall_enabled": "CUTCTX_FIREWALL_ENABLED",
        "text_compression_engine_enabled": "CUTCTX_TEXT_COMPRESSION_ENABLED",
        "log_template_mining_enabled": "CUTCTX_LOG_TEMPLATE_MINING_ENABLED",
        "audit_enabled": "CUTCTX_AUDIT_DISABLED=0",
    }
    _FLAG_ENTITLEMENTS = {
        "shared_context_enabled": "cross_agent_memory",
        "episodic_memory_enabled": "episodic_memory",
        "audit_enabled": "audit_logs",
    }

    def _normalize_flag_key(key: str) -> str:
        return _LEGACY_FLAG_ALIASES.get(key, key)

    def _config_attr_name(key: str) -> str:
        return _CONFIG_ATTR_ALIASES.get(key, key)

    def _set_flag_on_config(key: str, value: bool) -> None:
        attr_name = _config_attr_name(key)
        if key == "orchestrator":
            _config.orchestrator_enabled = value
            return
        if hasattr(_config, attr_name):
            setattr(_config, attr_name, value)
        if key == "ccr_context_tracking":
            _config.ccr_context_tracking = value
            _config.ccr_handle_responses = value

    def _flag_state(key: str, runtime: dict[str, Any]) -> dict[str, Any]:
        if key == "orchestrator":
            model_router = getattr(_proxy, "_model_router", None)
            enabled = bool(
                model_router
                and getattr(model_router, "config", None)
                and getattr(model_router.config, "enabled", False)
            )
            return {
                "enabled": enabled,
                "source": "runtime",
                "config_default": bool(getattr(_config, "orchestrator_enabled", False)),
            }

        attr_name = _config_attr_name(key)
        config_val = bool(getattr(_config, attr_name, False))
        if key in runtime:
            return {
                "enabled": bool(runtime[key]),
                "source": "runtime",
                "config_default": config_val,
            }
        return {"enabled": config_val, "source": "config", "config_default": config_val}

    def _apply_episodic_memory_toggle(value: bool) -> None:
        _set_flag_on_config("episodic_memory_enabled", value)
        tracker = getattr(_proxy, "episodic_tracker", None)
        if value:
            if tracker is None:
                from cutctx.memory.session_tracker import EpisodicSessionTracker
                from cutctx.memory.store import EpisodicMemoryStore

                tracker = EpisodicSessionTracker(
                    EpisodicMemoryStore(),
                    idle_timeout_seconds=getattr(_config, "episodic_idle_timeout_seconds", 300),
                    enabled=True,
                    extraction_model=getattr(
                        _config, "episodic_extraction_model", "claude-3-haiku-20240307"
                    ),
                )
                tracker.start_sweeper()
                _proxy.episodic_tracker = tracker
            else:
                tracker._enabled = True
                tracker.start_sweeper()
        elif tracker is not None:
            tracker._enabled = False
            tracker.stop_sweeper()

    def _apply_orchestrator_toggle(value: bool) -> None:
        _set_flag_on_config("orchestrator", value)
        model_router = getattr(_proxy, "_model_router", None)
        try:
            from cutctx.proxy.model_router import ModelRouter, ModelRouterConfig

            # Dashboard activation must be useful without a separate env-var
            # deployment.  Previously this created the legacy router when no
            # preset was configured, which has no GPT-5.6 -> Mini route.
            preset = getattr(_config, "model_routing_preset", None) or "codex-gpt54mini-high"
            preset_config = ModelRouterConfig.from_preset_name(preset)
            if preset_config is not None:
                _config.model_routing_preset = preset
                preset_config.enabled = value
                _proxy._model_router = ModelRouter(config=preset_config)
                return

            if model_router is None:
                model_router = ModelRouter()
                _proxy._model_router = model_router
        except Exception:
            model_router = None
        if model_router is not None and getattr(model_router, "config", None) is not None:
            model_router.config.enabled = value

    @router.get(
        "/config/flags",
        dependencies=[_Dep(require_admin_auth)],
    )
    async def get_config_flags():
        """Return current feature flag states defaults + runtime overrides."""
        from cutctx.proxy.intelligence_pipeline import get_all_runtime_flags

        runtime = get_all_runtime_flags()
        return {
            "live_toggleable": {k: _flag_state(k, runtime) for k in sorted(_LIVE_TOGGLE_KEYS)},
            "restart_required": {
                k: _flag_state(k, runtime) for k in sorted(_RESTART_REQUIRED_KEYS)
            },
            "legacy_aliases": _LEGACY_FLAG_ALIASES,
            "runtime_overrides": runtime,
        }

    @router.post(
        "/config/flags",
        dependencies=[_Dep(require_admin_auth)],
    )
    async def set_config_flags(body: dict, request: Request):
        """
        Toggle feature flags for the dashboard.

        Live-toggleable features apply to the next request immediately.
        Restart-required features update desired config and surface the restart hint.
        """
        from cutctx.proxy.intelligence_pipeline import set_runtime_flag

        applied_live: dict[str, Any] = {}
        needs_restart: dict[str, Any] = {}
        unknown: dict[str, str] = {}
        runtime_keys = {
            "task_aware_enabled",
            "dedup_enabled",
            "context_budget_enabled",
            "profiles_enabled",
            "shared_context_enabled",
            "cost_forecast_enabled",
            "autopilot_enabled",
        }

        for raw_key, value in body.items():
            key = _normalize_flag_key(raw_key)
            enabled = bool(value)

            entitlement_feature = _FLAG_ENTITLEMENTS.get(key)
            if entitlement_feature is not None:
                await require_entitlement(entitlement_feature)(request)

            if key in _LIVE_TOGGLE_KEYS:
                if key in runtime_keys:
                    set_runtime_flag(key, enabled)
                    _set_flag_on_config(key, enabled)
                elif key == "episodic_memory_enabled":
                    _apply_episodic_memory_toggle(enabled)
                elif key == "orchestrator":
                    _apply_orchestrator_toggle(enabled)
                elif key == "ccr_context_tracking":
                    _set_flag_on_config(key, enabled)

                applied_live[key] = {"enabled": enabled}
                if raw_key != key:
                    applied_live[raw_key] = {"enabled": enabled, "normalized_to": key}
                continue

            if key in _RESTART_REQUIRED_KEYS:
                _set_flag_on_config(key, enabled)
                needs_restart[key] = {
                    "requested": enabled,
                    "current": bool(_flag_state(key, {}).get("enabled")),
                    "env_var": _RESTART_ENV_VARS.get(key, key.upper()),
                }
                if raw_key != key:
                    needs_restart[raw_key] = {"requested": enabled, "normalized_to": key}
                continue

            unknown[raw_key] = "unknown flag"

        return {
            "applied_live": applied_live,
            "restart_required": needs_restart,
            "unknown": unknown,
        }

    @router.get(
        "/policy/status",
        dependencies=[_Dep(require_admin_auth), _Dep(require_rbac_permission("stats.read"))],
    )
    async def policy_status():
        """Get the active provider-aware savings policy decision (Phase 3.3)."""
        try:
            from cutctx.savings import StrategyResolver, WorkloadClass

            workload = getattr(_config, "workload_class", "unknown")
            try:
                workload_cls = WorkloadClass.from_str(workload)
            except Exception:
                workload_cls = WorkloadClass.UNKNOWN

            resolver = StrategyResolver()
            # Show one example decision for each major provider so the
            # operator can see what the policy engine produces.
            examples = {}
            for provider in ("anthropic", "openai", "gemini"):
                d = resolver.resolve(
                    provider=provider,
                    model=None,
                    workload=workload_cls,
                )
                examples[provider] = d.to_dict()
            return {
                "workload_class": workload,
                "resolver_disabled": False,
                "provider_decisions": examples,
                "description": (
                    "Provider-aware policy engine. When "
                    "preserve_prefix_for_provider_cache is true the "
                    "compression path leaves the cache-friendly prefix "
                    "intact. When semantic_cache_enabled is true the "
                    "system tries to short-circuit repeated queries."
                ),
            }
        except Exception:
            return {"resolver_disabled": True, "error": "Unable to validate savings profile"}

    # ── Subscription / Quota / Metrics ────────────────────────────────

    @router.get(
        "/subscription-window",
        dependencies=[_Dep(require_admin_auth), _Dep(require_rbac_permission("stats.read"))],
    )
    async def subscription_window():
        """Current Anthropic subscription window utilisation."""
        try:
            from cutctx.proxy.subscription import get_subscription_tracker

            tracker = get_subscription_tracker()
        except ImportError:
            tracker = None
        if tracker is None:
            return JSONResponse(
                status_code=503,
                content={"error": "Subscription tracking is not enabled"},
            )
        await tracker.maybe_poll_on_demand()
        return JSONResponse(content=tracker.render_state())

    @router.get(
        "/quota",
        dependencies=[_Dep(require_admin_auth), _Dep(require_rbac_permission("stats.read"))],
    )
    async def quota():
        """Unified quota/rate-limit stats for all registered providers."""
        from cutctx.subscription.base import get_quota_registry

        return JSONResponse(content=get_quota_registry().get_all_stats())

    @router.get(
        "/metrics",
        dependencies=[_Dep(require_admin_auth), _Dep(require_rbac_permission("stats.read"))],
    )
    async def metrics():
        """Prometheus metrics endpoint."""
        return PlainTextResponse(
            await _proxy.metrics.export(),
            media_type="text/plain; version=0.0.4",
        )

    # ── Cache ─────────────────────────────────────────────────────────

    @router.post(
        "/cache/clear",
        dependencies=[_Dep(require_admin_auth), _Dep(require_rbac_permission("cache.write"))],
    )
    async def clear_cache():
        """Clear the response cache."""
        if _proxy.cache:
            await _proxy.cache.clear()
            return {"status": "cleared"}
        return {"status": "cache disabled"}

    # ── CCR (Compress-Cache-Retrieve) ─────────────────────────────────

    @router.post(
        "/v1/retrieve",
        dependencies=[_Dep(require_admin_auth), _Dep(require_entitlement("ccr"))],
    )
    async def ccr_retrieve(request: Request):
        """Retrieve original content from CCR compression cache."""
        from cutctx.cache.compression_store import (
            format_retrieval_miss_detail,
            get_compression_store,
        )

        data = await request.json()
        hash_key = data.get("hash")
        query = data.get("query")

        if not hash_key:
            raise HTTPException(status_code=400, detail="hash required")

        store = get_compression_store()

        entry_status = store.get_entry_status(hash_key, clean_expired=True)
        if entry_status["status"] != "available":
            raise HTTPException(
                status_code=404,
                detail=format_retrieval_miss_detail(entry_status),
            )

        if query:
            results = store.search(hash_key, query)
            return {
                "hash": hash_key,
                "query": query,
                "results": results,
                "count": len(results),
            }
        else:
            entry = store.retrieve(hash_key)
            if entry:
                return {
                    "hash": hash_key,
                    "original_content": entry.original_content,
                    "original_tokens": entry.original_tokens,
                    "original_item_count": entry.original_item_count,
                    "compressed_item_count": entry.compressed_item_count,
                    "tool_name": entry.tool_name,
                    "retrieval_count": entry.retrieval_count,
                }
            raise HTTPException(
                status_code=404,
                detail=format_retrieval_miss_detail(
                    store.get_entry_status(hash_key, clean_expired=True)
                ),
            )

    @router.get(
        "/v1/retrieve/stats",
        dependencies=[_Dep(require_admin_auth), _Dep(require_entitlement("ccr"))],
    )
    async def ccr_stats():
        """Get CCR compression store statistics."""
        from cutctx.cache.compression_store import get_compression_store

        store = get_compression_store()
        stats = store.get_stats()
        events = store.get_retrieval_events(limit=20)
        return {
            "store": stats,
            "recent_retrievals": [
                {
                    "hash": e.hash,
                    "query": e.query,
                    "items_retrieved": e.items_retrieved,
                    "total_items": e.total_items,
                    "tool_name": e.tool_name,
                    "retrieval_type": e.retrieval_type,
                }
                for e in events
            ],
        }

    @router.get(
        "/v1/feedback",
        dependencies=[_Dep(require_admin_auth), _Dep(require_entitlement("ccr"))],
    )
    async def ccr_feedback():
        """Get CCR feedback loop statistics and learned patterns."""
        from cutctx.cache.compression_feedback import get_compression_feedback

        feedback = get_compression_feedback()
        stats = feedback.get_stats()
        return {
            "feedback": stats,
            "hints_example": {
                tool_name: {
                    "hints": {
                        "max_items": hints.max_items
                        if (hints := feedback.get_compression_hints(tool_name))
                        else 15,
                        "suggested_items": hints.suggested_items if hints else None,
                        "skip_compression": hints.skip_compression if hints else False,
                        "preserve_fields": hints.preserve_fields if hints else [],
                        "reason": hints.reason if hints else "",
                    }
                }
                for tool_name in list(stats.get("tool_patterns", {}).keys())[:5]
            },
        }

    @router.get(
        "/v1/feedback/{tool_name}",
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("stats.read")),
            _Dep(require_entitlement("ccr")),
        ],
    )
    async def ccr_feedback_for_tool(tool_name: str):
        """Get compression hints for a specific tool."""
        from cutctx.cache.compression_feedback import get_compression_feedback

        feedback = get_compression_feedback()
        hints = feedback.get_compression_hints(tool_name)
        patterns = feedback.get_all_patterns().get(tool_name)

        return {
            "tool_name": tool_name,
            "hints": {
                "max_items": hints.max_items,
                "min_items": hints.min_items,
                "suggested_items": hints.suggested_items,
                "aggressiveness": hints.aggressiveness,
                "skip_compression": hints.skip_compression,
                "preserve_fields": hints.preserve_fields,
                "reason": hints.reason,
            },
            "pattern": {
                "total_compressions": patterns.total_compressions if patterns else 0,
                "total_retrievals": patterns.total_retrievals if patterns else 0,
                "retrieval_rate": patterns.retrieval_rate if patterns else 0.0,
                "full_retrieval_rate": patterns.full_retrieval_rate if patterns else 0.0,
                "search_rate": patterns.search_rate if patterns else 0.0,
                "common_queries": list(patterns.common_queries.keys())[:10] if patterns else [],
                "queried_fields": list(patterns.queried_fields.keys())[:10] if patterns else [],
            }
            if patterns
            else None,
        }

    # ── Telemetry (Data Flywheel) ─────────────────────────────────────

    @router.get(
        "/v1/telemetry",
        dependencies=[_Dep(require_admin_auth), _Dep(require_rbac_permission("stats.read"))],
    )
    async def telemetry_stats():
        """Get telemetry statistics for the data flywheel."""
        from cutctx.cache.compression_store import get_telemetry_collector

        telemetry = get_telemetry_collector()
        return telemetry.get_stats()

    @router.get(
        "/v1/telemetry/export",
        dependencies=[_Dep(require_admin_auth), _Dep(require_rbac_permission("stats.read"))],
    )
    async def telemetry_export():
        """Export full telemetry data for aggregation."""
        from cutctx.cache.compression_store import get_telemetry_collector

        telemetry = get_telemetry_collector()
        return telemetry.export_stats()

    @router.post(
        "/v1/telemetry/import",
        dependencies=[_Dep(require_admin_auth), _Dep(require_rbac_permission("stats.write"))],
    )
    async def telemetry_import(request: Request):
        """Import telemetry data from another source."""
        from cutctx.cache.compression_store import get_telemetry_collector

        telemetry = get_telemetry_collector()
        data = await request.json()
        if not isinstance(data, dict):
            raise HTTPException(status_code=400, detail="Request body must be a JSON object")
        if "tool_patterns" in data and not isinstance(data["tool_patterns"], dict):
            raise HTTPException(status_code=400, detail="tool_patterns must be a JSON object")
        telemetry.import_stats(data)
        return {"status": "imported", "current_stats": telemetry.get_stats()}

    @router.get(
        "/v1/telemetry/tools",
        dependencies=[_Dep(require_admin_auth), _Dep(require_rbac_permission("stats.read"))],
    )
    async def telemetry_tools():
        """Get telemetry statistics for all tracked tool signatures."""
        from cutctx.cache.compression_store import get_telemetry_collector

        telemetry = get_telemetry_collector()
        all_stats = telemetry.get_all_tool_stats()
        return {
            "tool_count": len(all_stats),
            "tools": {sig_hash: stats.to_dict() for sig_hash, stats in all_stats.items()},
        }

    @router.get(
        "/v1/telemetry/tools/{signature_hash}",
        dependencies=[_Dep(require_admin_auth), _Dep(require_rbac_permission("stats.read"))],
    )
    async def telemetry_tool_detail(signature_hash: str):
        """Get detailed telemetry for a specific tool signature."""
        from cutctx.cache.compression_store import get_telemetry_collector

        telemetry = get_telemetry_collector()
        stats = telemetry.get_tool_stats(signature_hash)
        recommendations = telemetry.get_recommendations(signature_hash)

        if stats is None:
            raise HTTPException(
                status_code=404, detail=f"No telemetry found for signature: {signature_hash}"
            )

        return {
            "signature_hash": signature_hash,
            "stats": stats.to_dict(),
            "recommendations": recommendations,
        }

    # ── TOIN (Tool Output Intelligence Network) ───────────────────────

    @router.get(
        "/v1/toin/stats",
        dependencies=[_Dep(require_admin_auth), _Dep(require_rbac_permission("stats.read"))],
    )
    async def toin_stats():
        """Get overall TOIN statistics."""
        from cutctx.cache.compression_store import get_toin

        toin = get_toin()
        return toin.get_stats()

    @router.get(
        "/v1/toin/patterns",
        dependencies=[_Dep(require_admin_auth), _Dep(require_rbac_permission("stats.read"))],
    )
    async def toin_patterns(limit: int = 20):
        """List TOIN patterns with most samples."""
        from cutctx.cache.compression_store import get_toin

        toin = get_toin()
        exported = toin.export_patterns()
        patterns_data = exported.get("patterns", {})

        patterns_list = []
        for sig_hash, pattern_dict in patterns_data.items():
            sample_size = pattern_dict.get("sample_size", 0)
            total_compressions = pattern_dict.get("total_compressions", 0)
            total_retrievals = pattern_dict.get("total_retrievals", 0)
            retrieval_rate = (
                total_retrievals / total_compressions if total_compressions > 0 else 0.0
            )

            patterns_list.append(
                {
                    "hash": sig_hash[:12],
                    "compressions": total_compressions,
                    "retrievals": total_retrievals,
                    "retrieval_rate": f"{retrieval_rate:.1%}",
                    "confidence": round(pattern_dict.get("confidence", 0.0), 3),
                    "skip_recommended": pattern_dict.get("skip_compression_recommended", False),
                    "optimal_max_items": pattern_dict.get("optimal_max_items", 20),
                    "sample_size": sample_size,
                }
            )

        patterns_list.sort(key=lambda p: p["sample_size"], reverse=True)

        for p in patterns_list:
            del p["sample_size"]

        return patterns_list[:limit]

    @router.get(
        "/v1/toin/pattern/{hash_prefix}",
        dependencies=[_Dep(require_admin_auth), _Dep(require_rbac_permission("stats.read"))],
    )
    async def toin_pattern_detail(hash_prefix: str):
        """Get detailed TOIN pattern info by hash prefix."""
        from cutctx.cache.compression_store import get_toin

        toin = get_toin()
        exported = toin.export_patterns()
        patterns_data = exported.get("patterns", {})

        for sig_hash, pattern_dict in patterns_data.items():
            if sig_hash.startswith(hash_prefix):
                return pattern_dict

        raise HTTPException(
            status_code=404, detail=f"No TOIN pattern found with hash starting with: {hash_prefix}"
        )

    # ── CCR Retrieve (GET and tool_call) ──────────────────────────────

    @router.get(
        "/v1/retrieve/{hash_key}",
        dependencies=[_Dep(require_admin_auth), _Dep(require_entitlement("ccr"))],
    )
    async def ccr_retrieve_get(hash_key: str, query: str | None = None):
        """GET version of CCR retrieve for easier testing."""
        from cutctx.cache.compression_store import (
            format_retrieval_miss_detail,
            get_compression_store,
        )

        store = get_compression_store()
        entry_status = store.get_entry_status(hash_key, clean_expired=True)

        if entry_status["status"] != "available":
            raise HTTPException(
                status_code=404,
                detail=format_retrieval_miss_detail(entry_status),
            )

        if query:
            results = store.search(hash_key, query)
            return {
                "hash": hash_key,
                "query": query,
                "results": results,
                "count": len(results),
            }
        else:
            entry = store.retrieve(hash_key)
            if entry:
                return {
                    "hash": hash_key,
                    "original_content": entry.original_content,
                    "original_tokens": entry.original_tokens,
                    "original_item_count": entry.original_item_count,
                    "compressed_item_count": entry.compressed_item_count,
                    "tool_name": entry.tool_name,
                    "retrieval_count": entry.retrieval_count,
                }
            raise HTTPException(
                status_code=404,
                detail=format_retrieval_miss_detail(
                    store.get_entry_status(hash_key, clean_expired=True)
                ),
            )

    @router.post(
        "/v1/retrieve/tool_call",
        dependencies=[_Dep(require_admin_auth), _Dep(require_entitlement("ccr"))],
    )
    async def ccr_handle_tool_call(request: Request):
        """Handle a CCR tool call from an LLM response."""
        from cutctx.cache.compression_store import (
            CCR_TOOL_NAME,
            format_retrieval_miss_detail,
            get_compression_store,
            parse_tool_call,
        )

        data = await request.json()
        tool_call = data.get("tool_call", {})
        provider = data.get("provider", "anthropic")

        hash_key, query = parse_tool_call(tool_call, provider)

        if hash_key is None:
            raise HTTPException(
                status_code=400, detail=f"Invalid tool call or not a {CCR_TOOL_NAME} call"
            )

        store = get_compression_store()
        entry_status = store.get_entry_status(hash_key, clean_expired=True)

        if entry_status["status"] != "available":
            retrieval_data = {
                "error": format_retrieval_miss_detail(entry_status),
                "hash": hash_key,
                "status": entry_status["status"],
                "ttl_seconds": entry_status.get("ttl_seconds", entry_status["default_ttl_seconds"]),
            }
        elif query:
            results = store.search(hash_key, query)
            retrieval_data = {
                "hash": hash_key,
                "query": query,
                "results": results,
                "count": len(results),
            }
        else:
            entry = store.retrieve(hash_key)
            if entry:
                retrieval_data = {
                    "hash": hash_key,
                    "original_content": entry.original_content,
                    "original_item_count": entry.original_item_count,
                    "compressed_item_count": entry.compressed_item_count,
                }
            else:
                miss_status = store.get_entry_status(hash_key, clean_expired=True)
                retrieval_data = {
                    "error": format_retrieval_miss_detail(miss_status),
                    "hash": hash_key,
                    "status": miss_status["status"],
                    "ttl_seconds": miss_status.get(
                        "ttl_seconds", miss_status["default_ttl_seconds"]
                    ),
                }

        tool_call_id = tool_call.get("id", "")
        result_content = json.dumps(retrieval_data, indent=2)

        if provider == "anthropic":
            tool_result = {
                "type": "tool_result",
                "tool_use_id": tool_call_id,
                "content": result_content,
            }
        elif provider == "openai":
            tool_result = {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": result_content,
            }
        else:
            tool_result = {
                "tool_call_id": tool_call_id,
                "content": result_content,
            }

        return {
            "tool_result": tool_result,
            "success": "error" not in retrieval_data,
            "data": retrieval_data,
        }

    # ── Compression-only endpoint ─────────────────────────────────────

    @router.post(
        "/v1/compress",
        dependencies=[_Dep(require_admin_auth)],
    )
    async def compress_messages(request: Request):
        return await _proxy.handle_compress(request)

    # ── Analytics Dashboard Rollups ───────────────────────────────────

    @router.get(
        "/analytics/dashboard",
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("stats.read")),
            _Dep(require_entitlement("team_analytics")),
        ],
    )
    async def analytics_dashboard(org_id: str | None = None):
        """Aggregated dashboard view: key metrics, trends, and health score."""
        m = _proxy.metrics
        cost_stats = _proxy.cost_tracker.stats() if _proxy.cost_tracker else {}
        total_before = m.tokens_input_total + m.tokens_saved_total
        savings_pct = round(m.tokens_saved_total / max(1, total_before) * 100, 2)

        error_rate = m.requests_failed / max(1, m.requests_total) * 100
        avg_latency = m.latency_sum_ms / max(1, m.latency_count)
        health_score = max(
            0,
            min(
                100,
                round(
                    savings_pct * 0.5
                    + (100 - min(error_rate, 100)) * 0.3
                    + max(0, 100 - avg_latency / 10) * 0.2,
                    1,
                ),
            ),
        )

        result = {
            "health_score": health_score,
            "tokens": {
                "input": m.tokens_input_total,
                "output": m.tokens_output_total,
                "saved": m.tokens_saved_total,
                "savings_percent": savings_pct,
            },
            "cost": {
                "total_usd": cost_stats.get("total_cost_usd", 0.0),
                "saved_usd": cost_stats.get("total_savings_usd", 0.0),
            },
            "requests": {
                "total": m.requests_total,
                "cached": m.requests_cached,
                "failed": m.requests_failed,
                "error_rate_percent": round(error_rate, 2),
            },
            "latency": {
                "avg_ms": round(avg_latency, 2),
                "min_ms": round(m.latency_min_ms, 2) if m.latency_min_ms != float("inf") else 0,
                "max_ms": round(m.latency_max_ms, 2),
            },
            "top_providers": dict(sorted(m.requests_by_provider.items(), key=lambda x: -x[1])[:5]),
            "top_models": dict(sorted(m.requests_by_model.items(), key=lambda x: -x[1])[:5]),
            "top_strategies": dict(
                sorted(m.compressions_by_strategy.items(), key=lambda x: -x[1])[:5]
            ),
            "generated_at": _iso_utc_now(),
        }

        if org_id and _proxy.org_store:
            try:
                hierarchy = _proxy.org_store.get_org_hierarchy(org_id)
                if hierarchy:
                    result["scope"] = {
                        "org_id": org_id,
                        "org_name": hierarchy.get("name", ""),
                        "workspaces": len(hierarchy.get("workspaces", [])),
                        "projects": sum(
                            len(ws.get("projects", [])) for ws in hierarchy.get("workspaces", [])
                        ),
                    }
                else:
                    result["scope"] = {"org_id": org_id, "error": "org_not_found"}
            except Exception:
                result["scope"] = {"org_id": org_id, "error": "lookup_failed"}

        return result

    @router.get(
        "/analytics/projects",
        dependencies=[
            _Dep(require_admin_auth),
            _Dep(require_rbac_permission("orgs.read")),
            _Dep(require_entitlement("project_model")),
        ],
    )
    async def analytics_projects(org_id: str | None = None):
        """Per-project token savings breakdown."""
        persistent = _proxy.metrics.savings_tracker.stats_preview()
        projects = persistent.get("projects", {})

        org_project_paths: set[str] = set()
        if org_id and _proxy.org_store:
            try:
                hierarchy = _proxy.org_store.get_org_hierarchy(org_id)
                if hierarchy:
                    for ws in hierarchy.get("workspaces", []):
                        for proj in ws.get("projects", []):
                            if proj.get("path"):
                                org_project_paths.add(proj["path"])
                            org_project_paths.add(proj.get("name", ""))
            except Exception:
                pass

        project_list = []
        for name, data in projects.items():
            if org_project_paths and name not in org_project_paths:
                continue
            project_list.append(
                {
                    "name": name,
                    "tokens_saved": data.get("tokens_saved", 0),
                    "requests": data.get("requests", 0),
                    "avg_savings_percent": data.get("avg_savings_percent", 0),
                }
            )

        project_list.sort(key=lambda p: p["tokens_saved"], reverse=True)

        result = {
            "projects": project_list,
            "total_projects": len(project_list),
            "generated_at": _iso_utc_now(),
        }
        if org_id:
            result["scope"] = {"org_id": org_id}
        return result

    return router
