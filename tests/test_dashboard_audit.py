"""Deterministic Playwright audit matrix for the ten dashboard routes."""

from __future__ import annotations

import json
import os
import re
import signal
import socket
import subprocess
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass
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


@dataclass
class DashboardStartResult:
    """Outcome of :func:`start_dashboard`.

    Exactly one of ``(base_url, process)`` or ``error`` is populated: a
    successful start leaves ``error`` as ``None`` and hands back the running
    ``process`` for the caller to manage; a failed start always terminates
    any process it spawned and returns a diagnostic ``error`` message.
    """

    base_url: str | None
    process: subprocess.Popen | None
    error: str | None


def _drain_stream(stream, buffer: list[str]) -> None:
    """Continuously read a pipe into ``buffer`` so it never fills and blocks."""
    try:
        for line in iter(stream.readline, ""):
            buffer.append(line)
    except (ValueError, OSError):
        pass
    finally:
        try:
            stream.close()
        except OSError:
            pass


def _terminate_process(process: subprocess.Popen) -> None:
    """Terminate ``process`` (and its process group, if any) and reap it."""
    if process.poll() is not None:
        return
    pgid: int | None
    try:
        pgid = os.getpgid(process.pid)
    except (ProcessLookupError, OSError):
        pgid = None

    def _signal(sig: int) -> None:
        try:
            if pgid is not None:
                os.killpg(pgid, sig)
            else:
                process.send_signal(sig)
        except ProcessLookupError:
            pass

    _signal(signal.SIGTERM)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        _signal(signal.SIGKILL)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass


def _format_start_error(
    command: Sequence[str], port: int, elapsed: float, *, stdout: str, stderr: str
) -> str:
    return (
        "Dashboard server failed to become ready.\n"
        f"command: {list(command)!r}\n"
        f"port: {port}\n"
        f"elapsed: {elapsed:.2f}s\n"
        f"stdout:\n{stdout or '(empty)'}\n"
        f"stderr:\n{stderr or '(empty)'}\n"
    )


def start_dashboard(
    command: Sequence[str],
    *,
    cwd: Path = DASHBOARD_DIR,
    port: int | None = None,
    timeout_seconds: float = 20.0,
    ready_path: str = "/dashboard",
) -> DashboardStartResult:
    """Start ``command`` and wait for an HTTP readiness probe to succeed.

    Captures stdout/stderr (never ``DEVNULL``) so a failure can report the
    command, port, elapsed time, and the process's actual output. On any
    failure path the spawned process (and its process group) is terminated
    and waited on before returning; on success the running process is handed
    back to the caller, who owns shutting it down.
    """
    if port is None:
        port = _available_loopback_port()
    base_url = f"http://127.0.0.1:{port}"
    started_at = time.monotonic()

    try:
        process = subprocess.Popen(
            list(command),
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
    except OSError as exc:
        elapsed = time.monotonic() - started_at
        return DashboardStartResult(
            base_url=None,
            process=None,
            error=_format_start_error(command, port, elapsed, stdout="", stderr=str(exc)),
        )

    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    stdout_thread = threading.Thread(
        target=_drain_stream, args=(process.stdout, stdout_lines), daemon=True
    )
    stderr_thread = threading.Thread(
        target=_drain_stream, args=(process.stderr, stderr_lines), daemon=True
    )
    stdout_thread.start()
    stderr_thread.start()

    deadline = started_at + timeout_seconds
    ready = False
    while time.monotonic() < deadline:
        if process.poll() is not None:
            break
        try:
            with urlopen(f"{base_url}{ready_path}", timeout=1):
                ready = True
                break
        except (OSError, URLError):
            time.sleep(0.1)

    if ready:
        return DashboardStartResult(base_url=base_url, process=process, error=None)

    elapsed = time.monotonic() - started_at
    _terminate_process(process)
    stdout_thread.join(timeout=2)
    stderr_thread.join(timeout=2)
    return DashboardStartResult(
        base_url=None,
        process=None,
        error=_format_start_error(
            command,
            port,
            elapsed,
            stdout="".join(stdout_lines),
            stderr="".join(stderr_lines),
        ),
    )


def test_vite_start_failure_includes_stderr_and_command() -> None:
    result = start_dashboard(command=["false"], timeout_seconds=1)

    assert result.error is not None
    assert result.base_url is None
    assert result.process is None
    assert "command" in result.error
    assert "stderr" in result.error
    assert "false" in result.error


def test_vite_start_timeout_includes_command_port_and_elapsed() -> None:
    result = start_dashboard(command=["sleep", "5"], timeout_seconds=0.5)

    assert result.error is not None
    assert result.process is None
    assert "command" in result.error
    assert "port" in result.error
    assert "elapsed" in result.error
    assert "stderr" in result.error
    assert "sleep" in result.error


@pytest.fixture(scope="session")
def dashboard_server():
    base_url = os.environ.get("CUTCTX_DASHBOARD_AUDIT_BASE_URL")
    if base_url:
        yield base_url.rstrip("/")
        return

    port = _available_loopback_port()
    command = ["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", str(port)]
    result = start_dashboard(command=command, port=port, timeout_seconds=20.0)
    if result.error:
        pytest.fail(result.error)

    yield result.base_url
    _terminate_process(result.process)


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

    if route == "/orchestrator":
        # Keep the visual artifact meaningful: teardown captures the screenshot,
        # so this assertion must complete after the route leaves its loading shell.
        expect(page.get_by_text("Routing mode control", exact=True)).to_be_visible()

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
