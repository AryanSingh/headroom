const assert = require("node:assert/strict");
const { chromium } = require("playwright");
const { createFixtureServer, port } = require("../static-server.cjs");

async function main() {
  const server = createFixtureServer();
  await new Promise((resolve) => server.listen(port, "127.0.0.1", resolve));
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage();
    await page.goto(`http://127.0.0.1:${port}/`, { waitUntil: "networkidle" });
    assert.equal(await page.getByRole("heading", { name: "Atlas transfer review" }).isVisible(), true);
    await page.getByRole("button", { name: "Simulate unavailable evidence" }).click();
    const alert = page.getByRole("alert");
    const alertText = await alert.textContent();
    assert.match(alertText, /Evidence service is temporarily unavailable/);
    assert.equal(alertText.toLowerCase().includes("token"), false);
    assert.equal(await page.getByRole("button", { name: "Retry evidence check" }).isVisible(), true);
    console.log("PLAYWRIGHT_FIXTURE_PASS recovery-state-visible sensitive-detail-absent");
  } finally {
    await browser.close();
    await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  }
}

main().catch((error) => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
