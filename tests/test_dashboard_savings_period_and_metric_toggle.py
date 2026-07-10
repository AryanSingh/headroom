"""Regression tests for two Savings & Attribution dashboard bugs:

1. The "Last 24 Hours"/"Last 7 Days"/"Last 30 Days" tabs used to render all
   zeros because the frontend treated `/stats-history`'s `history_summary`
   field (compaction metadata: {mode, stored_points, returned_points,
   compacted}) as if it were a period stats aggregate. It's always a
   truthy object, so it silently won `data.history_summary || data.lifetime`
   every time, never falling through to real data. The fix aggregates the
   real bucketed data under `series.{hourly,daily,weekly,monthly}` for the
   requested lookback window (see dashboard/src/lib/period-stats.js).
2. The attribution panels ("Savings by model"/"Savings by client") only
   showed token counts, with no way to view dollar savings. The fix adds a
   "Show by: Tokens / Cost" tab control that re-sorts and relabels both
   panels by the selected metric.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from cutctx.dashboard import get_dashboard_html

playwright = pytest.importorskip("playwright.sync_api")
Page = playwright.Page
expect = playwright.expect
sync_playwright = playwright.sync_playwright

ROOT_DIR = Path(__file__).parent.parent


def _hourly_bucket_hours_ago(hours_ago: int) -> str:
    return time.strftime("%Y-%m-%dT%H:00:00Z", time.gmtime(time.time() - hours_ago * 3600))


def _install_dashboard_routes(page: Page, mock_history: dict, mock_stats: dict | None = None) -> None:
    dashboard_html = get_dashboard_html(prefer_react=True)

    def handler(route) -> None:  # type: ignore[no-untyped-def]
        url = route.request.url

        if "cutctx.local" not in url:
            route.fulfill(status=200, body="")
            return

        if url.endswith("/dashboard") or "/dashboard/savings" in url or url.endswith("/"):
            route.fulfill(status=200, content_type="text/html", body=dashboard_html)
            return

        if "/assets/" in url:
            asset_path = ROOT_DIR / "dashboard/dist" / url.split("cutctx.local/")[1]
            if asset_path.exists():
                mime = "text/javascript" if url.endswith(".js") else "text/css"
                route.fulfill(status=200, content_type=mime, body=asset_path.read_bytes())
                return

        if "/stats-history" in url:
            route.fulfill(status=200, content_type="application/json", body=json.dumps(mock_history))
            return

        # `/stats` is requested with a `?cached=1`-style query string by the
        # live dashboard, so this must not be an exact endswith("/stats") match.
        if "/stats" in url or "/health" in url or "/favicon" in url:
            route.fulfill(status=200, content_type="application/json", body=json.dumps(mock_stats or {}))
            return

        route.fulfill(status=404, body="Not Found")

    page.route("**/*", handler)


def _base_mock_history() -> dict:
    return {
        "lifetime": {
            "tokens_saved": 43_585_573,
            "compression_savings_usd": 81.39,
            "total_input_tokens": 122_296_678,
            "total_input_cost_usd": 91.63,
            "requests": 2701,
            "savings_percent": 35.6,
        },
        "display_session": {
            "tokens_saved": 100,
            "compression_savings_usd": 0.1,
            "total_input_tokens": 1000,
            "total_input_cost_usd": 0.5,
            "requests": 5,
        },
        "models": {
            "claude-sonnet-5": {"tokens_saved": 4_528_851, "compression_savings_usd": 9.058},
            "gpt-5.4-mini": {"tokens_saved": 1_200_000, "compression_savings_usd": 2.4},
        },
        "clients": {
            "claude-code": {"tokens_saved": 4_528_851, "compression_savings_usd": 9.058},
            "opencode": {"tokens_saved": 1_200_000, "compression_savings_usd": 2.4},
        },
        # Deliberately non-empty and lifetime-shaped, to prove the frontend
        # no longer treats this as the period aggregate.
        "history_summary": {"mode": "compact", "stored_points": 100, "returned_points": 50, "compacted": True},
        "series": {"hourly": [], "daily": [], "weekly": [], "monthly": []},
    }


def test_last_24_hours_tab_shows_real_data_not_zero() -> None:
    """Guards the history_summary regression: the 24h tab must reflect the
    hourly bucket series, not render blank/zero metrics."""
    mock_history = _base_mock_history()
    mock_history["series"]["hourly"] = [
        {
            "timestamp": _hourly_bucket_hours_ago(h),
            "requests": 10,
            "tokens_saved": 50_000,
            "compression_savings_usd_delta": 0.5,
            "total_input_tokens_delta": 100_000,
            "total_input_cost_usd_delta": 1.0,
            "by_model": {"claude-sonnet-5": {"tokens_saved": 50_000, "compression_savings_usd_delta": 0.5}},
        }
        for h in range(1, 20)
    ]

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome")
        try:
            page = browser.new_page(viewport={"width": 1400, "height": 900}, color_scheme="dark")
            _install_dashboard_routes(page, mock_history)

            page.goto("http://cutctx.local/dashboard/savings", wait_until="load")
            page.get_by_role("button", name="Last 24 Hours").click()

            # 19 buckets * 50,000 tokens_saved = 950,000 -> "950.0k"
            expect(page.get_by_text("950.0k")).to_be_visible(timeout=5000)
            expect(page.locator(".metric-value", has_text="$9.500").first).to_be_visible()
            coverage_card = page.locator(".metric-card").filter(
                has=page.get_by_text("Attribution coverage", exact=True)
            )
            expect(coverage_card).to_contain_text("100%")

            # Bonus behavior enabled by the same fix: per-model attribution
            # now populates for non-lifetime periods (bucket series carries
            # by_model), while per-client stays lifetime-only (no by_client
            # in the bucket series).
            model_panel = page.locator(".panel").filter(has=page.get_by_text("Savings by model", exact=True))
            client_panel = page.locator(".panel").filter(has=page.get_by_text("Savings by client", exact=True))
            expect(model_panel.get_by_text("claude-sonnet-5", exact=True)).to_be_visible()
            expect(client_panel.get_by_text("No client data yet", exact=True)).to_be_visible()
        finally:
            browser.close()


def test_last_7_days_tab_shows_real_data_not_zero() -> None:
    """Same regression, weekly duration -> daily bucket series."""
    mock_history = _base_mock_history()
    mock_history["series"]["daily"] = [
        {
            "timestamp": time.strftime("%Y-%m-%dT00:00:00Z", time.gmtime(time.time() - d * 86400)),
            "requests": 20,
            "tokens_saved": 100_000,
            "compression_savings_usd_delta": 1.0,
            "total_input_tokens_delta": 200_000,
            "total_input_cost_usd_delta": 2.0,
            "by_model": {},
        }
        for d in range(1, 5)
    ]

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome")
        try:
            page = browser.new_page(viewport={"width": 1400, "height": 900}, color_scheme="dark")
            _install_dashboard_routes(page, mock_history)

            page.goto("http://cutctx.local/dashboard/savings", wait_until="load")
            page.get_by_role("button", name="Last 7 Days").click()

            # 4 buckets * 100,000 tokens_saved = 400,000 -> "400.0k"
            expect(page.get_by_text("400.0k")).to_be_visible(timeout=5000)
            created_card = page.locator(".metric-card").filter(
                has=page.get_by_text("Cutctx-created savings", exact=True)
            )
            expect(created_card).to_contain_text("$4.000")
        finally:
            browser.close()


def test_attribution_metric_toggle_switches_between_tokens_and_cost() -> None:
    """Guards the Tokens/Cost tab control: switching tabs must re-order and
    relabel both attribution panels by the selected metric."""
    mock_history = _base_mock_history()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome")
        try:
            page = browser.new_page(viewport={"width": 1400, "height": 1000}, color_scheme="dark")
            _install_dashboard_routes(page, mock_history)

            page.goto("http://cutctx.local/dashboard/savings", wait_until="load")

            toggle = page.locator(".attribution-toolbar")
            expect(toggle).to_be_visible(timeout=5000)

            # Default view is tokens-first labeling.
            model_panel = page.locator(".panel").filter(has=page.get_by_text("Savings by model", exact=True))
            client_panel = page.locator(".panel").filter(has=page.get_by_text("Savings by client", exact=True))

            expect(client_panel.locator(".source-meta").first).to_contain_text("tokens")
            first_row_tokens_mode = client_panel.locator(".source-row").first.inner_text()
            assert "4,528,851 tokens" in first_row_tokens_mode

            toggle.get_by_role("button", name="Cost").click()

            # Cost view relabels with $ first and re-sorts by usd descending.
            expect(client_panel.locator(".source-meta").first).to_contain_text("$")
            first_row_cost_mode = client_panel.locator(".source-row").first.inner_text()
            assert "$9.058" in first_row_cost_mode
        finally:
            browser.close()


def test_session_view_prefers_explicit_created_observed_fields_and_shows_declines() -> None:
    """Session savings should honor explicit created/observed totals and surface decline reasons compactly."""
    mock_history = _base_mock_history()
    mock_history["display_session"].update(
        {
            "created_savings_usd": 6.25,
            "observed_provider_savings_usd": 3.5,
            "savings_by_source_tokens": {
                "cutctx_compression": 1200,
                "provider_prompt_cache": 800,
            },
            "savings_by_source_usd": {
                "cutctx_compression": 1.25,
                "provider_prompt_cache": 0.75,
            },
        }
    )
    mock_stats = {
        "compression_declined_total": {
            "bypass_header": 4,
            "compression_disabled": 2,
        },
        "cost": {
            "savings_by_source": {
                "tokens": {
                    "cutctx_compression": 1200,
                    "provider_prompt_cache": 800,
                },
                "usd": {
                    "cutctx_compression": 9999.0,
                    "provider_prompt_cache": 8888.0,
                },
            },
        },
    }

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome")
        try:
            page = browser.new_page(viewport={"width": 1400, "height": 1000}, color_scheme="dark")
            _install_dashboard_routes(page, mock_history, mock_stats)

            page.goto("http://cutctx.local/dashboard/savings", wait_until="load")
            page.get_by_role("button", name="Current Session").click(force=True)

            created_card = page.locator(".metric-card").filter(
                has=page.get_by_text("Cutctx-created savings", exact=True)
            )
            observed_card = page.locator(".metric-card").filter(
                has=page.get_by_text("Provider savings preserved", exact=True)
            )

            expect(created_card).to_contain_text("$6.250", timeout=5000)
            expect(observed_card).to_contain_text("$3.500")
            source_panel = page.locator(".panel").filter(
                has=page.get_by_text("Savings by source", exact=True)
            )
            expect(source_panel).to_contain_text("1,200 tokens")
            expect(source_panel).not_to_contain_text("9,999")
            expect(page.locator(".decline-reason-strip")).to_be_visible()
            expect(page.locator(".decline-reason-chip").first).to_contain_text("Bypass header")
        finally:
            browser.close()


def test_overview_page_attribution_toggle_switches_between_tokens_and_cost() -> None:
    """The Overview/Dashboard page has its own separate SavingsPanel and
    attribution rows (sourced from /stats's persistent_savings.clients/models,
    not /stats-history), which historically had no Tokens/Cost tab control at
    all. Guards that the same tab-based approach also exists and works there."""
    mock_history = _base_mock_history()
    mock_stats = {
        "persistent_savings": {
            "clients": {
                "claude-code": {"tokens_saved": 7_457_726, "compression_savings_usd": 14.92, "requests": 403},
                "opencode": {"tokens_saved": 3_982_873, "compression_savings_usd": 0.548, "requests": 270},
            },
            "models": {
                "claude-sonnet-5": {"tokens_saved": 7_457_726, "compression_savings_usd": 14.92, "requests": 390},
                "deepseek-v4-flash": {"tokens_saved": 3_908_363, "compression_savings_usd": 0.547, "requests": 250},
            },
        },
    }

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome")
        try:
            page = browser.new_page(viewport={"width": 1400, "height": 1400}, color_scheme="dark")
            _install_dashboard_routes(page, mock_history, mock_stats)

            page.goto("http://cutctx.local/dashboard", wait_until="load")

            toggle = page.locator(".attribution-toolbar")
            expect(toggle).to_be_visible(timeout=5000)

            # Default view is tokens-first labeling, sorted by tokens desc.
            client_panel = page.locator(".panel").filter(has=page.get_by_text("Savings by client", exact=True))
            expect(client_panel.locator(".source-meta").first).to_contain_text("tokens")
            first_row_tokens_mode = client_panel.locator(".source-row").first.inner_text()
            assert "7,457,726 tokens" in first_row_tokens_mode

            toggle.get_by_role("button", name="Cost").click()

            # Cost view relabels with $ first; requests count is preserved.
            expect(client_panel.locator(".source-meta").first).to_contain_text("$")
            first_row_cost_mode = client_panel.locator(".source-row").first.inner_text()
            assert "$14.92" in first_row_cost_mode
            assert "403 requests" in first_row_cost_mode
        finally:
            browser.close()
