import time

from playwright.sync_api import sync_playwright


def take_screenshot():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        context.add_init_script("window.localStorage.setItem('cutctxAdminKey', 'admin_12345');")
        page = context.new_page()
        page.goto("http://localhost:5173/dashboard/capabilities")
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        page.screenshot(path="capabilities_screenshot.png")
        browser.close()


if __name__ == "__main__":
    take_screenshot()
