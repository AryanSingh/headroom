"""Playwright regression tests for dashboard savings headlines."""

from __future__ import annotations

import copy
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


BASE_STATS = {
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
        "saved": 1_220,
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
            "cache_savings_usd": 139.34,
            "model_routing_savings_usd": 5.0,
            "normalization_savings_usd": 1.0,
            "batch_routing_savings_usd": 2.0,
            "memoization_savings_usd": 3.0,
            "output_optimization_savings_usd": 4.0,
        },
        "recent_history": [],
    },
    "savings_by_source": {
        "usd": {
            "cutctx_compression": 472.24,
            "provider_prompt_cache": 139.34,
            "model_routing": 5.0,
            "normalization": 1.0,
            "batch_routing": 2.0,
            "memoization": 3.0,
            "output_optimization": 4.0,
        },
    },
    "recent_requests": [],
    "prefix_cache": {"totals": {}},
    "knowledge_graph": {},
    "feature_availability": {},
}


def _deep_merge(base: dict, override: dict) -> dict:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _install_dashboard_routes(
    page: Page,
    stats_override: dict | None = None,
    history_override: dict | None = None,
) -> None:
    dashboard_html = get_dashboard_html(prefer_react=True)
    root_dir = _PROJECT_ROOT
    mock_stats = _deep_merge(BASE_STATS, stats_override or {})
    mock_history = {
        "schema_version": 3,
        "history": [],
        "series": {},
        "history_summary": {},
    }
    if history_override:
        mock_history = _deep_merge(mock_history, history_override)

    def handler(route) -> None:  # type: ignore[no-untyped-def]
        url = route.request.url
        if "cutctx.local" not in url:
            route.fulfill(status=200, body="")
            return

        if url.endswith("/dashboard") or url.endswith("/") or url == "http://cutctx.local/":
            route.fulfill(status=200, content_type="text/html", body=dashboard_html)
            return

        if "/assets/" in url:
            asset_rel = url.split("cutctx.local/")[1]
            asset_path = root_dir / "dashboard/dist" / asset_rel
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

        if url.endswith("/health") or "/health?" in url:
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"status": "healthy", "ready": True, "alive": True}),
            )
            return

        if url.endswith("/stats-history") or "/stats-history?" in url:
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(mock_history),
            )
            return

        if url.endswith("/config/flags") or "/config/flags?" in url:
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "live_toggleable": {},
                        "restart_required": {},
                        "legacy_aliases": {},
                        "runtime_overrides": {},
                    }
                ),
            )
            return

        route.fulfill(status=404, content_type="text/plain", body="not found")

    page.route("**/*", handler)


def test_overview_uses_lifetime_money_saved_across_all_sources() -> None:
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
            expect(page.get_by_text("$626.58", exact=True)).to_be_visible()
            money_card = page.locator("article").filter(has_text="Money saved")
            expect(
                money_card.get_by_text(
                    "Lifetime savings split between created Cutctx savings and observed provider cache"
                )
            ).to_be_visible()
            expect(money_card.get_by_text("$487.24 created by Cutctx")).to_be_visible()
            expect(money_card.get_by_text("$139.34 observed at provider")).to_be_visible()
            expect(page.get_by_text("Lifetime requests tracked", exact=True)).to_be_visible()
        finally:
            browser.close()


def test_overview_lifetime_never_uses_larger_session_money_saved() -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1200})
            _install_dashboard_routes(
                page,
                {
                    "summary": {
                        "cost": {
                            "without_cutctx_usd": 8.0,
                            "with_cutctx_usd": 1.25,
                            "total_saved_usd": 6.75,
                            "breakdown": {
                                "compression_savings_usd": 4.0,
                                "cache_savings_usd": 2.75,
                            },
                        },
                    },
                    "persistent_savings": {
                        "lifetime": {
                            "requests": 4,
                            "tokens_saved": 400,
                            "total_input_tokens": 8_000,
                            "compression_savings_usd": 1.2,
                            "cache_savings_usd": 0.3,
                            "model_routing_savings_usd": 0.0,
                            "normalization_savings_usd": 0.0,
                            "batch_routing_savings_usd": 0.0,
                            "memoization_savings_usd": 0.0,
                            "output_optimization_savings_usd": 0.0,
                        }
                    },
                    "savings_by_source": {
                        "usd": {
                            "cutctx_compression": 1.2,
                            "provider_prompt_cache": 0.3,
                            "model_routing": 0.0,
                            "normalization": 0.0,
                            "batch_routing": 0.0,
                            "memoization": 0.0,
                            "output_optimization": 0.0,
                        }
                    },
                },
            )

            page.goto("http://cutctx.local/dashboard")
            page.wait_for_load_state("networkidle")

            money_card = page.locator("article").filter(
                has=page.get_by_text("Money saved", exact=True)
            )
            # The lifetime tab must use the durable lifetime record ($1.50),
            # not the current process's $6.75 session counter.
            expect(money_card).to_contain_text("$1.500")
            expect(money_card).not_to_contain_text("$6.750")
        finally:
            browser.close()


def test_overview_current_session_sums_display_session_money_saved() -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1200})
            _install_dashboard_routes(
                page,
                {
                    "tokens": {
                        "saved": 15_900_000,
                        "total_before_compression": 54_266_211,
                        "active_savings_percent": 29.3,
                        "proxy_savings_percent": 10.0,
                    },
                    "cost": {
                        "savings_by_source": {
                            "tokens": {
                                "cutctx_compression": 15_900_000,
                            },
                            "usd": {
                                "cutctx_compression": 12.34,
                                "model_routing": 0.5,
                            },
                        },
                    },
                    "requests": {"total": 1_732},
                },
                {
                    "display_session": {
                        "requests": 1_732,
                        "tokens_saved": 15_900_000,
                        "total_input_tokens": 54_266_211,
                        "compression_savings_usd": 12.34,
                        "cache_savings_usd": 5.67,
                        "model_routing_savings_usd": 1.25,
                    }
                },
            )

            page.goto("http://cutctx.local/dashboard")
            page.wait_for_load_state("networkidle")
            page.get_by_role("button", name="Current Session").click()

            money_card = page.locator("article").filter(
                has=page.get_by_text("Money saved", exact=True)
            )
            expect(money_card).to_contain_text("$19.26")
            expect(money_card).to_contain_text("Current proxy-session savings")

            source_panel = page.locator(".panel").filter(
                has=page.get_by_text("Where savings come from", exact=True)
            )
            expect(source_panel.get_by_text("Model routing", exact=True)).to_be_visible()
        finally:
            browser.close()
