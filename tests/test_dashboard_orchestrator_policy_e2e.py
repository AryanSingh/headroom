"""Playwright coverage for the Orchestrator policy-status surface."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cutctx.dashboard import get_dashboard_html

playwright = pytest.importorskip("playwright.sync_api")
Page = playwright.Page
expect = playwright.expect
sync_playwright = playwright.sync_playwright

_TEST_ROOT = Path(__file__).resolve().parent
_PROJECT_ROOT = _TEST_ROOT.parent


def _install_dashboard_routes(page: Page) -> None:
    dashboard_html = get_dashboard_html(prefer_react=True)

    stats_payload = {
        "model_routing": {
            "requested": True,
            "available": True,
            "configured_routes": 4,
            "reason": None,
        },
        "config": {"orchestrator": True},
        "cost": {
            "savings_by_source": {
                "usd": {"model_routing": 1.75},
                "tokens": {"model_routing": 4200},
            }
        },
    }
    history_payload = {"schema_version": 3, "history": [], "series": {}, "history_summary": {}}
    policy_payload = {
        "workload_class": "coding_agent",
        "resolver_disabled": False,
        "provider_decisions": {
            "anthropic": {
                "strategy_label": "coding_agent",
                "preserve_prefix_for_provider_cache": True,
                "semantic_cache_enabled": True,
                "compress_tool_outputs_only": True,
            },
            "openai": {
                "strategy_label": "coding_agent",
                "preserve_prefix_for_provider_cache": True,
                "semantic_cache_enabled": True,
                "compress_tool_outputs_only": True,
            },
            "gemini": {
                "strategy_label": "coding_agent",
                "preserve_prefix_for_provider_cache": False,
                "semantic_cache_enabled": False,
                "compress_tool_outputs_only": False,
            },
        },
    }
    providers_payload = {
        "providers": [
            {
                "name": "anthropic",
                "base_url": "https://api.anthropic.com",
                "priority": 1,
                "healthy": True,
            },
            {
                "name": "openai",
                "base_url": "https://api.openai.com",
                "priority": 2,
                "healthy": False,
            },
        ]
    }

    def handler(route) -> None:  # type: ignore[no-untyped-def]
        url = route.request.url

        if "cutctx.local" not in url:
            route.fulfill(status=200, body="")
            return

        if url.endswith("/orchestrator") or url.endswith("/dashboard") or url == "http://cutctx.local/":
            route.fulfill(status=200, content_type="text/html", body=dashboard_html)
            return

        if "/assets/" in url:
            asset_rel = url.split("cutctx.local/")[1]
            if asset_rel.startswith("dashboard/"):
                asset_rel = asset_rel[len("dashboard/") :]
            asset_path = _PROJECT_ROOT / "cutctx/dashboard" / asset_rel
            if asset_path.exists():
                mime = "text/javascript" if url.endswith(".js") else "text/css"
                route.fulfill(
                    status=200,
                    content_type=mime,
                    body=asset_path.read_bytes(),
                    headers={"Access-Control-Allow-Origin": "*"},
                )
                return

        if "/stats?cached=1" in url:
            route.fulfill(status=200, content_type="application/json", body=json.dumps(stats_payload))
            return

        if url.endswith("/stats-history"):
            route.fulfill(status=200, content_type="application/json", body=json.dumps(history_payload))
            return

        if "/policy/status" in url:
            route.fulfill(status=200, content_type="application/json", body=json.dumps(policy_payload))
            return

        if "/v1/providers" in url:
            route.fulfill(status=200, content_type="application/json", body=json.dumps(providers_payload))
            return

        if "/health" in url:
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"status": "ok", "ready": True}),
            )
            return

        if "/config/flags" in url or "/admin/config/flags" in url:
            route.fulfill(status=404, content_type="text/plain", body="not found")
            return

        route.fulfill(status=404, content_type="text/plain", body="not found")

    page.route("**/*", handler)


def test_orchestrator_renders_provider_policy_status() -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1400})
            page.add_init_script(
                """
                window.localStorage.setItem('cutctxAdminKey', 'testkey');
                """
            )
            _install_dashboard_routes(page)

            page.goto("http://cutctx.local/dashboard/orchestrator")
            page.wait_for_load_state("networkidle")

            expect(page.get_by_text("Routing mode control", exact=True)).to_be_visible()
            expect(page.get_by_text("Fallback and selection posture", exact=True)).to_be_visible()
            expect(page.get_by_text("Compatibility-provider health and overrides", exact=True)).to_be_visible()
            expect(page.get_by_text("coding_agent", exact=True).first).to_be_visible()
            expect(page.get_by_text("Prefix cache: preserve").first).to_be_visible()
            expect(page.get_by_text("Semantic cache: on").first).to_be_visible()
            expect(page.get_by_text("Prefix cache: compress").first).to_be_visible()
            expect(page.get_by_text("Semantic cache: off").first).to_be_visible()
            expect(page.get_by_text("Healthy", exact=True).first).to_be_visible()
            expect(page.get_by_text("Disabled", exact=True).first).to_be_visible()
            expect(page.get_by_role("button", name="Disable provider").first).to_be_visible()
        finally:
            browser.close()
