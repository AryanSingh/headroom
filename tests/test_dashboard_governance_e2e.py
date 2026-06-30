"""Behavior-driven Playwright validation for dashboard Governance tab."""

from __future__ import annotations

import json
import pytest

from cutctx.dashboard import get_dashboard_html

playwright = pytest.importorskip("playwright.sync_api")
Page = playwright.Page
expect = playwright.expect
sync_playwright = playwright.sync_playwright


def _install_dashboard_routes(page: Page, stats_payload: dict, sections_payload: dict) -> None:
    dashboard_html = get_dashboard_html(prefer_react=True)

    def handler(route) -> None:  # type: ignore[no-untyped-def]
        url = route.request.url
        
        if "cutctx.local" not in url:
            route.fulfill(status=200, body="")
            return
            
        if url.endswith("/governance") or url.endswith("/dashboard") or url == "http://cutctx.local/":
            # For react router SPA, we serve the same HTML
            route.fulfill(status=200, content_type="text/html", body=dashboard_html)
            return
            
        if "/assets/" in url:
            from pathlib import Path
            root_dir = Path(__file__).parent.parent
            asset_path = root_dir / "dashboard/dist" / url.split("cutctx.local/")[1]
            if asset_path.exists():
                mime = "text/javascript" if url.endswith(".js") else "text/css"
                route.fulfill(
                    status=200, 
                    content_type=mime, 
                    body=asset_path.read_bytes(),
                    headers={"Access-Control-Allow-Origin": "*"}
                )
                return
        
        if "/stats" in url:
            route.fulfill(status=200, content_type="application/json", body=json.dumps(stats_payload))
            return
            
        if "/health" in url:
            route.fulfill(status=200, content_type="application/json", body=json.dumps({"status": "ok"}))
            return
            
        # Mock governance section endpoints
        for endpoint in ["/audit/events", "/orgs", "/quota", "/rbac/roles", "/retention", "/subscription"]:
            if endpoint in url:
                key = endpoint.split("/")[-1]
                if key == "events":
                    key = "audit"
                if key == "roles":
                    key = "rbac"
                
                # Mock a 403 or 501 for enterprise stubs
                if key in ["orgs", "quota", "retention", "subscription"]:
                    route.fulfill(status=403, content_type="application/json", body=json.dumps({"detail": "Enterprise feature"}))
                else:
                    route.fulfill(status=200, content_type="application/json", body=json.dumps(sections_payload.get(key, {})))
                return
            
        # fallback for everything else
        route.fulfill(status=404, body="Not Found")

    page.route("**/*", handler)

def test_governance_ui_e2e() -> None:
    stats = {
        "config": {
            "rate_limit": True,
            "rate_limiter": True,
        },
        "rate_limiter": {
            "active_keys": 5,
            "total_requests": 150,
            "throttled_requests": 2,
            "total_tokens": 50000
        }
    }
    
    sections = {
        "audit": {"logs": []},
        "rbac": {"roles": []}
    }

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1720, "height": 1400}, color_scheme="dark")
        
        _install_dashboard_routes(page, stats, sections)
        
        page.goto("http://cutctx.local/dashboard/governance", wait_until="commit")
        
        # Verify the section loaded
        expect(page.get_by_text("Rate limiting").first).to_be_visible(timeout=5000)
        
        # Ensure the confusing error banner is suppressed!
        expect(page.locator(".alert-card")).not_to_be_visible()
        
        # Check rate limiter metrics
        expect(page.locator(".metric-card").filter(has_text="Active keys")).to_contain_text("5")
        expect(page.locator(".metric-card").filter(has_text="Request limit")).to_be_visible()

        browser.close()
