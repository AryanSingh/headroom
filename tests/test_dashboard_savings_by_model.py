"""Behavior-driven Playwright validation for dashboard savings by model."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cutctx.dashboard import get_dashboard_html

_TEST_ROOT = Path(__file__).resolve().parent
_PROJECT_ROOT = _TEST_ROOT.parent

playwright = pytest.importorskip("playwright.sync_api")
Page = playwright.Page
expect = playwright.expect
sync_playwright = playwright.sync_playwright


def _install_dashboard_routes_with_stats(page: Page) -> None:
    dashboard_html = get_dashboard_html(prefer_react=True)
    root_dir = _PROJECT_ROOT

    mock_stats = {
        "summary": {
            "cost": {
                "per_model": {
                    "gpt-4o": {"tokens_saved": 5000, "savings_usd": 0.025},
                    "claude-3-opus": {"tokens_saved": 10000, "savings_usd": 0.150},
                }
            }
        },
        "tokens": {"total_before_compression": 15000, "saved": 15000},
        "requests": {"total": 100},
        "display_session": {
            "total_input_tokens": 15000,
            "tokens_saved": 15000,
            "compression_savings_usd": 0.175,
            "models": {
                "gpt-4o": {"tokens_saved": 5000, "compression_savings_usd": 0.025},
                "claude-3-opus": {"tokens_saved": 10000, "compression_savings_usd": 0.150},
            },
        },
    }

    def handler(route) -> None:
        url = route.request.url
        if "cutctx.local" not in url:
            route.fulfill(status=200, body="")
            return

        if url.endswith("/dashboard") or url.endswith("/dashboard/savings") or url.endswith("/") or url == "http://cutctx.local/":
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
                status=200, content_type="application/json", body=json.dumps({"status": "healthy"})
            )
            return

        if "/stats-history" in url:
            mock_history = {
                "models": {
                    "gpt-4o": {"tokens_saved": 5000, "compression_savings_usd": 0.025},
                    "claude-3-opus": {"tokens_saved": 10000, "compression_savings_usd": 0.150},
                },
                "lifetime": {
                    "savings_by_source_tokens.model.gpt-4o": 5000,
                    "savings_by_source_usd.model.gpt-4o": 0.025,
                    "savings_by_source_tokens.model.claude-3-opus": 10000,
                    "savings_by_source_usd.model.claude-3-opus": 0.150,
                    "tokens_saved": 15000,
                    "compression_savings_usd": 0.175,
                    "total_input_tokens": 15000,
                    "requests": 100,
                },
                "display_session": {
                    "total_input_tokens": 15000,
                    "tokens_saved": 15000,
                    "compression_savings_usd": 0.175,
                    "models": {
                        "gpt-4o": {"tokens_saved": 5000, "compression_savings_usd": 0.025},
                        "claude-3-opus": {"tokens_saved": 10000, "compression_savings_usd": 0.150},
                    },
                }
            }
            route.fulfill(status=200, content_type="application/json", body=json.dumps(mock_history))
            return

        route.fulfill(status=404, body="Not Found")

    page.route("**/*", handler)


def test_dashboard_savings_by_model() -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page()
            page.on("console", lambda msg: print(f"Browser console: {msg.text}"))
            page.on("request", lambda request: print(">>", request.method, request.url))
            page.on("response", lambda response: print("<<", response.status, response.url))
            _install_dashboard_routes_with_stats(page)

            page.goto("http://cutctx.local/dashboard/savings")
            page.wait_for_load_state("networkidle")
            page.get_by_role("button", name="Lifetime").click()

            # Check if "Savings by model" header exists
            header = page.locator("h2:has-text('Savings by model')")
            expect(header).to_be_visible(timeout=5000)

            # Check if the models are displayed
            expect(page.locator(".source-name:has-text('gpt-4o')")).to_be_visible()
            expect(page.locator(".source-name:has-text('claude-3-opus')")).to_be_visible()

            # Save screenshot for walkthrough
            page.screenshot(
                path="/Users/aryansingh/.gemini/antigravity/brain/109383ec-01a4-4dc7-bc11-9f895839864c/savings_by_model_screenshot.png"
            )

        finally:
            browser.close()


def test_dashboard_savings_headline_shows_single_estimated_value() -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1200})
            _install_dashboard_routes_with_stats(page)

            page.goto("http://cutctx.local/dashboard/savings")
            page.wait_for_load_state("networkidle")

            savings_card = page.locator(".metric-card").filter(
                has=page.get_by_text("Cutctx-created savings", exact=True)
            )
            expect(savings_card).to_contain_text("$0.175", timeout=5000)
            expect(savings_card).not_to_contain_text("(list)")
            expect(savings_card).not_to_contain_text("(observed)")

        finally:
            browser.close()
