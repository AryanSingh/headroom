"""Behavior-driven Playwright validation for dashboard Capabilities toggles."""

from __future__ import annotations

import json
import pytest

from cutctx.dashboard import get_dashboard_html

playwright = pytest.importorskip("playwright.sync_api")
Page = playwright.Page
expect = playwright.expect
sync_playwright = playwright.sync_playwright


def _install_dashboard_routes(page: Page, stats_payload: dict, flags_callback) -> None:
    dashboard_html = get_dashboard_html(prefer_react=True)

    def handler(route) -> None:  # type: ignore[no-untyped-def]
        url = route.request.url
        
        if "cutctx.local" not in url:
            route.fulfill(status=200, body="")
            return
            
        if url.endswith("/capabilities") or url.endswith("/dashboard") or url == "http://cutctx.local/":
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
        
        if "/admin/config/flags" in url and route.request.method == "POST":
            # Record the payload
            payload = json.loads(route.request.post_data or "{}")
            flags_callback(payload)
            route.fulfill(status=200, content_type="application/json", body=json.dumps({"success": True}))
            return

        if "/stats" in url:
            route.fulfill(status=200, content_type="application/json", body=json.dumps(stats_payload))
            return
            
        if "/health" in url:
            route.fulfill(status=200, content_type="application/json", body=json.dumps({"status": "ok"}))
            return
            
        # fallback for everything else to avoid hanging on fake domain
        route.fulfill(status=404, body="Not Found")

    page.route("**/*", handler)

def test_capabilities_toggles_e2e() -> None:
    stats = {
        "config": {
            "cache": False,
            "ccr": False,
            "memory": False,
            "firewall": False,
            "rate_limiter": False,
        }
    }
    
    posted_flags = []
    def on_flags(payload):
        posted_flags.append(payload)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1720, "height": 1400}, color_scheme="dark")
        
        _install_dashboard_routes(page, stats, on_flags)
        
        page.goto("http://cutctx.local/dashboard", wait_until="commit")
        
        # Click on the capabilities tab
        page.locator("a[href='/dashboard/capabilities']").first.click()
        
        # Verify the modules are shown
        expect(page.get_by_text("Episodic memory").first).to_be_visible(timeout=5000)
        expect(page.get_by_text("Firewall").first).to_be_visible()

        # Both should initially show "Idle" because they are False in config
        memory_card = page.locator(".metric-card").filter(has_text="Episodic memory")
        firewall_card = page.locator(".metric-card").filter(has_text="Firewall")
        
        expect(memory_card.locator(".status-inactive")).to_have_text("Idle")
        expect(firewall_card.locator(".status-inactive")).to_have_text("Idle")

        # Click the toggles
        memory_card = page.locator(".metric-card").filter(has_text="Episodic memory")
        memory_card.locator(".toggle-switch").click()
        firewall_card.locator(".toggle-switch").click()
        
        # Wait for the API posts
        page.wait_for_timeout(1000)
        
        assert len(posted_flags) >= 2
        assert any("memory" in payload and payload["memory"] is True for payload in posted_flags)
        assert any("firewall" in payload and payload["firewall"] is True for payload in posted_flags)
        
        # Assert they instantly show "Active"
        expect(memory_card.locator(".status-active")).to_have_text("Active")
        expect(firewall_card.locator(".status-active")).to_have_text("Active")

        browser.close()
