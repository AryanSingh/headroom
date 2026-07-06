
with open("tests/test_dashboard_surfaces_playwright.py") as f:
    content = f.read()

content = content.replace(
    'if url.endswith("/stats") or url.endswith("/stats/recent"):',
    'if url.endswith("/stats") or url.endswith("/stats/recent") or "/stats-history" in url:'
)

with open("tests/test_dashboard_surfaces_playwright.py", "w") as f:
    f.write(content)
