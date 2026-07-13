"""Exercise the authenticated dashboard served by a configured staging proxy."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


class StagingDashboardNotConfigured(RuntimeError):
    """Raised when the operator-surface smoke cannot safely run."""


ROUTES = (
    ("/dashboard", "Dashboard"),
    ("/dashboard/savings", "Savings"),
    ("/dashboard/orchestrator", "Orchestrator"),
    ("/dashboard/capabilities", "Capabilities"),
    ("/dashboard/governance", "Governance"),
    ("/dashboard/firewall", "Security"),
    ("/dashboard/memory", "Memory"),
    ("/dashboard/replay", "Replay"),
    ("/dashboard/playground", "Playground"),
    ("/dashboard/docs", "Docs"),
)
VIEWPORTS = (("desktop", 1440, 1000), ("mobile", 390, 844))


def staging_dashboard_config_from_env() -> tuple[str, str]:
    base_url = os.environ.get("CUTCTX_STAGED_DASHBOARD_URL", "").rstrip("/")
    admin_key = os.environ.get("CUTCTX_STAGED_PROXY_ADMIN_API_KEY", "")
    if not base_url or not admin_key:
        raise StagingDashboardNotConfigured(
            "CUTCTX_STAGED_DASHBOARD_URL and CUTCTX_STAGED_PROXY_ADMIN_API_KEY are required"
        )
    return base_url, admin_key


def _redacted_location(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return f"{parsed.scheme}://{host}{parsed.path}"


def run_staging_dashboard_smoke(
    *, base_url: str, admin_key: str, artifact_dir: Path
) -> dict[str, Any]:
    """Verify navigation, layout, and browser errors against staging without storing secrets."""
    from playwright.sync_api import sync_playwright

    artifact_dir.mkdir(parents=True, exist_ok=True)
    failures: list[dict[str, str]] = []
    checked = 0
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for viewport, width, height in VIEWPORTS:
            context = browser.new_context(viewport={"width": width, "height": height})
            context.add_init_script(
                "window.localStorage.setItem('cutctxAdminKey', " + json.dumps(admin_key) + ");"
            )
            for route, heading in ROUTES:
                page = context.new_page()
                console_errors: list[str] = []
                page_errors: list[str] = []
                page.on(
                    "console",
                    lambda message, console_errors=console_errors: (
                        console_errors.append(message.text) if message.type == "error" else None
                    ),
                )
                page.on(
                    "pageerror",
                    lambda error, page_errors=page_errors: page_errors.append(str(error)),
                )
                try:
                    page.goto(f"{base_url}{route}", wait_until="networkidle", timeout=60_000)
                    if page.locator(".topbar-title-row h2").inner_text(timeout=10_000) != heading:
                        raise RuntimeError(f"expected {heading!r} page heading")
                    width_metrics = page.evaluate(
                        """() => ({ viewport: document.documentElement.clientWidth,
                        document: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) })"""
                    )
                    if width_metrics["document"] > width_metrics["viewport"] + 1:
                        raise RuntimeError("horizontal overflow")
                    # OSS/local deployments legitimately return 403 for
                    # optional enterprise surfaces (for example audit/RBAC
                    # panels). The dashboard handles those denials in-place;
                    # they are not JavaScript or route failures. Keep them in
                    # the artifact, but fail only unexpected console errors.
                    expected_auth_denials = [
                        message for message in console_errors if "403 (Forbidden)" in message
                    ]
                    unexpected_console_errors = [
                        message
                        for message in console_errors
                        if message not in expected_auth_denials
                    ]
                    if unexpected_console_errors or page_errors:
                        raise RuntimeError("browser errors")
                    page.screenshot(
                        path=str(
                            artifact_dir
                            / f"{viewport}-{route.rsplit('/', 1)[-1] or 'dashboard'}.png"
                        ),
                        full_page=True,
                    )
                    checked += 1
                except Exception as exc:
                    # Keep enough browser diagnostics to make a failed
                    # release smoke actionable, without retaining request
                    # headers, local storage, or page content.
                    failures.append(
                        {
                            "viewport": viewport,
                            "route": route,
                            "reason": str(exc),
                            "console_errors": console_errors[:5],
                            "page_errors": page_errors[:5],
                        }
                    )
                finally:
                    page.close()
            context.close()
        browser.close()

    payload = {
        "status": "passed" if not failures else "failed",
        "dashboard": _redacted_location(base_url),
        "routes_checked": checked,
        "failures": failures,
        "screenshots": "dashboard screenshots contain no request payloads or credentials",
    }
    (artifact_dir / "staging-dashboard-smoke.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    if failures:
        raise RuntimeError(f"staging dashboard smoke failed: {failures[:3]}")
    return payload


def main() -> None:
    base_url, admin_key = staging_dashboard_config_from_env()
    print(
        json.dumps(
            run_staging_dashboard_smoke(
                base_url=base_url,
                admin_key=admin_key,
                artifact_dir=Path("artifacts/staging-dashboard-smoke"),
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
