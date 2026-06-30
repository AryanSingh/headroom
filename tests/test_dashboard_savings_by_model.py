"""Behavior-driven Playwright validation for dashboard savings by model."""

from __future__ import annotations
import json
import os
from pathlib import Path
import pytest
from cutctx.dashboard import get_dashboard_html

playwright = pytest.importorskip("playwright.sync_api")
Page = playwright.Page
expect = playwright.expect
sync_playwright = playwright.sync_playwright

def _install_dashboard_routes_with_stats(page: Page) -> None:
    dashboard_html = get_dashboard_html(prefer_react=True)
    root_dir = Path(__file__).parent.parent

    mock_stats = {
        "summary": {
            "cost": {
                "per_model": {
                    "gpt-4o": {
                        "tokens_saved": 5000,
                        "savings_usd": 0.025
                    },
                    "claude-3-opus": {
                        "tokens_saved": 10000,
                        "savings_usd": 0.150
                    }
                }
            }
        },
        "tokens": {
            "total_before_compression": 15000,
            "saved": 15000
        },
        "requests": {
            "total": 100
        }
    }

    def handler(route) -> None:
        url = route.request.url
        if "cutctx.local" not in url:
            route.fulfill(status=200, body="")
            return
            
        if url.endswith("/dashboard") or url.endswith("/") or url == "http://cutctx.local/":
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
        
        if url.endswith("/stats") or "/stats?" in url:
            route.fulfill(status=200, content_type="application/json", body=json.dumps(mock_stats))
            return
            
        if url.endswith("/health"):
            route.fulfill(status=200, content_type="application/json", body=json.dumps({"status": "healthy"}))
            return
            
        if "/history" in url:
            route.fulfill(status=200, content_type="application/json", body=json.dumps([]))
            return
            
        route.fulfill(status=404, body="Not Found")

    page.route("**/*", handler)

def test_dashboard_savings_by_model() -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page()
            _install_dashboard_routes_with_stats(page)

            page.goto("http://cutctx.local/dashboard")
            page.wait_for_load_state("networkidle")

            # Check if "Savings by model" header exists
            header = page.locator("h2:has-text('Savings by model')")
            expect(header).to_be_visible(timeout=5000)

            # Check if the models are displayed
            expect(page.locator("text=claude-3-opus").first).to_be_visible()
            expect(page.locator("text=gpt-4o").first).to_be_visible()
            
            # Save screenshot for walkthrough
            page.screenshot(path="/Users/aryansingh/.gemini/antigravity/brain/109383ec-01a4-4dc7-bc11-9f895839864c/savings_by_model_screenshot.png")
            
        finally:
            browser.close()
