"""Behavior-driven Playwright validation for the dashboard docs surface."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cutctx.dashboard import get_dashboard_html

playwright = pytest.importorskip("playwright.sync_api")
Page = playwright.Page
expect = playwright.expect
sync_playwright = playwright.sync_playwright


def _install_docs_routes(page: Page) -> None:
    dashboard_html = get_dashboard_html(prefer_react=True)
    root_dir = Path(__file__).parent.parent

    def handler(route) -> None:  # type: ignore[no-untyped-def]
        url = route.request.url
        if "cutctx.local" not in url:
            route.fulfill(status=200, body="")
            return

        if (
            url.endswith("/dashboard/docs")
            or url.endswith("/docs")
            or url == "http://cutctx.local/"
        ):
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
            route.fulfill(status=200, content_type="application/json", body=json.dumps({}))
            return

        if url.endswith("/health"):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"status": "healthy", "ready": True}),
            )
            return

        if "/stats-history" in url:
            route.fulfill(status=200, content_type="application/json", body=json.dumps([]))
            return

        route.fulfill(status=404, body="Not Found")

    page.route("**/*", handler)


def test_docs_page_renders_quick_start_and_cli_reference() -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1200})
            _install_docs_routes(page)

            page.goto("http://cutctx.local/dashboard/docs")
            page.wait_for_load_state("networkidle")

            expect(page.get_by_role("heading", name="Quick Start")).to_be_visible(timeout=5000)
            expect(page.get_by_role("heading", name="CLI Reference")).to_be_visible()
            expect(page.get_by_text("Cutctx — CLI, API, and configuration reference")).to_be_visible()
        finally:
            browser.close()
