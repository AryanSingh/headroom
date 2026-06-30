"""Behavior-driven Playwright validation for dashboard tab surfaces."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from cutctx.dashboard import get_dashboard_html

playwright = pytest.importorskip("playwright.sync_api")
Page = playwright.Page
expect = playwright.expect
sync_playwright = playwright.sync_playwright


def _install_dashboard_routes(page: Page) -> None:
    dashboard_html = get_dashboard_html(prefer_react=True)
    root_dir = Path(__file__).parent.parent

    def handler(route) -> None:  # type: ignore[no-untyped-def]
        url = route.request.url
        
        if "cutctx.local" not in url:
            route.fulfill(status=200, body="")
            return
            
        if url.endswith("/dashboard") or url.endswith("/") or url.endswith("playground") or url.endswith("firewall") or url.endswith("governance") or url.endswith("memory") or url == "http://cutctx.local/":
            # For react router SPA, we serve the same HTML
            route.fulfill(status=200, content_type="text/html", body=dashboard_html)
            return
            
        if "/assets/" in url:
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
        
        # mock all API requests
        if "/stats" in url:
            route.fulfill(status=200, content_type="application/json", body="{}")
            return
            
        # fallback for everything else to avoid hanging on fake domain
        route.fulfill(status=404, body="Not Found")

    page.route("**/*", handler)

def test_dashboard_surfaces_render_correctly() -> None:
    artifact_dir = os.environ.get("CUTCTX_PLAYWRIGHT_ARTIFACT_DIR")

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1720, "height": 1400}, color_scheme="dark")
        
        _install_dashboard_routes(page)
        
        # Start at dashboard
        page.goto("http://cutctx.local/dashboard", wait_until="commit")
        
        # Wait for React to mount
        page.wait_for_selector(".sidebar-shell", timeout=5000)
        
        # Click Governance tab
        page.get_by_text("Governance", exact=True).click()
        expect(page.get_by_role("heading", name="Governance", exact=True)).to_be_visible()
        # Check toggles in Governance
        expect(page.get_by_text("Task-aware compression", exact=True)).to_be_visible()
        expect(page.get_by_text("Context budget controller", exact=True)).to_be_visible()
        
        # Click Security tab (Firewall)
        page.get_by_text("Security", exact=True).click()
        expect(page.get_by_role("heading", name="Security", exact=True)).to_be_visible()
        # Check firewall elements
        expect(page.get_by_text("PII redaction", exact=True)).to_be_visible()
        expect(page.get_by_text("Prompt injection", exact=True)).to_be_visible()
        
        # Click Memory tab
        page.get_by_text("Memory", exact=True).click()
        expect(page.get_by_role("heading", name="Memory", exact=True)).to_be_visible()
        
        # Click Playground tab
        page.get_by_text("Playground", exact=True).click()
        expect(page.get_by_role("heading", name="Playground", exact=True)).to_be_visible()
        # Check playground inputs
        expect(page.get_by_role("heading", name="Build a compression request", exact=True)).to_be_visible()
        expect(page.get_by_role("button", name="Run live compression", exact=True)).to_be_visible()

        browser.close()
