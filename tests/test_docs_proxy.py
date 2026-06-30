"""Optional live-proxy docs smoke test.

Run only when CUTCTX_LIVE_PROXY_TESTS=1 and a proxy is already serving on
http://127.0.0.1:8787. The deterministic docs surface coverage lives in
tests/test_docs_page.py.
"""

from __future__ import annotations

import os

import pytest

playwright = pytest.importorskip("playwright.sync_api")
expect = playwright.expect
sync_playwright = playwright.sync_playwright


@pytest.mark.skipif(
    os.environ.get("CUTCTX_LIVE_PROXY_TESTS") != "1",
    reason="set CUTCTX_LIVE_PROXY_TESTS=1 to run live proxy smoke checks",
)
def test_docs_live_proxy_smoke() -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            context = browser.new_context()
            context.add_init_script(
                "window.localStorage.setItem('cutctx_admin_key', 'admin_12345');"
            )
            page = context.new_page()
            page.goto("http://127.0.0.1:8787/dashboard/docs")
            page.wait_for_load_state("networkidle")
            expect(page.get_by_text("Quick Start", exact=True)).to_be_visible(timeout=5000)
        finally:
            browser.close()
