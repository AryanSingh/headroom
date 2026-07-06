import os
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from cutctx.dashboard import get_dashboard_html


def test_debug():
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        
        dashboard_html = get_dashboard_html(prefer_react=True)
        root_dir = Path(__file__).parent.parent
        
        def handler(route):
            url = route.request.url
            print(f"REQUEST: {url}")
            if "cutctx.local" not in url:
                route.fulfill(status=200, body="")
                return
            if url.endswith("/dashboard") or url == "http://cutctx.local/":
                route.fulfill(status=200, content_type="text/html", body=dashboard_html)
                return
            if "/assets/" in url:
                asset_path = root_dir / "dashboard/dist" / url.split("cutctx.local/")[1]
                if asset_path.exists():
                    mime = "text/javascript" if url.endswith(".js") else "text/css"
                    route.fulfill(status=200, content_type=mime, body=asset_path.read_bytes(), headers={"Access-Control-Allow-Origin": "*"})
                    return
                print(f"MISSING ASSET: {asset_path}")
            if "/stats" in url:
                route.fulfill(status=200, content_type="application/json", body="{}")
                return
            route.fulfill(status=404, body="Not Found")
            
        page.route("**/*", handler)
        page.on("console", lambda msg: print(f"DEBUG CONSOLE: {msg.text}"))
        page.on("pageerror", lambda err: print(f"DEBUG PAGE ERROR: {err}"))
        
        page.goto("http://cutctx.local/dashboard")
        page.wait_for_timeout(2000)
        
