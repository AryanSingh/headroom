import asyncio
import os
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        errors = []
        page.on("pageerror", lambda err: errors.append(err.message))
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)

        print("Navigating to dashboard...")
        await page.goto("http://127.0.0.1:8787/dashboard")
        
        # Inject the admin key to bypass login
        await page.evaluate(f"window.localStorage.setItem('cutctxAdminKey', '1DioiRWMFyQ4ShyP6M9h6uQrmo4dnqr3OobymGIBJxk')")
        
        # Reload to apply the key
        await page.reload()
        
        # Wait for data to load
        await page.wait_for_timeout(3000)
        
        print(f"Console errors: {errors}")
        
        await page.screenshot(path="dashboard_screenshot.png")
        print("Screenshot saved to dashboard_screenshot.png")
        
        # Click on Firewall
        print("Clicking on Firewall...")
        await page.get_by_role("link", name="Security").click()
        await page.wait_for_timeout(2000)
        await page.screenshot(path="firewall_screenshot.png")
        print("Screenshot saved to firewall_screenshot.png")

        # Click on Memory
        print("Clicking on Memory...")
        await page.get_by_role("link", name="Memory").click()
        await page.wait_for_timeout(2000)
        await page.screenshot(path="memory_screenshot.png")
        print("Screenshot saved to memory_screenshot.png")

        # Light mode
        print("Taking light mode screenshots...")
        light_page = await browser.new_page(color_scheme="light")
        await light_page.goto("http://127.0.0.1:8787/dashboard")
        await light_page.evaluate(f"window.localStorage.setItem('cutctxAdminKey', '1DioiRWMFyQ4ShyP6M9h6uQrmo4dnqr3OobymGIBJxk')")
        await light_page.reload()
        await light_page.wait_for_timeout(3000)
        
        await light_page.screenshot(path="dashboard_light.png")
        await light_page.get_by_role("link", name="Security").click()
        await light_page.wait_for_timeout(2000)
        await light_page.screenshot(path="firewall_light.png")
        await light_page.get_by_role("link", name="Memory").click()
        await light_page.wait_for_timeout(2000)
        await light_page.screenshot(path="memory_light.png")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
