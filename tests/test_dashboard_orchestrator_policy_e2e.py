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


def _safe_savings_enabled_payload() -> dict:
    return {
        "schema_version": 1,
        "experience_enabled": True,
        "enabled": True,
        "mode": "balanced",
        "preset": "codex-gpt54mini-high",
        "route_count": 1,
        "routes": [
            {
                "source_model": "gpt-5.6-sol",
                "low_target_model": "gpt-5.4-mini",
                "medium_target_model": "gpt-5.6-luna",
                "low_target_capabilities": ["tools"],
                "medium_target_capabilities": ["tools"],
                "low_target_transport_safe": True,
                "medium_target_transport_safe": False,
            }
        ],
        "transport_safe_targets": ["gpt-5.4-mini"],
        "decision": {
            "request_id": "req-1",
            "requested_model": "gpt-5.6-sol",
            "effective_model": "gpt-5.4-mini",
            "candidate_model": "gpt-5.4-mini",
            "applied": True,
            "reason": "downgrade_applied",
            "title": "Safe route applied",
            "explanation": (
                "The request passed the configured safety and compatibility gates "
                "for the selected lower-cost model."
            ),
            "scorer": None,
            "confidence": 0.9,
            "signals": ["explicit_low_complexity"],
            "required_capabilities": [],
            "missing_capabilities": [],
            "transport": {},
        },
        "rollback_available": True,
    }


def _safe_savings_blocked_payload() -> dict:
    payload = _safe_savings_enabled_payload()
    payload["decision"] = {
        "request_id": "req-2",
        "requested_model": "gpt-5.6-sol",
        "effective_model": "gpt-5.6-sol",
        "candidate_model": "gpt-5.4-mini",
        "applied": False,
        "reason": "downgrade_blocked_unproven_transport",
        "title": "Transport proof blocked routing",
        "explanation": (
            "The target transport or account could not be proven safe, so Cutctx "
            "retained the requested model."
        ),
        "scorer": None,
        "confidence": None,
        "signals": [],
        "required_capabilities": ["tools"],
        "missing_capabilities": [],
        "transport": {},
    }
    return payload


def _safe_savings_off_payload() -> dict:
    return {
        "schema_version": 1,
        "experience_enabled": True,
        "enabled": False,
        "mode": "off",
        "preset": None,
        "route_count": 0,
        "routes": [],
        "transport_safe_targets": [],
        "decision": None,
        "rollback_available": False,
    }


def _install_dashboard_routes(
    page: Page,
    *,
    safe_savings_payloads: list | None = None,
    config_flags_handler=None,
) -> None:
    dashboard_html = get_dashboard_html(prefer_react=True)
    safe_savings_queue = (
        list(safe_savings_payloads)
        if safe_savings_payloads is not None
        else [_safe_savings_enabled_payload()]
    )

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
    evidence_payload = {
        "schema_version": 1,
        "status": "ready",
        "samples": 24,
        "sample_progress": {"observed": 24, "required": 20, "fraction": 1.0},
        "constraints": {
            "minimum_samples": 20,
            "minimum_mean_quality": 0.9,
            "maximum_unsafe_rate": 0.01,
            "quality_floor": 0.8,
        },
        "recommendation": {
            "minimum_confidence": 0.85,
            "routed_samples": 18,
            "routing_rate": 0.75,
            "mean_quality": 0.96,
            "unsafe_rate": 0.0,
            "total_savings_usd": 4.2,
            "mean_savings_usd": 0.233,
        },
        "frontier": [],
        "segmented": {"minimum_segment_samples": 20, "dimensions": {}},
        "shadow": {"enabled": True, "sample_rate": 0.1},
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
    orchestration_config_payload = {
        "version": 1,
        "providers": [
            {"id": "anthropic", "display_name": "Anthropic", "runtime": "anthropic"},
            {"id": "openai", "display_name": "OpenAI", "runtime": "openai"},
        ],
        "roles": [
            {"id": "worker", "name": "Worker", "description": "General execution role"},
            {"id": "reviewer", "name": "Reviewer", "description": "Checks outputs"},
        ],
        "bindings": [
            {
                "id": "worker-default",
                "role": "worker",
                "model": "anthropic:claude-sonnet-4",
                "selectors": {},
                "fallback_chain": [],
                "required_capabilities": [],
                "enabled": True,
            },
            {
                "id": "reviewer-default",
                "role": "reviewer",
                "model": "openai:gpt-5.4-mini",
                "selectors": {},
                "fallback_chain": [],
                "required_capabilities": [],
                "enabled": True,
            },
            {
                "id": "worker-docs",
                "role": "worker",
                "model": "openai:gpt-5.4-mini",
                "selectors": {"workflow": "docs"},
                "fallback_chain": ["anthropic:claude-sonnet-4"],
                "required_capabilities": ["tool_calling"],
                "equivalent_deployments": ["openai:account-b:gpt-5.4-mini"],
                "enabled": True,
            },
        ],
        "settings": {
            "mode": "strict",
            "policy": "role_locked",
            "retries": 1,
            "timeout_seconds": 120,
            "deployment_cooldown_seconds": 30,
        },
    }
    orchestration_providers_payload = {
        "catalog": [
            {
                "id": "anthropic",
                "display_name": "Anthropic",
                "runtime": "anthropic",
                "auth_methods": ["api_key"],
            },
            {
                "id": "openai",
                "display_name": "OpenAI",
                "runtime": "openai",
                "auth_methods": ["api_key"],
            },
        ],
        "accounts": [
            {
                "id": "anthropic-main",
                "provider": "anthropic",
                "display_name": "Anthropic Main",
                "auth_method": "api_key",
                "credential_configured": True,
                "base_url": "https://api.anthropic.com",
                "enabled": True,
            },
            {
                "id": "openai-main",
                "provider": "openai",
                "display_name": "OpenAI Main",
                "auth_method": "api_key",
                "credential_configured": True,
                "base_url": "https://api.openai.com",
                "enabled": True,
            },
        ],
    }
    orchestration_models_payload = {
        "models": [
            {
                "key": "anthropic:claude-sonnet-4",
                "deployment_key": "anthropic:claude-sonnet-4",
                "display_name": "Claude Sonnet 4",
                "account_id": "anthropic-main",
                "provider": "anthropic",
                "available": True,
                "deprecated": False,
                "executable": True,
                "capabilities": ["tool_calling", "reasoning"],
            },
            {
                "key": "openai:gpt-5.4-mini",
                "deployment_key": "openai:gpt-5.4-mini",
                "display_name": "GPT-5.4 Mini",
                "account_id": "openai-main",
                "provider": "openai",
                "available": True,
                "deprecated": False,
                "executable": True,
                "capabilities": ["tool_calling"],
            },
        ]
    }
    orchestration_executions_payload = {
        "executions": [
            {
                "request_id": "exec-1",
                "requested_role": "Worker",
                "assigned_model": "anthropic:claude-sonnet-4",
                "provider": "anthropic",
                "actual_model": "claude-sonnet-4",
                "latency_ms": 92,
                "fallback_used": False,
                "error": None,
            },
            {
                "request_id": "exec-2",
                "requested_role": "Reviewer",
                "assigned_model": "openai:gpt-5.4-mini",
                "provider": "openai",
                "actual_model": "gpt-5.4-mini",
                "latency_ms": 118,
                "fallback_used": True,
                "fallback_trigger": "capacity",
                "error": None,
            },
        ]
    }
    orchestration_harnesses_payload = {
        "harnesses": [
            {
                "id": "codex",
                "support_level": "native",
                "routing": True,
                "artifact_handoffs": True,
                "hidden_session_sharing": False,
                "notes": "Use native adapter/proxy paths.",
            },
            {
                "id": "openclaw",
                "support_level": "bridge",
                "routing": True,
                "artifact_handoffs": False,
                "hidden_session_sharing": True,
                "notes": "Bridge-backed harness support.",
            },
        ]
    }

    def handler(route) -> None:  # type: ignore[no-untyped-def]
        url = route.request.url

        if "cutctx.local" not in url:
            route.fulfill(status=200, body="")
            return

        if (
            url.endswith("/orchestrator")
            or url.endswith("/dashboard")
            or url == "http://cutctx.local/"
        ):
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
                status=200, content_type="application/json", body=json.dumps(stats_payload)
            )
            return

        if url.endswith("/stats-history"):
            route.fulfill(
                status=200, content_type="application/json", body=json.dumps(history_payload)
            )
            return

        if "/policy/status" in url:
            route.fulfill(
                status=200, content_type="application/json", body=json.dumps(policy_payload)
            )
            return

        if "/v1/orchestration/safe-savings/status" in url:
            payload = safe_savings_queue[0]
            if len(safe_savings_queue) > 1:
                safe_savings_queue.pop(0)
            route.fulfill(
                status=200, content_type="application/json", body=json.dumps(payload)
            )
            return

        if "/v1/orchestration/routing/evidence" in url:
            route.fulfill(
                status=200, content_type="application/json", body=json.dumps(evidence_payload)
            )
            return

        if "/v1/providers" in url:
            route.fulfill(
                status=200, content_type="application/json", body=json.dumps(providers_payload)
            )
            return

        if "/v1/orchestration/config" in url:
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(orchestration_config_payload),
            )
            return

        if "/v1/orchestration/providers" in url:
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(orchestration_providers_payload),
            )
            return

        if "/v1/orchestration/models" in url:
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(orchestration_models_payload),
            )
            return

        if "/v1/orchestration/executions" in url:
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(orchestration_executions_payload),
            )
            return

        if "/v1/orchestration/harness-compatibility" in url:
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(orchestration_harnesses_payload),
            )
            return

        if "/health" in url:
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"status": "ok", "ready": True}),
            )
            return

        if "/config/flags" in url or "/admin/config/flags" in url:
            if config_flags_handler is not None and config_flags_handler(route):
                return
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
            expect(page.get_by_text("Routing evidence", exact=True)).to_be_visible()
            expect(page.get_by_text("Ready to promote", exact=True)).to_be_visible()
            expect(page.get_by_text("24 / 20 samples", exact=True)).to_be_visible()
            expect(page.get_by_text("96.0%", exact=True)).to_be_visible()
            expect(page.get_by_text("0.0%", exact=True)).to_be_visible()
            expect(page.get_by_text("$4.200", exact=True)).to_be_visible()
            expect(page.get_by_text("0.85", exact=True)).to_be_visible()
            expect(page.get_by_text("Fallback and selection posture", exact=True)).to_be_visible()
            expect(
                page.get_by_text("Compatibility-provider health and overrides", exact=True)
            ).to_be_visible()
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


def test_orchestrator_search_expands_and_filters_tabs() -> None:
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

            search_shell = page.locator(".search-shell")
            search_input = page.locator(".search-shell input")

            expect(search_input).to_be_enabled()
            before_width = search_shell.bounding_box()["width"]
            search_input.focus()
            expect(search_input).to_be_focused()
            page.wait_for_function(
                "([element, width]) => element.getBoundingClientRect().width > width",
                arg=[search_shell.element_handle(), before_width],
            )
            after_focus_width = search_shell.bounding_box()["width"]
            assert after_focus_width > before_width

            search_input.fill("anthropic")
            page.get_by_role("tab", name="Providers").click()
            expect(page.get_by_text("Anthropic Main", exact=True)).to_be_visible()
            expect(page.get_by_text("OpenAI Main", exact=True)).to_have_count(0)

            search_input.fill("worker")
            page.get_by_role("tab", name="Roles").click()
            expect(page.get_by_text("Worker", exact=True)).to_be_visible()
            expect(page.get_by_text("Reviewer", exact=True)).to_have_count(0)
        finally:
            browser.close()


def test_orchestrator_models_tab_search_filters_without_error() -> None:
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
            page.get_by_role("tab", name="Models").click()

            search = page.get_by_label("Search models or capabilities")
            expect(search).to_be_visible()
            search.fill("gpt")
            expect(page.get_by_text("GPT-5.4 Mini", exact=True)).to_be_visible()
            expect(page.get_by_text("Claude Sonnet 4", exact=True)).to_have_count(0)
        finally:
            browser.close()


def test_orchestrator_roles_expose_advanced_binding_editor() -> None:
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
            page.get_by_role("tab", name="Roles").click()

            expect(page.get_by_label("Model for Worker", exact=True)).to_have_value(
                "anthropic:claude-sonnet-4"
            )
            page.locator(".orchestration-binding-editor summary").first.click()
            expect(page.get_by_text("Advanced bindings", exact=True).first).to_be_visible()
            expect(page.get_by_label("Binding id for Worker worker-default")).to_be_visible()
            expect(page.get_by_label("Selectors for Worker worker-docs")).to_be_visible()
            expect(page.get_by_label("Required capabilities for Worker worker-docs")).to_be_visible()
        finally:
            browser.close()


def _open_orchestrator(page: Page) -> None:
    page.add_init_script(
        "window.localStorage.setItem('cutctxAdminKey', 'testkey');"
    )
    page.goto("http://cutctx.local/dashboard/orchestrator")
    page.wait_for_load_state("networkidle")


def test_safe_savings_panel_renders_exact_routes_and_applied_decision() -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1400})
            page.add_init_script(
                "window.localStorage.setItem('cutctxAdminKey', 'testkey');"
            )
            _install_dashboard_routes(page)
            page.goto("http://cutctx.local/dashboard/orchestrator")
            page.wait_for_load_state("networkidle")

            expect(page.get_by_text("Safe Savings", exact=True)).to_be_visible()
            expect(
                page.get_by_text("gpt-5.6-sol → gpt-5.4-mini", exact=True).first
            ).to_be_visible()
            expect(page.get_by_text("Safe route applied", exact=True)).to_be_visible()
            expect(page.get_by_text("Confidence 0.90", exact=True)).to_be_visible()
        finally:
            browser.close()


def test_safe_savings_panel_renders_blocked_decision_without_bypass() -> None:
    import re

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1400})
            _install_dashboard_routes(
                page, safe_savings_payloads=[_safe_savings_blocked_payload()]
            )
            _open_orchestrator(page)

            expect(
                page.get_by_text("Transport proof blocked routing", exact=True)
            ).to_be_visible()
            expect(
                page.get_by_text("gpt-5.6-sol → gpt-5.6-sol", exact=True).first
            ).to_be_visible()
            bypass = page.get_by_role(
                "button", name=re.compile("bypass|override|force|allow", re.IGNORECASE)
            )
            assert bypass.count() == 0
        finally:
            browser.close()


def test_safe_savings_off_action_uses_config_mutation_and_confirms() -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1400})
            posted_bodies: list[dict] = []

            def flags_handler(route) -> bool:
                if route.request.method != "POST":
                    return False
                posted_bodies.append(json.loads(route.request.post_data or "{}"))
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {"applied_live": {"orchestrator_mode": {"mode": "off"}}}
                    ),
                )
                return True

            _install_dashboard_routes(
                page,
                safe_savings_payloads=[
                    _safe_savings_enabled_payload(),
                    _safe_savings_off_payload(),
                ],
                config_flags_handler=flags_handler,
            )
            page.on("dialog", lambda dialog: dialog.accept())
            _open_orchestrator(page)

            expect(page.get_by_text("Safe route applied", exact=True)).to_be_visible()
            page.get_by_role("button", name="Turn Safe Savings off").click()
            expect(
                page.get_by_text(
                    "Requests retain the originally requested model.", exact=True
                )
            ).to_be_visible()
            assert posted_bodies == [{"orchestrator_mode": "off"}]
        finally:
            browser.close()


def test_safe_savings_off_action_failure_keeps_enabled_display() -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1400})

            def flags_handler(route) -> bool:
                if route.request.method != "POST":
                    return False
                route.fulfill(
                    status=500, content_type="text/plain", body="server error"
                )
                return True

            _install_dashboard_routes(
                page,
                safe_savings_payloads=[_safe_savings_enabled_payload()],
                config_flags_handler=flags_handler,
            )
            page.on("dialog", lambda dialog: dialog.accept())
            _open_orchestrator(page)

            page.get_by_role("button", name="Turn Safe Savings off").click()
            expect(
                page.locator(".safe-savings-panel [role='alert']")
            ).to_be_visible()
            expect(page.get_by_text("Safe route applied", exact=True)).to_be_visible()
            expect(
                page.get_by_text("gpt-5.6-sol → gpt-5.4-mini", exact=True).first
            ).to_be_visible()
        finally:
            browser.close()
