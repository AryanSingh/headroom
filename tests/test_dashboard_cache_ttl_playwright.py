"""Behavior-driven Playwright validation for dashboard TTL cache metrics."""

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


def _sample_stats() -> dict:
    return {
        "cost": {
            "savings_usd": 12.34,
            "compression_savings_usd": 12.34,
            "cache_savings_usd": 5.67,
            "cli_tokens_avoided": 0,
        },
        "requests": {
            "total": 128,
            "cached": 96,
            "rate_limited": 0,
            "failed": 0,
            "by_provider": {"anthropic": 128},
            "by_model": {"claude-opus-4-6": 128},
        },
        "tokens": {
            "input": 245_000,
            "output": 88_000,
            "saved": 143_000,
            "cli_tokens_avoided": 0,
            "total_before_compression": 388_000,
            "savings_percent": 36.86,
        },
        "overhead": {"average_ms": 14.2, "min_ms": 4.5, "max_ms": 42.7},
        "ttfb": {"average_ms": 1320.0, "min_ms": 420.0, "max_ms": 2900.0},
        "latency": {"average_ms": 1510.0, "min_ms": 520.0, "max_ms": 3300.0},
        "waste_signals": {"json_bloat": 95_000, "repetition": 48_000},
        "savings_history": [
            ["2026-04-01T00:00:00Z", 12_000],
            ["2026-04-02T00:00:00Z", 38_000],
            ["2026-04-03T00:00:00Z", 57_000],
            ["2026-04-04T00:00:00Z", 102_000],
            ["2026-04-05T00:00:00Z", 143_000],
        ],
        "persistent_savings": {
            "display_session": {},
            "lifetime": {"tokens_saved": 143_000, "compression_savings_usd": 12.34},
        },
        "pipeline_timing": {},
        "compression_cache": {"mode": "cache"},
        "prefix_cache": {
            "by_provider": {
                "anthropic": {
                    "cache_read_tokens": 9_800_000,
                    "cache_write_tokens": 420_000,
                    "cache_write_5m_tokens": 185_000,
                    "cache_write_1h_tokens": 235_000,
                    "cache_write_5m_requests": 18,
                    "cache_write_1h_requests": 24,
                    "requests": 128,
                    "hit_requests": 96,
                    "hit_rate": 75.0,
                    "bust_count": 0,
                    "bust_write_tokens": 0,
                    "read_discount": "90%",
                    "write_premium": "25%",
                    "savings_usd": 5.67,
                    "write_premium_usd": 0.42,
                    "net_savings_usd": 5.67,
                    "label": "Explicit breakpoints, 5-min TTL",
                    "observed_ttl_buckets": {
                        "5m": {"tokens": 185_000, "requests": 18},
                        "1h": {"tokens": 235_000, "requests": 24},
                    },
                    "observed_ttl_mix": {
                        "5m_pct": 44.0,
                        "1h_pct": 56.0,
                        "active_buckets": ["5m", "1h"],
                    },
                }
            },
            "totals": {
                "cache_read_tokens": 9_800_000,
                "cache_write_tokens": 420_000,
                "cache_write_5m_tokens": 185_000,
                "cache_write_1h_tokens": 235_000,
                "cache_write_5m_requests": 18,
                "cache_write_1h_requests": 24,
                "requests": 128,
                "hit_requests": 96,
                "bust_count": 0,
                "bust_write_tokens": 0,
                "savings_usd": 5.67,
                "write_premium_usd": 0.42,
                "net_savings_usd": 5.67,
                "hit_rate": 75.0,
                "observed_ttl_buckets": {
                    "5m": {"tokens": 185_000, "requests": 18},
                    "1h": {"tokens": 235_000, "requests": 24},
                },
                "observed_ttl_mix": {
                    "5m_pct": 44.0,
                    "1h_pct": 56.0,
                    "active_buckets": ["5m", "1h"],
                },
            },
            "prefix_freeze": {
                "busts_avoided": 0,
                "tokens_preserved": 0,
                "compression_foregone_tokens": 0,
                "net_benefit_tokens": 0,
            },
            "attribution": "Observed provider TTL buckets.",
        },
    }


def _sample_history() -> dict:
    return {
        "history": [
            {
                "timestamp": "2026-04-01T00:00:00Z",
                "total_tokens_saved": 12_000,
                "compression_savings_usd": 0.6,
            },
            {
                "timestamp": "2026-04-05T00:00:00Z",
                "total_tokens_saved": 143_000,
                "compression_savings_usd": 12.34,
            },
        ],
        "series": {
            "daily": [
                {
                    "timestamp": "2026-04-05T00:00:00Z",
                    "tokens_saved": 20_000,
                    "total_tokens_saved": 143_000,
                    "compression_savings_usd_delta": 1.7,
                }
            ],
            "weekly": [],
            "monthly": [],
        },
        "lifetime": {"tokens_saved": 143_000, "compression_savings_usd": 12.34},
    }


def _install_dashboard_routes(page: Page) -> None:
    stats = _sample_stats()
    history = _sample_history()
    health = {"status": "healthy", "version": "0.3.0"}
    dashboard_html = get_dashboard_html()

    def handler(route) -> None:  # type: ignore[no-untyped-def]
        url = route.request.url
        if url.endswith("/dashboard") or url == "http://cutctx.local/":
            route.fulfill(status=200, content_type="text/html", body=dashboard_html)
            return
        if "/stats" in url and "/stats-history" not in url:
            route.fulfill(status=200, content_type="application/json", body=json.dumps(stats))
            return
        if "/stats-history" in url:
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(history),
            )
            return
        if url.endswith("/health"):
            route.fulfill(status=200, content_type="application/json", body=json.dumps(health))
            return
        route.continue_()

    page.route("**/*", handler)


def test_dashboard_renders_observed_ttl_metrics_and_can_capture_screenshot(
    tmp_path: Path,
) -> None:
    artifact_dir = os.environ.get("CUTCTX_PLAYWRIGHT_ARTIFACT_DIR")

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1720, "height": 1400}, color_scheme="dark")
        _install_dashboard_routes(page)
        page.goto("http://cutctx.local/dashboard", wait_until="commit")

        # `wait_until="commit"` returns as soon as navigation commits, before
        # any content exists, so this first assertion is what waits for the
        # SPA to download, parse and hydrate. Playwright's default expect
        # timeout is 5s, which is comfortable locally and marginal in CI: the
        # route mocks are served from Python, and coverage instrumentation
        # slows every one of them. That raced and failed the whole job.
        #
        # Only the hydration gate needs the longer budget; once the first
        # element is visible the rest are already rendered. This does not
        # weaken the test — an element that never appears still fails it.
        expect(page.get_by_text("Observed TTL Buckets")).to_be_visible(timeout=30_000)
        expect(page.get_by_text("Provider-reported cache write mix")).to_be_visible()
        expect(page.get_by_test_id("ttl-bucket-headline")).to_have_text("1h leaning")
        expect(page.get_by_test_id("ttl-bucket-mix-1h-pct")).to_have_text("1h 56.0%")
        expect(page.get_by_test_id("ttl-bucket-mix-5m-pct")).to_have_text("5m 44.0%")
        expect(page.get_by_test_id("ttl-bucket-1h-value")).to_have_text("235.0k")
        expect(page.get_by_test_id("ttl-bucket-5m-value")).to_have_text("185.0k")
        expect(page.get_by_text("TTL 1h 56.0% / 5m 44.0%")).to_be_visible()

        # Falling back to Path.cwd() wrote the screenshot over the TRACKED
        # dashboard-cache-ttl-main.png at the repo root, so simply running the
        # suite left the working tree dirty. That is not cosmetic: the release
        # manifest generator aborts with "requires a clean checkout", and past
        # plans in docs/superpowers worked around it by telling authors to
        # "preserve the pre-existing dashboard-cache-ttl-main.png
        # modification" rather than fixing the cause.
        #
        # CI still sets CUTCTX_PLAYWRIGHT_ARTIFACT_DIR and collects the image
        # from there; locally it goes to the test's tmp dir. Regenerating the
        # committed evidence is now a deliberate act (set the env var), not a
        # side effect of running tests.
        screenshot_path = (
            Path(artifact_dir) / "dashboard-cache-ttl-main.png"
            if artifact_dir
            else tmp_path / "dashboard-cache-ttl-main.png"
        )
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(screenshot_path), full_page=True)
        browser.close()
