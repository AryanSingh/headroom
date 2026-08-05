const fs = require("node:fs");

for (const file of ["package.json", "playwright.config.cjs", "index.html", "fixture.js", "tests/local-visual-test.cjs"]) {
  if (!fs.existsSync(file)) throw new Error(`missing fixture asset: ${file}`);
}
console.log("PLAYWRIGHT_MANIFEST_PASS local-fixture-assets-present");
