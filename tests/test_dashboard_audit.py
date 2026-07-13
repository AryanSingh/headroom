"""Deterministic Playwright audit matrix for the ten dashboard routes."""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pytest

playwright = pytest.importorskip("playwright.sync_api")
Browser = playwright.Browser
Page = playwright.Page
expect = playwright.expect
sync_playwright = playwright.sync_playwright

ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = ROOT / "dashboard"
ARTIFACT_DIR = ROOT / "dashboard" / "screenshots" / "dashboard-audit" / "python"
ROUTES = (
    ("/", "Dashboard"),
    ("/savings", "Savings"),
    ("/orchestrator", "Orchestrator"),
    ("/capabilities", "Capabilities"),
    ("/governance", "Governance"),
    ("/firewall", "Security"),
    ("/memory", "Memory"),
    ("/replay", "Replay"),
    ("/playground", "Playground"),
    ("/docs", "Docs"),
)
VIEWPORTS = ((375, 812), (768, 1024), (1280, 900), (1720, 1400))
ROUTE_MATRIX = tuple(
    (route, label, width, height) for route, label in ROUTES for width, height in VIEWPORTS
)

JSON_HEADERS = {"content-type": "application/json"}
STATS = {
    "summary": {"saved": 0, "input": 0, "savings_percent": 0},
    "tokens": {"saved": 0, "input": 0, "total_before_compression": 0, "savings_percent": 0},
    "requests": {"total": 0, "failed": 0, "cached": 0},
    "config": {"firewall": False, "memory": False, "orchestrator": False, "rate_limiter": False},
    "cost": {"budget": {"enabled": False}},
    "recent_requests": [
        {
            "request_id": "req-1",
            "model": "memory-keeper",
            "provider": "openai",
            "timestamp": "2026-07-12T00:00:00Z",
        },
        {
            "request_id": "req-2",
            "model": "gpt-4o",
            "provider": "anthropic",
            "timestamp": "2026-07-12T00:00:01Z",
        },
    ],
    "persistent_savings": {"lifetime": {}, "display_session": {}},
}
FLAGS = {"live_toggleable": {}, "restart_required": {}}


def _payload(pathname: str, method: str) -> dict | list:
    if pathname == "/health":
        return {"status": "healthy", "ready": True, "version": "0.30.0", "checks": {}}
    if pathname == "/stats":
        return STATS
    if pathname == "/stats-history":
        return {
            "history": [],
            "series": {"hourly": [], "daily": [], "weekly": [], "monthly": []},
            "lifetime": {},
        }
    if pathname in {"/config/flags", "/admin/config/flags"}:
        return {**FLAGS, "applied_live": {}} if method == "POST" else FLAGS
    if pathname == "/entitlements":
        return {"current_tier": "builder", "features": {}}
    if pathname == "/audit/events":
        return {"events": []}
    if pathname == "/rbac/roles":
        return {"assignments": [], "roles": []}
    if pathname == "/v1/memory/query":
        return []
    if pathname == "/v1/providers":
        return {"providers": []}
    if pathname.startswith("/v1/sessions/"):
        return {"events": []}
    return {}


def _is_api(pathname: str) -> bool:
    return pathname in {"/health", "/stats", "/entitlements"} or pathname.startswith(
        (
            "/stats-history",
            "/v1/",
            "/config/",
            "/admin/config/",
            "/audit/",
            "/rbac/",
            "/firewall/",
            "/policy/",
        )
    )


def _install_routes(page: Page, events: dict[str, list[str]]) -> None:
    page.add_init_script("window.localStorage.setItem('cutctxAdminKey', 'dashboard-audit-key')")

    page.on(
        "console",
        lambda message: (
            events["console_errors"].append(message.text) if message.type == "error" else None
        ),
    )
    page.on("pageerror", lambda error: events["page_errors"].append(str(error)))
    page.on(
        "requestfailed",
        lambda request: events["failed_requests"].append(f"{request.url}: {request.failure}"),
    )

    def on_response(response) -> None:  # type: ignore[no-untyped-def]
        if (
            response.request.resource_type in {"stylesheet", "script", "font", "image"}
            and response.status >= 400
        ):
            events["broken_assets"].append(f"{response.status}: {response.url}")

    page.on("response", on_response)

    def handler(route) -> None:  # type: ignore[no-untyped-def]
        from urllib.parse import urlparse

        parsed = urlparse(route.request.url)
        if not _is_api(parsed.path):
            route.continue_()
            return
        route.fulfill(
            status=200,
            headers=JSON_HEADERS,
            body=json.dumps(_payload(parsed.path, route.request.method)),
        )

    page.route("**/*", handler)


def _available_loopback_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@pytest.fixture(scope="session")
def dashboard_server():
    base_url = os.environ.get("CUTCTX_DASHBOARD_AUDIT_BASE_URL")
    process = None
    if not base_url:
        port = _available_loopback_port()
        base_url = f"http://127.0.0.1:{port}"
        process = subprocess.Popen(
            ["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", str(port)],
            cwd=DASHBOARD_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        try:
            with urlopen(f"{base_url}/dashboard", timeout=1):
                break
        except (OSError, URLError):
            time.sleep(0.1)
    else:
        if process:
            process.terminate()
        pytest.fail(f"Dashboard server did not start at {base_url}")

    yield base_url.rstrip("/")
    if process:
        process.terminate()
        process.wait(timeout=10)


@pytest.fixture(scope="module")
def audit_browser():
    with sync_playwright() as playwright_instance:
        browser = playwright_instance.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture(
    params=ROUTE_MATRIX,
    ids=lambda item: f"{item[2]}px-{item[0].strip('/').replace('/', '-') or 'dashboard'}",
)
def audit_page(request, dashboard_server: str, audit_browser: Browser):
    route, label, width, height = request.param
    events = {"console_errors": [], "page_errors": [], "failed_requests": [], "broken_assets": []}
    context = audit_browser.new_context(viewport={"width": width, "height": height})
    page = context.new_page()
    _install_routes(page, events)
    page.goto(
        f"{dashboard_server}/dashboard{'' if route == '/' else route}",
        wait_until="domcontentloaded",
    )
    yield page, route, label, width, events

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"{width}px-{route.strip('/').replace('/', '-') or 'dashboard'}"
    page.screenshot(path=str(ARTIFACT_DIR / f"{stem}.png"), full_page=True)
    (ARTIFACT_DIR / f"{stem}.json").write_text(
        json.dumps(events, indent=2) + "\n", encoding="utf-8"
    )
    context.close()


def test_dashboard_audit_matrix(audit_page) -> None:  # type: ignore[no-untyped-def]
    page, route, label, width, events = audit_page
    expect(page.locator(".topbar-title-row h2")).to_have_text(label)

    expected_hrefs = [f"/dashboard{path if path != '/' else ''}" for path, _ in ROUTES]
    links = page.locator('nav[aria-label="Main Navigation"] a').evaluate_all(
        "elements => elements.map(element => ({ href: element.getAttribute('href'), label: element.textContent.trim() }))"
    )
    assert links == [
        {"href": href, "label": route_label}
        for href, (_, route_label) in zip(expected_hrefs, ROUTES)
    ]
    assert len({link["href"] for link in links}) == 10

    metrics = page.evaluate(
        """() => ({
          viewportWidth: document.documentElement.clientWidth,
          documentWidth: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth),
          duplicateIds: [...document.querySelectorAll('[id]')].map(element => element.id).filter((id, index, ids) => ids.indexOf(id) !== index),
        })"""
    )
    assert metrics["documentWidth"] <= metrics["viewportWidth"] + 1
    assert metrics["duplicateIds"] == []

    missing_names = page.locator(
        "button:visible, a:visible, input:visible, select:visible, textarea:visible"
    ).evaluate_all(
        """elements => elements.filter(element => !element.disabled && !element.closest('[aria-hidden="true"]')).map(element => element.getAttribute('aria-label') || element.getAttribute('title') || element.getAttribute('placeholder') || element.labels?.[0]?.textContent?.trim() || element.textContent.trim()).filter(Boolean).length === elements.filter(element => !element.disabled && !element.closest('[aria-hidden="true"]')).length"""
    )
    assert missing_names
    expect(page.locator('nav[aria-label="Main Navigation"]')).to_be_visible()
    expect(page.get_by_role("button", name="Toggle sidebar")).to_be_visible()
    expect(page.get_by_role("button", name="Switch to")).to_be_visible()

    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement && document.activeElement.tagName") != "BODY"

    if route == "/governance":
        page.keyboard.press("/")
        expect(page.locator('input[aria-label="Search"]')).to_be_focused()

    if route == "/capabilities":
        # Capabilities does not expose a global filter. The shared topbar
        # intentionally renders a disabled search affordance on this route;
        # the audit must not attempt to type into it.
        search = page.locator('input[placeholder="Search unavailable"]')
        expect(search).to_be_disabled()

    if route == "/playground":
        page.get_by_role("button", name="Load sample multimodal image").click()
        expect(page.get_by_text("Image attached")).to_be_visible()

    if route == "/":
        # Overview's dashboard-wide search filters its summary panels.  This
        # assertion deliberately checks the enabled control; a prior audit
        # expectation for a disabled affordance became stale when Overview
        # search support was implemented.
        expect(page.get_by_role("textbox", name="Search")).to_be_visible()

    if width <= 1024:
        toggle = page.get_by_role("button", name="Toggle sidebar")
        toggle.click()
        expect(page.locator(".sidebar-shell")).to_have_class(re.compile("open"))
        page.keyboard.press("Escape")
        expect(page.locator(".sidebar-shell")).not_to_have_class(re.compile("open"))
        expect(toggle).to_be_focused()

    assert events == {
        "console_errors": [],
        "page_errors": [],
        "failed_requests": [],
        "broken_assets": [],
    }


def test_dashboard_skip_link_focuses_main_content(
    dashboard_server: str, audit_browser: Browser
) -> None:  # type: ignore[no-untyped-def]
    events = {"console_errors": [], "page_errors": [], "failed_requests": [], "broken_assets": []}
    context = audit_browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    try:
        _install_routes(page, events)
        page.goto(f"{dashboard_server}/dashboard", wait_until="domcontentloaded")

        skip_link = page.get_by_role("link", name="Skip to main content")
        page.keyboard.press("Tab")
        expect(skip_link).to_be_focused()

        skip_link.press("Enter")
        expect(page.locator("#main-content")).to_be_focused()

        assert events == {
            "console_errors": [],
            "page_errors": [],
            "failed_requests": [],
            "broken_assets": [],
        }
    finally:
        context.close()
