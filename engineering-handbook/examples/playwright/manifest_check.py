from pathlib import Path

for name in (
    "package.json",
    "playwright.config.cjs",
    "index.html",
    "fixture.js",
    "tests/local-visual-test.cjs",
):
    if not Path(name).is_file():
        raise SystemExit(f"missing fixture asset: {name}")

print("PLAYWRIGHT_MANIFEST_PASS local-fixture-assets-present")
