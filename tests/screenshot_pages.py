from playwright.sync_api import sync_playwright
import time

def take_screenshots():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        context.add_init_script("window.localStorage.setItem('cutctxAdminKey', 'admin_12345');")
        page = context.new_page()
        
        # Dashboard
        page.goto("http://localhost:5173/dashboard")
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        page.screenshot(path="dashboard_main_fixed.png")
        
        # Orchestrator
        page.goto("http://localhost:5173/dashboard/orchestrator")
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        page.screenshot(path="orchestrator_fixed.png")
        
        browser.close()

if __name__ == "__main__":
    take_screenshots()
