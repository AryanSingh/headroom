"""Playwright regression test for lifetime-vs-session dashboard headlines."""

from __future__ import annotations

import json
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

    mock_stats = {
        "summary": {
            "cost": {
                "without_cutctx_usd": 0.0,
                "with_cutctx_usd": 0.0,
                "total_saved_usd": 0.0,
                "breakdown": {
                    "compression_savings_usd": 0.0,
                    "cache_savings_usd": 0.0,
                },
            },
        },
        "tokens": {
            "saved": 1220,
            "savings_percent": 0.05,
            "total_before_compression": 2_545_714,
            "active_savings_percent": 0.05,
            "proxy_savings_percent": 0.05,
        },
        "requests": {
            "total": 17,
            "failed": 0,
            "cached": 0,
        },
        "persistent_savings": {
            "lifetime": {
                "requests": 15_799,
                "tokens_saved": 194_800_000,
                "total_input_tokens": 406_885_406,
                "compression_savings_usd": 472.24,
            },
            "recent_history": [],
        },
        "recent_requests": [],
        "prefix_cache": {"totals": {}},
        "knowledge_graph": {},
        "feature_availability": {},
    }

    def handler(route) -> None:  # type: ignore[no-untyped-def]
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
                    headers={"Access-Control-Allow-Origin": "*"},
                )
                return

        if url.endswith("/stats") or "/stats?" in url:
            route.fulfill(status=200, content_type="application/json", body=json.dumps(mock_stats))
            return

        if url.endswith("/health"):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"status": "healthy", "ready": True}),
            )
            return

        if "/stats-history" in url:
            route.fulfill(status=200, content_type="application/json", body=json.dumps({}))
            return

        route.fulfill(status=404, body="Not Found")

    page.route("**/*", handler)


def test_overview_uses_lifetime_reduction_with_lifetime_headline() -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1200})
            _install_dashboard_routes(page)

            page.goto("http://cutctx.local/dashboard")
            page.wait_for_load_state("networkidle")

            expect(page.get_by_text("194.8M", exact=True)).to_be_visible(timeout=5000)
            expect(page.get_by_text("47.9% total reduction", exact=True)).to_be_visible()
            expect(page.get_by_text("15,799", exact=True)).to_be_visible()
            expect(page.get_by_text("Lifetime requests tracked", exact=True)).to_be_visible()
        finally:
            browser.close()
