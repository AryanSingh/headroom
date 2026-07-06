from pathlib import Path

from playwright.sync_api import sync_playwright

from cutctx.dashboard import get_dashboard_html


def _install_dashboard_routes(page) -> None:
    dashboard_html = get_dashboard_html(prefer_react=True)
    root_dir = Path(".").absolute()

    def handler(route) -> None:
        url = route.request.url

        if "cutctx.local" not in url:
            route.fulfill(status=200, body="")
            return

        if (
            url.endswith("/dashboard")
            or url.endswith("/")
            or url.endswith("playground")
            or url.endswith("firewall")
            or url.endswith("governance")
            or url.endswith("memory")
            or url == "http://cutctx.local/"
        ):
            route.fulfill(status=200, content_type="text/html", body=dashboard_html)
            return

        if "/assets/" in url:
            asset_path = root_dir / "dashboard/dist" / url.split("cutctx.local/")[1]
            if asset_path.exists():
                mime = "text/javascript" if url.endswith(".js") else "text/css"
                route.fulfill(
                    status=200,
                    content_type=mime,
                    body=asset_path.read_bytes(),
                    headers={"Access-Control-Allow-Origin": "*"},
                )
                return

        if "/stats" in url:
            route.fulfill(status=200, content_type="application/json", body="{}")
            return

        route.fulfill(status=404, body="Not Found")

    page.route("**/*", handler)

def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1720, "height": 1400}, color_scheme="dark")
        _install_dashboard_routes(page)

        page.on("console", lambda msg: print(f"CONSOLE: {msg.text}"))
        page.on("pageerror", lambda err: print(f"PAGE ERROR: {err}"))

        page.goto("http://cutctx.local/dashboard", wait_until="networkidle")

        import time
        time.sleep(2)

        print("DOM BODY:")
        print(page.evaluate("document.body.innerHTML")[:1000])

if __name__ == "__main__":
    main()
