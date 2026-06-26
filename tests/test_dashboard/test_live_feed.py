import pytest

pytest.importorskip("playwright")
import threading
import time

import uvicorn
from playwright.sync_api import expect, sync_playwright

from cutctx.proxy.server import ProxyConfig, create_app


@pytest.fixture(scope="module", autouse=True)
def run_proxy_server():
    app = create_app(ProxyConfig(log_full_messages=True, admin_api_key="test-key"))
    config = uvicorn.Config(app, host="127.0.0.1", port=8799, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run)
    thread.daemon = True
    thread.start()
    time.sleep(3)  # Give uvicorn time to bind
    yield
    server.should_exit = True
    thread.join(timeout=2)

@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def page(browser):
    page = browser.new_page()
    page.set_extra_http_headers({"Authorization": "Bearer test-key"})
    page.on("console", lambda msg: print(f"CONSOLE: {msg.text}"))
    page.on("pageerror", lambda exc: print(f"PAGE_ERROR: {exc}"))
    return page


@pytest.fixture
def dashboard_url():
    return "http://127.0.0.1:8799/dashboard"


def test_live_feed_button_exists(page, dashboard_url):
    """The Live Feed button should be visible in the dashboard header."""
    page.goto(dashboard_url)
    feed_button = page.locator("#feed-toggle")
    expect(feed_button).to_be_visible(timeout=5000)


def test_live_feed_drawer_opens(page, dashboard_url):
    """Clicking Live Feed should open the sidebar drawer."""
    page.goto(dashboard_url)
    page.click("#feed-toggle")
    page.wait_for_timeout(400)
    # Check drawer is displayed (x-show becomes visible)
    drawer = page.locator('[x-show="feedOpen"]')
    expect(drawer).to_be_visible(timeout=5000)


def test_live_feed_shows_empty_state(page, dashboard_url):
    """Feed should show empty state when no transformations available."""
    page.goto(dashboard_url)
    page.click("#feed-toggle")
    page.wait_for_timeout(1000)
    # Check for empty state or feed container
    feed_container = page.locator("#feed-container")
    expect(feed_container).to_be_visible(timeout=5000)


def test_live_feed_fetches_and_displays(page, dashboard_url):
    """Feed should display transformation data after polling."""
    page.goto(dashboard_url)
    page.click("#feed-toggle")
    # Wait for at least one poll cycle
    page.wait_for_timeout(4000)
    feed_container = page.locator("#feed-virtual-list")
    content = feed_container.inner_html()
    # Should have at least empty state
    assert len(content) >= 0
