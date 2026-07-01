import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        print("Navigating to dashboard...")
        await page.goto("http://127.0.0.1:8787/dashboard")
        await page.wait_for_timeout(1000)
        
        # Fill in the admin key
        input_elem = page.locator("input[type='password']")
        if await input_elem.count() > 0:
            await input_elem.fill("admin_12345")
            
            # Click Save & Reload
            save_btn = page.locator("text='Save & Reload'")
            await save_btn.click()
            await page.wait_for_timeout(3000)
            
            await page.screenshot(path="dashboard_main.png")
            print("Main dashboard screenshot taken.")
            
            # Look for live feed drawer toggle
            live_feed = page.locator("text='Live Feed'")
            if await live_feed.count() > 0:
                await live_feed.first.click()
                await page.wait_for_timeout(2000)
                await page.screenshot(path="dashboard_live_feed.png")
                print("Live feed screenshot taken.")
            else:
                # maybe it's an icon or something else?
                # let's just dump the text of the page
                texts = await page.evaluate("() => document.body.innerText")
                print("Live Feed button not found! Page text:", texts[:200])
        else:
            print("Password input not found!")

        await browser.close()

asyncio.run(main())
