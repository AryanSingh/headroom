"""Behavior-driven Playwright validation for dashboard Governance tab."""

from __future__ import annotations

import json

import pytest

from cutctx.dashboard import get_dashboard_html

playwright = pytest.importorskip("playwright.sync_api")
Page = playwright.Page
expect = playwright.expect
sync_playwright = playwright.sync_playwright


def _install_dashboard_routes(
    page: Page,
    stats_payload: dict,
    sections_payload: dict,
    *,
    entitlements_features: dict | None = None,
    config_flags_post: tuple[int, dict] | None = None,
) -> None:
    dashboard_html = get_dashboard_html(prefer_react=True)

    def handler(route) -> None:  # type: ignore[no-untyped-def]
        url = route.request.url

        if "cutctx.local" not in url:
            route.fulfill(status=200, body="")
            return

        if (
            url.endswith("/governance")
            or url.endswith("/dashboard")
            or url == "http://cutctx.local/"
        ):
            route.fulfill(status=200, content_type="text/html", body=dashboard_html)
            return

        if "/assets/" in url:
            from pathlib import Path

            root_dir = Path(__file__).parent.parent
            asset_rel = url.split("cutctx.local/")[1]
            if asset_rel.startswith("dashboard/"):
                asset_rel = asset_rel[len("dashboard/") :]
            asset_path = root_dir / "cutctx/dashboard" / asset_rel
            if asset_path.exists():
                mime = "text/javascript" if url.endswith(".js") else "text/css"
                route.fulfill(
                    status=200,
                    content_type=mime,
                    body=asset_path.read_bytes(),
                    headers={"Access-Control-Allow-Origin": "*"},
                )
                return

        if "/stats" in url:
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(stats_payload),
            )
            return

        if "/health" in url:
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"status": "ok", "checks": {"rate_limiter": {"ready": True}}}),
            )
            return

        if "/config/flags" in url:
            if route.request.method == "POST" and config_flags_post is not None:
                status, body = config_flags_post
                route.fulfill(
                    status=status,
                    content_type="application/json",
                    body=json.dumps(body),
                )
                return
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "live_toggleable": {
                            "orchestrator": {"enabled": True},
                            "task_aware_enabled": {"enabled": False},
                            "episodic_memory_enabled": {"enabled": False},
                        },
                        "restart_required": {
                            "rate_limit_enabled": {"enabled": True},
                            "audit_enabled": {"enabled": True},
                        },
                    }
                ),
            )
            return

        if "/entitlements" in url:
            if entitlements_features is not None:
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"current_tier": "builder", "features": entitlements_features}),
                )
                return
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "current_tier": "builder",
                        "features": {
                            "episodic_memory": {
                                "available": False,
                                "required_tier": "business",
                            },
                            "cross_agent_memory": {
                                "available": False,
                                "required_tier": "business",
                            },
                            "audit_logs": {
                                "available": False,
                                "required_tier": "enterprise",
                            },
                            "rbac": {
                                "available": False,
                                "required_tier": "enterprise",
                            },
                        },
                    }
                ),
            )
            return

        for endpoint in ["/audit/events", "/rbac/roles"]:
            if endpoint in url:
                key = "audit" if endpoint.endswith("events") else "rbac"
                section = sections_payload.get(key)
                if section is None:
                    route.fulfill(
                        status=403,
                        content_type="application/json",
                        body=json.dumps({"detail": {"error": "feature_not_available"}}),
                    )
                else:
                    route.fulfill(
                        status=200,
                        content_type="application/json",
                        body=json.dumps(section),
                    )
                return

        route.fulfill(status=404, body="Not Found")

    page.route("**/*", handler)


def test_governance_ui_e2e() -> None:
    stats = {
        "config": {
            "orchestrator": True,
            "rate_limiter": True,
        },
        "rate_limiter": None,
        "cost": {
            "budget": {
                "enabled": True,
                "period": "daily",
                "limit_usd": 25.0,
                "spent_usd": 8.75,
                "remaining_usd": 16.25,
                "allowed": True,
                "exceeded": False,
                "percent_used": 35.0,
            }
        },
    }
    sections = {"audit": None, "rbac": None}

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1720, "height": 1400}, color_scheme="dark")

        _install_dashboard_routes(page, stats, sections)
        page.goto("http://cutctx.local/dashboard/governance", wait_until="commit")

        expect(page.get_by_text("Rate limiting").first).to_be_visible(timeout=5000)
        expect(
            page.get_by_text("Some governance surfaces could not be reached")
        ).not_to_be_visible()

        rate_limit_panel = page.locator(".panel").filter(has_text="Rate limiting")
        budget_panel = page.locator(".panel").filter(has_text="Cost budget")

        expect(rate_limit_panel.locator(".metric-card").filter(has_text="Status")).to_contain_text(
            "Configured"
        )
        expect(
            rate_limit_panel.locator(".metric-card").filter(has_text="Token limit")
        ).to_contain_text("-")
        expect(page.get_by_text("Cost budget").first).to_be_visible()
        expect(
            budget_panel.locator(".metric-card").filter(has_text="Budget limit")
        ).to_contain_text("$25.00")
        expect(budget_panel.locator(".metric-card").filter(has_text="Spend used")).to_contain_text(
            "$8.750"
        )
        expect(budget_panel.locator(".metric-card").filter(has_text="Remaining")).to_contain_text(
            "$16.25"
        )

        orchestrator_row = page.locator(".feature-config-row").filter(has_text="Routing mode")
        expect(orchestrator_row).to_contain_text("Routing mode")
        expect(orchestrator_row).to_contain_text(
            "Choose Off, Balanced, or Aggressive on the dedicated routing page."
        )
        expect(orchestrator_row).to_contain_text("CUTCTX_MODEL_ROUTING_PRESET=codex-gpt54mini-high")
        expect(orchestrator_row).to_contain_text("Open routing page")
        expect(orchestrator_row.locator(".feature-toggle")).to_have_count(0)

        episodic_row = page.locator(".feature-config-row").filter(has_text="Episodic memory")
        expect(episodic_row).to_contain_text("Business")
        expect(episodic_row).to_contain_text("Unavailable")
        expect(episodic_row).to_contain_text("Available on Business tier")
        expect(episodic_row.locator(".feature-toggle")).to_be_disabled()

        audit_row = page.locator(".feature-config-row").filter(has_text="Audit trail")
        expect(audit_row).to_contain_text("Unavailable")

        expect(page.locator(".graphify-kv").filter(has_text="Status").first).to_contain_text(
            "Unavailable on builder tier"
        )

        browser.close()


def test_gated_toggle_surfaces_entitlement_error_when_proxy_refuses() -> None:
    """When tier metadata is unavailable and the proxy answers a toggle with
    403 feature_not_available, the row must explain the refusal instead of
    silently doing nothing (the audit found the error was swallowed)."""
    stats = {"config": {"orchestrator": False, "rate_limiter": False}, "cost": {}}
    sections = {"audit": None, "rbac": None}

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1720, "height": 1400}, color_scheme="dark")

        _install_dashboard_routes(
            page,
            stats,
            sections,
            entitlements_features={},
            config_flags_post=(
                403,
                {
                    "detail": {
                        "error": "feature_not_available",
                        "feature": "episodic_memory",
                        "required_tier": "business",
                        "current_tier": "builder",
                    }
                },
            ),
        )
        page.goto("http://cutctx.local/dashboard/governance", wait_until="commit")

        episodic_row = page.locator(".feature-config-row").filter(has_text="Episodic memory")
        expect(episodic_row.locator(".feature-toggle")).to_be_enabled(timeout=5000)
        episodic_row.locator(".feature-toggle").click()

        alert = episodic_row.locator(".feature-config-error")
        expect(alert).to_be_visible(timeout=5000)
        expect(alert).to_contain_text("requires the Business tier")
        expect(alert).to_contain_text("current tier: Builder")
        browser.close()
