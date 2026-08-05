---
id: EX-CH14-PLAYWRIGHT
kind: worked-example
chapter: CH-14
standards: [OWASP-WSTG-4.2, W3C-WCAG-2.2, NIST-SSDF-1.1]
preconditions: [Node.js with npm and npx, cached Playwright 1.61.1, local Chromium executable]
placement: engineering-handbook/examples/playwright
dependencies: [package.json, playwright.config.cjs, static-server.cjs, local-visual-test.cjs]
invocation: CI=true npm test
expected_output: PLAYWRIGHT_FIXTURE_PASS recovery-state-visible sensitive-detail-absent
failure_output: A missing accessible heading, missing alert/retry control, leaked token text, unavailable cached Playwright runtime, or nonzero process exit.
interpretation: The browser exercised a local recovery state and verified user-visible and sensitive-detail boundaries without contacting an external service.
remediation: Repair the tested accessibility contract, preserve the failing browser output, and rerun the fixture before release.
cleanup: The runner closes Chromium and the loopback-only static server in a finally block; it writes no persistent customer or test data.
---

# Product Atlas local visual recovery fixture

This package is a deterministic, local-only browser test specimen. The static
fixture has no API calls, tracking code, credentials, external fonts, or remote
assets. It serves on `127.0.0.1:41714`, opens Chromium headlessly, verifies the
transfer-review heading, simulates unavailable evidence, and asserts that the
recovery alert includes a retry action but no token-like sensitive detail.

Run actual browser evidence non-interactively:

```shell
CI=true npm test
```

Expected output:

```text
PLAYWRIGHT_FIXTURE_PASS recovery-state-visible sensitive-detail-absent
```

`example.yaml` intentionally runs `node manifest-check.cjs`, not the browser.
The handbook example runner prevents all network sockets—including loopback
listeners—so it cannot start the fixture server by design. The `npm test`
command above is the required separate, offline browser-evidence gate. It uses
the already-cached Playwright runtime through `npm root -g`; no registry request
or package download is made. A `package-lock.json` cannot be generated offline
here because npm's cache lacks the registry metadata for `playwright`.
