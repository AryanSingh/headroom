# CutCtx Commerce Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make CutCtx’s self-service purchase, license retrieval, account management, and activation journey clear while keeping PitchToShip as the sole commerce authority.

**Architecture:** CutCtx remains a static discovery site. It adds consistent navigation and deterministic outbound links to PitchToShip’s existing `/billing` and `/account` surfaces, plus local CLI activation guidance. PitchToShip’s React billing and account pages are the system of record for Razorpay checkout, license issuance, entitlement lookup, and billing management; its deployed frontend must be rebuilt and published from the current CutCtx-aware source.

**Tech Stack:** Static HTML/CSS and pytest in Headroom; React 18, TypeScript, Vite, Vitest, Cloudflare Pages Functions, Render-backed license API, and Razorpay in PitchToShip.

## Global Constraints

- PitchToShip is the exclusive checkout, payment-verification, license-issuance, billing, and customer-account authority.
- Do not add a CutCtx-hosted payment form, license-recovery form, customer account, payment SDK, payment secret, webhook secret, or checkout-email storage.
- Use canonical hosted URLs exactly: `https://pitchtoship.com/billing?product=cutctx&plan=starter&billing=monthly`, `https://pitchtoship.com/billing?product=cutctx&plan=studio&billing=monthly`, and `https://pitchtoship.com/account`.
- Preserve Builder as free, Team → `starter`, Business → `studio`, and Enterprise as sales-led.
- The deployed PitchToShip copy must name CutCtx and Razorpay; it must not present Headroom or Stripe as the self-service CutCtx payment path.
- Never test a live payment with production credentials. Use Razorpay test mode only after the provider owner has configured the required test credentials.

---

## File structure

### Headroom / CutCtx site

- `website/index.html` — global home-page navigation/footer conversion links.
- `website/{routing,integrations,pricing,docs,security,terms,privacy,refunds}/index.html` — shared global navigation/footer conversion links.
- `website/pricing/index.html` — paid-plan labels, merchant disclosure, and license-management CTA.
- `website/docs/index.html` — explicit local activation instruction and account-recovery link.
- `tests/website/test_static_site.py` — static commerce-link and activation-copy regression coverage.

### PitchToShip commerce site

- `src/pages/BillingPage.tsx` — CutCtx-context billing presentation and Razorpay checkout UI.
- `src/pages/LicensePortalPage.tsx` — purchaser-facing license/subscription lookup experience.
- `src/data/billing.ts` — canonical purchasable plan/catalogue copy including CutCtx.
- `src/__tests__/billing-page.test.tsx` — unit coverage for CutCtx deep links and purchases.
- `src/__tests__/license-portal-page.test.tsx` — new component test for license lookup affordances.
- `functions/_shared/pricing.js` — server-side catalogue source of truth used for order amounts and purchasability.
- `functions/api/razorpay/create-order.js` and `functions/api/razorpay/verify.js` — existing secure payment/issuance path; inspect and retain the current amount/signature protections.
- `functions/api/licenses/my-licenses.ts` and `functions/api/billing/entitlements.ts` — existing server proxies used by the account portal.

### Deployment and evidence

- `docs/superpowers/specs/2026-07-23-cutctx-pitchtoship-commerce-design.md` — approved cross-site ownership contract.
- `audit/manual-verification/` — add dated, non-secret screenshots or text evidence of the deployed pricing, billing, and account-entry surfaces.

## Task 1: Lock CutCtx’s public commerce contract with tests

**Files:**

- Modify: `tests/website/test_static_site.py`
- Modify: `website/index.html`
- Modify: `website/{routing,integrations,pricing,docs,security,terms,privacy,refunds}/index.html`

**Interfaces:**

- Consumes: the approved PitchToShip URLs in the global constraints.
- Produces: every public CutCtx page exposes `href="/pricing/"` and `href="https://pitchtoship.com/account"` through its navigational shell.

- [ ] **Step 1: Add the failing static navigation contract**

  Add this test to `tests/website/test_static_site.py`:

  ```python
  def test_public_navigation_exposes_purchase_and_license_management():
      for page in PUBLIC_PAGES:
          html = page.read_text(encoding="utf-8")
          assert 'href="/pricing/"' in html
          assert 'href="https://pitchtoship.com/account"' in html
  ```

- [ ] **Step 2: Run the focused test and confirm it fails**

  Run:

  ```bash
  rtk pytest tests/website/test_static_site.py::test_public_navigation_exposes_purchase_and_license_management -q
  ```

  Expected: FAIL because the non-home pages omit one or both commerce links.

- [ ] **Step 3: Add the two global links to every public page shell**

  In each page’s primary navigation, place the two links with the existing non-button navigation links:

  ```html
  <a href="/pricing/">Pricing</a>
  <a href="https://pitchtoship.com/account">Manage license</a>
  ```

  In each footer navigation, add the same links using the existing footer link style:

  ```html
  <a href="/pricing/">Pricing</a>
  <a href="https://pitchtoship.com/account">Manage license</a>
  ```

  Do not add an email query parameter to the account link. The customer supplies their checkout email only after arriving at PitchToShip.

- [ ] **Step 4: Re-run the focused and full static-site suites**

  Run:

  ```bash
  rtk pytest tests/website/test_static_site.py -q
  ```

  Expected: PASS.

- [ ] **Step 5: Commit the CutCtx navigation contract**

  ```bash
  rtk git add tests/website/test_static_site.py website/index.html website/routing/index.html website/integrations/index.html website/pricing/index.html website/docs/index.html website/security/index.html website/terms/index.html website/privacy/index.html website/refunds/index.html
  GIT_TERMINAL_PROMPT=0 GIT_EDITOR=true rtk git commit -m "feat: expose CutCtx purchase and license links"
  ```

## Task 2: Clarify paid purchase, post-purchase, and local activation on CutCtx

**Files:**

- Modify: `tests/website/test_static_site.py`
- Modify: `website/pricing/index.html`
- Modify: `website/docs/index.html`

**Interfaces:**

- Consumes: canonical Team/Business checkout URLs and the `cutctx license activate <license-key>` local command.
- Produces: visible Buy Team, Buy Business, Manage license, and activation guidance without a CutCtx payment/account implementation.

- [ ] **Step 1: Add failing content-contract tests**

  Add this test:

  ```python
  def test_pricing_explains_checkout_and_license_management():
      pricing = read_page("website/pricing/index.html")
      assert ">Buy Team<" in pricing
      assert ">Buy Business<" in pricing
      assert "License key emailed after payment" in pricing
      assert 'href="https://pitchtoship.com/account"' in pricing
      assert "Manage license" in pricing


  def test_docs_explains_how_to_activate_and_recover_a_paid_license():
      docs = read_page("website/docs/index.html")
      assert "cutctx license activate <license-key>" in docs
      assert 'href="https://pitchtoship.com/account"' in docs
  ```

- [ ] **Step 2: Run the new static contract tests and confirm failure**

  Run:

  ```bash
  rtk pytest tests/website/test_static_site.py::test_pricing_explains_checkout_and_license_management tests/website/test_static_site.py::test_docs_explains_how_to_activate_and_recover_a_paid_license -q
  ```

  Expected: FAIL because the labels, delivery language, and account route are absent.

- [ ] **Step 3: Implement the limited CutCtx copy changes**

  In `website/pricing/index.html`, replace the paid CTAs with:

  ```html
  <a class="button button-primary" data-cta="team-checkout" data-cta-placement="pricing-card" href="https://pitchtoship.com/billing?product=cutctx&amp;plan=starter&amp;billing=monthly">Buy Team</a>
  <p class="merchant-note">Secure checkout at PitchToShip · License key emailed after payment</p>
  ```

  and the equivalent Business link with `plan=studio` and label `Buy Business`. Add this account action to the merchant panel:

  ```html
  <a class="button button-secondary" data-cta="manage-license" data-cta-placement="merchant-panel" href="https://pitchtoship.com/account">Manage license</a>
  ```

  In `website/docs/index.html`, add a short “Activate a paid license” section after quick-start setup with:

  ```html
  <pre><code>cutctx license activate &lt;license-key&gt;</code></pre>
  <p>Your license key arrives after a successful PitchToShip purchase. To find it again or manage your subscription, use the <a href="https://pitchtoship.com/account">PitchToShip account portal</a>.</p>
  ```

  Retain all existing merchant disclosure and do not name a payment processor on CutCtx.

- [ ] **Step 4: Run the focused and complete CutCtx website suites**

  Run:

  ```bash
  rtk pytest tests/website/test_static_site.py -q
  ```

  Expected: PASS.

- [ ] **Step 5: Commit the CutCtx conversion copy**

  ```bash
  rtk git add tests/website/test_static_site.py website/pricing/index.html website/docs/index.html
  GIT_TERMINAL_PROMPT=0 GIT_EDITOR=true rtk git commit -m "feat: clarify CutCtx checkout and activation"
  ```

## Task 3: Validate PitchToShip’s CutCtx purchase and account surfaces in source

**Files:**

- Modify: `/Users/aryansingh/Documents/Claude/Projects/pitchtoship/src/__tests__/billing-page.test.tsx`
- Create: `/Users/aryansingh/Documents/Claude/Projects/pitchtoship/src/__tests__/license-portal-page.test.tsx`
- Modify only if tests reveal a gap: `/Users/aryansingh/Documents/Claude/Projects/pitchtoship/src/pages/BillingPage.tsx`, `/Users/aryansingh/Documents/Claude/Projects/pitchtoship/src/pages/LicensePortalPage.tsx`, `/Users/aryansingh/Documents/Claude/Projects/pitchtoship/src/data/billing.ts`

**Interfaces:**

- Consumes: `/billing?product=cutctx&plan=starter|studio&billing=monthly` and `/account?email=<checkout-email>`.
- Produces: a CutCtx-aware billing context, enabled Razorpay checkout after valid email entry, and an account portal that explicitly exposes license/subscription lookup.

- [ ] **Step 1: Expand the failing CutCtx billing test**

  In `src/__tests__/billing-page.test.tsx`, add assertions to the existing deep-link test:

  ```tsx
  expect(screen.getByRole('button', { name: 'Choose Starter' })).toBeEnabled();
  expect(screen.getByText(/secure checkout via razorpay/i)).toBeInTheDocument();
  expect(screen.getByText('CutCtx')).toBeInTheDocument();
  ```

  Render `LicensePortalPage` in the new `license-portal-page.test.tsx` and assert the entry route is understandable without leaking a key:

  ```tsx
  expect(screen.getByRole('heading', { name: 'License portal' })).toBeInTheDocument();
  expect(screen.getByLabelText('Email address used at checkout')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Find licenses' })).toBeInTheDocument();
  expect(screen.getByText(/payment methods and invoices live in the shared account portal/i)).toBeInTheDocument();
  ```

- [ ] **Step 2: Run the affected Vitest files and establish the baseline**

  Run:

  ```bash
  CI=true rtk npm run test -- src/__tests__/billing-page.test.tsx src/__tests__/license-portal-page.test.tsx
  ```

  Expected: the new portal test initially fails until the test harness supplies `MemoryRouter`; the existing billing test may expose a mismatch between source copy and the current expectation. Fix only test harness/setup or source behavior required by this plan.

- [ ] **Step 3: Make the portal/test setup reflect the existing public contract**

  Use the same router wrapper as the billing test:

  ```tsx
  render(
    <MemoryRouter initialEntries={['/account']}>
      <LicensePortalPage />
    </MemoryRouter>,
  );
  ```

  Keep lookup as an email-based request to the existing `/api/licenses/my-licenses` and `/api/billing/entitlements` proxies. Do not render, log, or return an unmasked license key from the page. If source asserts stale `Headroom` or `Stripe` copy, replace it with the existing `CutCtx`/`Razorpay` language from the approved design.

- [ ] **Step 4: Run all unit tests and type checks in PitchToShip**

  Run:

  ```bash
  CI=true rtk npm run test
  CI=true rtk npm run lint
  ```

  Expected: PASS.

- [ ] **Step 5: Commit the independently verified PitchToShip source changes**

  ```bash
  rtk git -C /Users/aryansingh/Documents/Claude/Projects/pitchtoship add src/pages/BillingPage.tsx src/pages/LicensePortalPage.tsx src/data/billing.ts src/__tests__/billing-page.test.tsx src/__tests__/license-portal-page.test.tsx
  GIT_TERMINAL_PROMPT=0 GIT_EDITOR=true rtk git -C /Users/aryansingh/Documents/Claude/Projects/pitchtoship commit -m "feat: verify CutCtx billing and license portal"
  ```

## Task 4: Build and deploy the existing PitchToShip commerce frontend

**Files:**

- Modify: no source file when Tasks 1–3 are complete.
- Verify: `/Users/aryansingh/Documents/Claude/Projects/pitchtoship/wrangler.toml`, `/Users/aryansingh/Documents/Claude/Projects/pitchtoship/functions/api/razorpay/create-order.js`, `/Users/aryansingh/Documents/Claude/Projects/pitchtoship/functions/api/razorpay/verify.js`

**Interfaces:**

- Consumes: configured Cloudflare Pages project `pitchtoship`, Render `SERVER_URL`, and non-production Razorpay test credentials for transactional smoke testing.
- Produces: the built frontend served at `https://pitchtoship.com/billing` and `https://pitchtoship.com/account`.

- [ ] **Step 1: Confirm source configuration does not accept browser-provided amounts or secrets**

  Run:

  ```bash
  rtk proxy rg -n "getCheckoutAmount|RAZORPAY_KEY_SECRET|userEmail|licenseKey" functions/_shared/pricing.js functions/api/razorpay/create-order.js functions/api/razorpay/verify.js
  ```

  Expected: price derives server-side through `getCheckoutAmount`; `RAZORPAY_KEY_SECRET` appears only in server-side function code; checkout requires a valid email; payment verification delegates issuance to the license service.

- [ ] **Step 2: Build the production artifact before deploying**

  Run:

  ```bash
  CI=true rtk npm run build
  ```

  Expected: PASS with a fresh `dist/` artifact.

- [ ] **Step 3: Deploy only the PitchToShip Pages project**

  Run:

  ```bash
  CI=true rtk npm run deploy:main
  ```

  Expected: Wrangler reports the deployment URL and successful publication for project `pitchtoship`.

  Do not deploy, modify, or delete the independent `cutctx.com` Cloudflare zone or any secret while publishing this frontend.

- [ ] **Step 4: Commit deployment evidence only**

  Add a dated text file under `audit/manual-verification/` containing the deploy URL, timestamp, non-secret build/test command results, and the exact live URLs inspected. Do not record customer emails, license keys, payment IDs, or gateway credentials.

  ```bash
  rtk git add audit/manual-verification/YYYY-MM-DD-pitchtoship-commerce-deploy.md
  GIT_TERMINAL_PROMPT=0 GIT_EDITOR=true rtk git commit -m "docs: record PitchToShip commerce deployment"
  ```

## Task 5: Validate the deployed CutCtx-to-PitchToShip customer journey

**Files:**

- Create: `audit/manual-verification/2026-07-23-cutctx-commerce-smoke.md`
- Verify: `https://cutctx.com/pricing/`, `https://pitchtoship.com/billing?product=cutctx&plan=starter&billing=monthly`, `https://pitchtoship.com/account`

**Interfaces:**

- Consumes: deployed static CutCtx site and deployed PitchToShip Pages site.
- Produces: documented, reproducible evidence that visitors can discover buy, license management, and activation without performing a real purchase.

- [ ] **Step 1: Open the three canonical live pages in a browser**

  Inspect the visible page state at desktop and mobile widths. On CutCtx, confirm the header/footer show Pricing and Manage license, and pricing shows Buy Team, Buy Business, and the emailed-license disclosure. On PitchToShip, confirm the billing page recognizes CutCtx, names Razorpay accurately, and the account page exposes license lookup.

- [ ] **Step 2: Verify the purchase-link handoff without submitting checkout**

  Confirm the Team card leads exactly to:

  ```text
  https://pitchtoship.com/billing?product=cutctx&plan=starter&billing=monthly
  ```

  Confirm the Business card leads exactly to:

  ```text
  https://pitchtoship.com/billing?product=cutctx&plan=studio&billing=monthly
  ```

  Do not enter email, payment data, or submit a checkout in the production environment.

- [ ] **Step 3: Run the test-mode end-to-end purchase only if test credentials are configured**

  With Razorpay test mode and a designated test email, complete a test checkout. Then verify all four outputs: a verified payment response, a newly issued license in the account portal, successful `cutctx license activate <test-license-key>` validation against the test service, and no paid entitlement after revoking/expiring the test key. Redact the email and key from all output.

- [ ] **Step 4: Record browser and test evidence**

  Write `audit/manual-verification/2026-07-23-cutctx-commerce-smoke.md` with the UTC timestamp, deployed URLs, checked UI labels, link destinations, viewport sizes, automated test output, and the test-mode result (or explicitly state that credentials were not configured). Include no secrets or customer data.

- [ ] **Step 5: Run final regression suites and commit evidence**

  Run:

  ```bash
  rtk pytest tests/website/test_static_site.py -q
  CI=true rtk npm --prefix /Users/aryansingh/Documents/Claude/Projects/pitchtoship run test
  CI=true rtk npm --prefix /Users/aryansingh/Documents/Claude/Projects/pitchtoship run build
  ```

  Expected: all commands PASS. Then commit only the verification record:

  ```bash
  rtk git add audit/manual-verification/2026-07-23-cutctx-commerce-smoke.md
  GIT_TERMINAL_PROMPT=0 GIT_EDITOR=true rtk git commit -m "docs: verify CutCtx commerce journey"
  ```

## Plan self-review

- Spec coverage: Tasks 1–2 cover CutCtx discovery and activation without duplicating commerce. Task 3 proves the PitchToShip source contract. Task 4 handles the stale production deployment. Task 5 proves the complete public journey and reserves transactional verification for test mode.
- Placeholder scan: no unresolved implementation steps, unspecified test assertions, or generic error-handling instructions remain.
- Interface consistency: CutCtx uses only the documented hosted URLs; PitchToShip receives `product=cutctx`, `plan=starter|studio`, and optional account email only inside its own origin.
