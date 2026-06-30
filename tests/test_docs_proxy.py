from playwright.sync_api import sync_playwright

def test_docs():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        context.add_init_script("window.localStorage.setItem('cutctx_admin_key', 'admin_12345');")
        page = context.new_page()
        
        page.on("console", lambda msg: print(f"CONSOLE: {msg.text}"))
        page.on("pageerror", lambda exc: print(f"ERROR: {exc}"))
        
        page.goto("http://127.0.0.1:8787/dashboard/docs")
        page.wait_for_load_state("networkidle")
        
        try:
            page.wait_for_selector("text=Quick Start", timeout=2000)
            print("Docs page rendered successfully.")
        except Exception as e:
            print("Docs page failed to render!")
            print(page.locator("body").inner_text())
        browser.close()

if __name__ == "__main__":
    test_docs()
