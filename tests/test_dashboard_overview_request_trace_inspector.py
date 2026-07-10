"""Playwright coverage for the Overview request trace inspector."""

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


def _base_stats() -> dict:
    return {
        "summary": {
            "cost": {
                "without_cutctx_usd": 6.0,
                "with_cutctx_usd": 1.5,
                "total_saved_usd": 4.5,
                "breakdown": {
                    "compression_savings_usd": 2.75,
                    "cache_savings_usd": 1.75,
                },
            }
        },
        "tokens": {
            "saved": 50_000,
            "savings_percent": 12.5,
            "total_before_compression": 400_000,
            "active_savings_percent": 12.5,
            "proxy_savings_percent": 8.0,
        },
        "requests": {"total": 25, "failed": 0, "cached": 2},
        "router": {"route_counts": {"log": 4, "json": 2}},
        "persistent_savings": {
            "lifetime": {
                "requests": 25,
                "tokens_saved": 50_000,
                "total_input_tokens": 400_000,
                "compression_savings_usd": 2.75,
                "cache_savings_usd": 1.75,
            },
            "display_session": {
                "requests": 25,
                "tokens_saved": 50_000,
                "total_input_tokens": 400_000,
                "compression_savings_usd": 2.75,
                "cache_savings_usd": 1.75,
            },
        },
        "recent_requests": [
            {
                "request_id": "trace-1",
                "timestamp": "2026-07-09T00:40:00Z",
                "model": "gpt-5.4-mini",
                "input_tokens_original": 1500,
                "tokens_saved": 300,
                "cache_saved_tokens": 200,
                "total_saved_tokens": 500,
                "total_savings_percent": 33.3,
                "savings_percent": 20.0,
            }
        ],
    }


def _base_history() -> dict:
    return {
        "generated_at": "2026-07-09T00:45:00Z",
        "lifetime": {
            "requests": 25,
            "tokens_saved": 50_000,
            "total_input_tokens": 400_000,
            "compression_savings_usd": 2.75,
            "cache_savings_usd": 1.75,
        },
        "display_session": {
            "requests": 25,
            "tokens_saved": 50_000,
            "total_input_tokens": 400_000,
            "compression_savings_usd": 2.75,
            "cache_savings_usd": 1.75,
        },
    }


def _trace_payload() -> dict:
    return {
        "trace": {
            "request_id": "trace-1",
            "timestamp": "2026-07-09T00:40:00Z",
            "turn_id": "turn-123",
            "provider": {
                "name": "openai",
                "requested_model": "gpt-5.4",
                "actual_model": "gpt-5.4-mini",
            },
            "routing": {
                "requested_model": "gpt-5.4",
                "actual_model": "gpt-5.4-mini",
                "routed": True,
                "source_model": "gpt-5.4",
                "target_model": "gpt-5.4-mini",
                "reason": "low_complexity",
                "request_overrides": {"reasoning": {"effort": "high"}},
                "saved_tokens": 300,
                "saved_usd": 0.12,
            },
            "compression": {
                "input_tokens_original": 1500,
                "input_tokens_optimized": 1000,
                "tokens_saved": 300,
                "savings_percent": 20.0,
                "total_saved_tokens": 500,
                "total_savings_percent": 33.3,
                "transforms_applied": ["smart_crusher", "router:log"],
                "decline_reason": None,
                "savings_by_source_tokens": {
                    "cutctx_compression": 300,
                    "provider_prompt_cache": 200,
                },
                "savings_by_source_usd": {
                    "cutctx_compression": 0.08,
                    "provider_prompt_cache": 0.04,
                },
            },
            "latency": {
                "optimization_ms": 14.5,
                "total_ms": 92.4,
                "pipeline_timing": {"route_ms": 3.1, "compress_ms": 11.4},
            },
            "cache": {
                "hit": True,
                "provider_prompt_cache_saved_tokens": 200,
                "semantic_cache_saved_tokens": 0,
                "self_hosted_prefix_cache_saved_tokens": 0,
            },
            "cost": {"request_cost_usd": 0.21},
            "fallback": {
                "provider": "openai",
                "reason": "circuit_breaker_open",
                "attempted": False,
                "circuit_breaker_state": "open",
                "circuit_breaker_retry_after_s": 12.5,
                "active_provider": "openai-primary",
                "active_base_url": "https://api.openai.com",
            },
            "tags": {"client": "codex", "project": "headroom"},
            "messages": {
                "request_messages": [{"role": "user", "content": "before"}],
                "compressed_messages": [{"role": "user", "content": "after"}],
                "response_content": "done",
            },
        },
        "log_full_messages": True,
    }


def _install_dashboard_routes(
    page: Page,
    *,
    stats_payload: dict | None = None,
    history_payload: dict | None = None,
    trace_payload: dict | None = None,
    trace_status: int = 200,
) -> None:
    dashboard_html = get_dashboard_html(prefer_react=True)

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
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(stats_payload or _base_stats()),
            )
            return

        if url.endswith("/stats-history"):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(history_payload or _base_history()),
            )
            return

        if "/transformations/traces/trace-1" in url:
            if trace_status == 200:
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(trace_payload or _trace_payload()),
                )
            else:
                route.fulfill(status=trace_status, content_type="text/plain", body="not found")
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


def test_overview_request_trace_inspector_renders_trace_details() -> None:
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

            page.goto("http://cutctx.local/dashboard")
            page.wait_for_load_state("networkidle")

            trace_panel = page.locator(".request-trace-panel")

            expect(page.get_by_text("Recent requests", exact=True)).to_be_visible()
            expect(trace_panel).not_to_be_visible()
            page.get_by_role("button", name="gpt-5.4-mini", exact=True).click()
            expect(page.get_by_text("Request trace", exact=True)).to_be_visible()
            expect(trace_panel.get_by_text("trace-1")).to_be_visible()
            expect(trace_panel.get_by_text("Requested model", exact=True)).to_be_visible()
            expect(page.get_by_text("Actual: gpt-5.4-mini", exact=True)).to_be_visible()
            expect(trace_panel.get_by_text("Direct compression", exact=True)).to_be_visible()
            expect(trace_panel.get_by_text("Provider prompt cache", exact=True)).to_be_visible()
            expect(trace_panel.locator(".request-trace-payload-card").nth(1)).to_contain_text(
                "Compressed upstream payload"
            )
            expect(trace_panel.locator(".request-trace-payload-block").nth(1)).to_contain_text(
                '"content": "after"'
            )
            expect(trace_panel).to_contain_text("route_ms 3.1ms")
            expect(trace_panel).to_contain_text("openai-primary")
            expect(trace_panel).to_contain_text("circuit open")
            expect(trace_panel).to_contain_text("circuit_breaker_open")
            expect(trace_panel).to_contain_text("12.5 s")
            expect(trace_panel).to_contain_text("https://api.openai.com")
        finally:
            browser.close()


def test_overview_request_trace_inspector_handles_trace_errors() -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1400})
            page.add_init_script(
                """
                window.localStorage.setItem('cutctxAdminKey', 'testkey');
                """
            )
            _install_dashboard_routes(page, trace_status=404)

            page.goto("http://cutctx.local/dashboard")
            page.wait_for_load_state("networkidle")

            expect(page.get_by_text("Recent requests", exact=True)).to_be_visible()
            expect(page.locator(".request-trace-panel")).not_to_be_visible()
            page.get_by_role("button", name="gpt-5.4-mini", exact=True).click()
            expect(page.get_by_text("Failed to load trace:")).to_be_visible()
        finally:
            browser.close()
