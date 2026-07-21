# CutCtx Cloudflare Launch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Launch an isolated, high-conversion CutCtx marketing site on `cutctx.com`, with accurate product claims and PitchToShip-hosted commerce, without changing existing PitchToShip infrastructure.

**Architecture:** A dependency-free static site in `website/` is deployed as a new Cloudflare Pages project. The source contains all public product, pricing, documentation-entry, security, and legal-link pages; Cloudflare owns the new `cutctx.com` zone and Pages custom-domain routing. Checkout remains a normal outbound link to the existing PitchToShip billing path, so the CutCtx site contains no payment credentials, webhook logic, or order creation.

**Tech Stack:** Semantic HTML, one shared CSS file, small vanilla JavaScript for mobile navigation and CTA event dispatch, Python/pytest static-site checks, Cloudflare Pages, Cloudflare DNS, BigRock authoritative nameserver delegation.

## Global Constraints

- Do not edit, delete, redeploy, or change DNS for `pitchtoship.com` or any other existing Cloudflare zone, Worker, Pages project, record, route, secret, or setting.
- Keep `PitchToShip` as merchant of record, checkout authority, invoice issuer, license authority, and customer account portal.
- Every purchase-adjacent page must state: `CutCtx is a product of PitchToShip. Payments, invoices, licensing, and customer account management are provided by PitchToShip.`
- Do not claim a guaranteed savings percentage, formal security certification, hosted prompt analytics, or a complete enterprise admin UI.
- Do not publish the site until an owner supplies/approves the exact legal business name, business address, support email, privacy email, refund/cancellation policy, and governing jurisdiction.
- Do not add third-party behavioural analytics or transmit prompt/customer-content data.
- Use only an isolated `cutctx.com` Cloudflare zone and a new dedicated CutCtx Pages project.
- Use `rtk` before all shell commands in this repository.

---

## File structure

| File | Responsibility |
| --- | --- |
| `website/index.html` | Homepage, conversion narrative, capability proof, primary and secondary CTAs. |
| `website/pricing/index.html` | Builder/Team/Business/Enterprise packaging and checkout/sales routes. |
| `website/docs/index.html` | Fast technical evaluation path: install, wrap, verify, and link to repository documentation. |
| `website/security/index.html` | Implementation-aligned local-first security and data-handling summary. |
| `website/terms/index.html` | Final, owner-approved Terms rendered from the legal-page template. |
| `website/privacy/index.html` | Final, owner-approved Privacy Notice rendered from the legal-page template. |
| `website/refunds/index.html` | Final, owner-approved cancellation/refund policy. |
| `website/assets/site.css` | Responsive visual system, reusable components, dark surface, focus states, and print-safe legal styling. |
| `website/assets/site.js` | Mobile navigation and privacy-preserving custom CTA events only. |
| `website/_headers` | Static security headers for all public pages. |
| `website/_redirects` | Canonical route redirects and historical-name normalization only. |
| `website/robots.txt` | Allows public search indexing after production launch. |
| `website/sitemap.xml` | Canonical public URLs. |
| `tests/website/test_static_site.py` | Static contract tests for CTA URLs, merchant disclosure, capabilities, legal links, headers, redirects, and no prohibited claims. |
| `docs/launch/cutctx-cloudflare-runbook.md` | Exact owner-facing Cloudflare/BigRock cutover and rollback record. |

## External values that must be obtained before production publication

The site can be built and previewed without these values. Before any public deployment, obtain the owner-approved values below and insert them exactly into the legal pages and the checkout-support section:

- registered legal entity name;
- registered business address and applicable tax registration information;
- legal-support email and privacy-contact email;
- exact refund/cancellation policy accepted by the payment processor;
- governing-law jurisdiction and effective date;
- confirmed PitchToShip checkout URL and sales-contact URL.

### Task 1: Establish the launch configuration and legal publication gate

**Files:**
- Create: `docs/launch/cutctx-cloudflare-runbook.md`
- Test: `tests/website/test_static_site.py`

**Interfaces:**
- Consumes: owner-approved legal values and the existing checkout contract `https://pitchtoship.com/billing?product=cutctx&plan=<plan>&billing=<cadence>`.
- Produces: `launch_configuration` documented as `{ legal_entity_name, legal_address, support_email, privacy_email, refund_policy_url, governing_jurisdiction, effective_date, checkout_base_url, sales_url }` for the static pages.

- [ ] **Step 1: Write the failing legal-gate test**

```python
from pathlib import Path


def test_public_legal_pages_do_not_contain_unapproved_legacy_identity():
    pages = [
        Path("website/terms/index.html"),
        Path("website/privacy/index.html"),
        Path("website/refunds/index.html"),
    ]
    rendered = "\n".join(page.read_text(encoding="utf-8") for page in pages)
    assert "Cutctx Labs" not in rendered
    assert "sales@payzli.com" not in rendered
    assert "{{" not in rendered
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `rtk pytest tests/website/test_static_site.py::test_public_legal_pages_do_not_contain_unapproved_legacy_identity -q`

Expected: FAIL because the public legal pages do not exist yet.

- [ ] **Step 3: Write the launch runbook and record the publication gate**

Create `docs/launch/cutctx-cloudflare-runbook.md` with these exact sections: `Scope protection`, `Prerequisites`, `Cloudflare zone`, `BigRock nameserver change`, `Pages deployment`, `Custom domains`, `Production verification`, and `Rollback`. In `Prerequisites`, list the eight required external values above and state: `Do not publish a public legal route or direct checkout button until every value has been supplied and approved by the owner.`

- [ ] **Step 4: Re-run the focused test**

Run: `rtk pytest tests/website/test_static_site.py::test_public_legal_pages_do_not_contain_unapproved_legacy_identity -q`

Expected: FAIL because public pages are deliberately not created until Task 5.

- [ ] **Step 5: Commit the runbook and test scaffold**

```bash
rtk git add docs/launch/cutctx-cloudflare-runbook.md tests/website/test_static_site.py
rtk git commit -m "docs: add CutCtx launch runbook"
```

### Task 2: Build the tested static-site foundation

**Files:**
- Create: `website/assets/site.css`
- Create: `website/assets/site.js`
- Create: `website/_headers`
- Create: `website/_redirects`
- Create: `website/robots.txt`
- Create: `website/sitemap.xml`
- Modify: `tests/website/test_static_site.py`

**Interfaces:**
- Consumes: public URLs rooted at `https://cutctx.com`.
- Produces: shared presentation assets and deployment contracts consumed by every route in Tasks 3–5.

- [ ] **Step 1: Write failing static-contract tests**

```python
def test_static_delivery_contracts_are_present():
    headers = Path("website/_headers").read_text(encoding="utf-8")
    redirects = Path("website/_redirects").read_text(encoding="utf-8")
    assert "Strict-Transport-Security" in headers
    assert "Content-Security-Policy" in headers
    assert "X-Content-Type-Options: nosniff" in headers
    assert "www.cutctx.com/* https://cutctx.com/:splat 301" in redirects


def test_sitemap_uses_only_cutctx_canonical_urls():
    sitemap = Path("website/sitemap.xml").read_text(encoding="utf-8")
    assert "https://cutctx.com/" in sitemap
    assert "https://www.cutctx.com" not in sitemap
```

- [ ] **Step 2: Run the foundation tests to verify failure**

Run: `rtk pytest tests/website/test_static_site.py -q`

Expected: FAIL because the `website/` deployment contracts do not exist.

- [ ] **Step 3: Implement the foundation**

Create a CSS design system with the variables `--surface: #09111f`, `--panel: #101c30`, `--text: #f5f8ff`, `--muted: #adbbd3`, `--accent: #68e6b3`, and `--focus: #8ab4ff`. Include responsive layout classes named `.site-shell`, `.nav`, `.hero`, `.proof-grid`, `.feature-grid`, `.pricing-grid`, `.cta-band`, and `.legal-copy`; make keyboard focus visible with `:focus-visible`.

Create `website/assets/site.js` that toggles the `[data-mobile-nav]` element from a button with `data-mobile-nav-toggle`, then dispatches only a browser-local `CustomEvent("cutctx:cta", { detail: { action } })` from elements that carry `data-cta`. Do not send network requests or load analytics SDKs.

Create `website/_headers` with these exact baseline directives:

```text
/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=()
  X-Frame-Options: DENY
  Strict-Transport-Security: max-age=31536000; includeSubDomains
  Content-Security-Policy: default-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'; img-src 'self' data:; script-src 'self'; style-src 'self'
```

Create `website/_redirects` with `www.cutctx.com/* https://cutctx.com/:splat 301` and `/index.html / 301`. Create `robots.txt` with `User-agent: *` and `Allow: /`. Create `sitemap.xml` containing the seven canonical routes named in the File structure table.

- [ ] **Step 4: Run the foundation tests to verify success**

Run: `rtk pytest tests/website/test_static_site.py -q`

Expected: PASS for the foundation contracts; route tests still fail until routes exist.

- [ ] **Step 5: Commit the foundation**

```bash
rtk git add website tests/website/test_static_site.py
rtk git commit -m "feat: add CutCtx static site foundation"
```

### Task 3: Implement homepage, product proof, and pricing conversion routes

**Files:**
- Create: `website/index.html`
- Create: `website/pricing/index.html`
- Modify: `tests/website/test_static_site.py`

**Interfaces:**
- Consumes: `website/assets/site.css`, `website/assets/site.js`, and the checkout contract from Task 1.
- Produces: `/` and `/pricing` routes whose CTA attributes are verified by Task 6.

- [ ] **Step 1: Write failing product-route tests**

```python
def test_homepage_has_product_and_merchant_disclosure():
    home = Path("website/index.html").read_text(encoding="utf-8")
    assert "Reduce LLM context overhead" in home
    assert "CutCtx is a product of PitchToShip" in home
    assert "OpenAI" in home and "Anthropic" in home and "Amazon Bedrock" in home
    assert "guaranteed" not in home.lower()


def test_pricing_routes_to_pitchtoship_without_payment_secrets():
    pricing = Path("website/pricing/index.html").read_text(encoding="utf-8")
    assert "https://pitchtoship.com/billing?product=cutctx&amp;plan=starter&amp;billing=monthly" in pricing
    assert "https://pitchtoship.com/billing?product=cutctx&amp;plan=studio&amp;billing=monthly" in pricing
    assert "Razorpay" not in pricing
    assert "RAZORPAY_" not in pricing
```

- [ ] **Step 2: Run the route tests to verify failure**

Run: `rtk pytest tests/website/test_static_site.py::test_homepage_has_product_and_merchant_disclosure tests/website/test_static_site.py::test_pricing_routes_to_pitchtoship_without_payment_secrets -q`

Expected: FAIL because the homepage and pricing route do not exist.

- [ ] **Step 3: Implement `website/index.html`**

Use semantic `header`, `main`, `section`, `nav`, `footer`, and one `h1`. The hero headline must be `Reduce LLM context overhead without changing your AI workflow.` Place the two CTAs in the hero: `Start free` linking to `/docs/` and `Choose a plan` linking to `/pricing/`. Include concise, implementation-aligned sections for compatible providers, coding-agent compatibility, local-first processing, telemetry/savings reports, deployment choices, and commercial governance. Include this disclosure verbatim above the footer: `CutCtx is a product of PitchToShip. Payments, invoices, licensing, and customer account management are provided by PitchToShip.`

- [ ] **Step 4: Implement `website/pricing/index.html`**

Render Builder as `$0` with a `/docs/` install CTA; Team as `$1,500/month` with checkout link `https://pitchtoship.com/billing?product=cutctx&amp;plan=starter&amp;billing=monthly`; Business as `$3,500/month` with checkout link `https://pitchtoship.com/billing?product=cutctx&amp;plan=studio&amp;billing=monthly`; and Enterprise as `Custom` with an email link to the owner-approved sales contact from Task 1. Add the exact merchant disclosure immediately before the footer. Do not embed a payment frame, a payment key, or a webhook URL.

- [ ] **Step 5: Run the route tests to verify success**

Run: `rtk pytest tests/website/test_static_site.py -q`

Expected: PASS for homepage, pricing, and foundation tests.

- [ ] **Step 6: Commit product conversion routes**

```bash
rtk git add website/index.html website/pricing/index.html tests/website/test_static_site.py
rtk git commit -m "feat: add CutCtx conversion pages"
```

### Task 4: Implement the evaluation and security routes

**Files:**
- Create: `website/docs/index.html`
- Create: `website/security/index.html`
- Modify: `tests/website/test_static_site.py`

**Interfaces:**
- Consumes: verified capabilities in `artifacts/PRODUCT_CAPABILITY_MATRIX.md`, `PRIVACY.md`, and `artifacts/security-one-pager.md`.
- Produces: low-friction technical evaluation and security-review entry routes.

- [ ] **Step 1: Write failing evaluation/security tests**

```python
def test_docs_provides_a_fast_evaluation_path():
    docs = Path("website/docs/index.html").read_text(encoding="utf-8")
    assert "pip install" in docs
    assert "cutctx wrap" in docs
    assert "cutctx savings report" in docs


def test_security_page_makes_only_supported_claims():
    security = Path("website/security/index.html").read_text(encoding="utf-8")
    assert "local-first" in security.lower()
    assert "customer-managed local storage" in security.lower()
    assert "SOC 2" not in security
    assert "HIPAA compliant" not in security
```

- [ ] **Step 2: Run the evaluation/security tests to verify failure**

Run: `rtk pytest tests/website/test_static_site.py::test_docs_provides_a_fast_evaluation_path tests/website/test_static_site.py::test_security_page_makes_only_supported_claims -q`

Expected: FAIL because neither public route exists.

- [ ] **Step 3: Implement `website/docs/index.html`**

Give evaluators a four-step path: install `cutctx-ai`, run `cutctx init`, wrap a supported agent with `cutctx wrap <agent>`, and inspect results with `cutctx savings report`. Use an HTML `<pre><code>` block for each command. Link to the repository documentation for full provider, Docker, Kubernetes, MCP, and deployment instructions; do not duplicate all operational documentation.

- [ ] **Step 4: Implement `website/security/index.html`**

State that processing is local-first; prompt/response content is processed in memory; retrieval state, audit records, and identity/org metadata are customer-managed local storage; and the customer chooses the upstream LLM provider. List supported governance capabilities as SSO/JWT/OIDC admin authentication, RBAC, audit logging/export, retention controls, fleet APIs, and SCIM-style provisioning APIs. Include a clearly labeled `What still requires external validation` block for formal certifications, DPAs/MSAs, and third-party audit reports.

- [ ] **Step 5: Run the evaluation/security tests to verify success**

Run: `rtk pytest tests/website/test_static_site.py -q`

Expected: PASS for all completed public content routes.

- [ ] **Step 6: Commit technical trust routes**

```bash
rtk git add website/docs/index.html website/security/index.html tests/website/test_static_site.py
rtk git commit -m "feat: add CutCtx docs and security pages"
```

### Task 5: Render owner-approved legal and support routes

**Files:**
- Create: `website/terms/index.html`
- Create: `website/privacy/index.html`
- Create: `website/refunds/index.html`
- Modify: `website/index.html`
- Modify: `website/pricing/index.html`
- Modify: `tests/website/test_static_site.py`

**Interfaces:**
- Consumes: the complete owner-approved `launch_configuration` values from Task 1.
- Produces: public legal routes with an accurate seller identity and support contacts.

- [ ] **Step 1: Verify external legal inputs before creating public legal files**

Require the owner to provide all values named under `External values that must be obtained before production publication`. If any one is absent, stop this task, retain the site only as a non-public preview, and report the exact missing field. Do not invent an address, refund deadline, tax policy, jurisdiction, legal entity, or support contact.

- [ ] **Step 2: Write failing legal-route tests using approved exact values**

```python
def test_legal_routes_use_approved_seller_identity_and_contacts():
    terms = Path("website/terms/index.html").read_text(encoding="utf-8")
    privacy = Path("website/privacy/index.html").read_text(encoding="utf-8")
    refunds = Path("website/refunds/index.html").read_text(encoding="utf-8")
    assert "CutCtx is a product of PitchToShip" in terms
    assert "Cutctx Labs" not in terms
    assert "sales@payzli.com" not in terms
    assert "mailto:" in privacy
    assert "cancellation" in refunds.lower()
```

Before the test is run, the owner must manually verify the rendered legal
entity name, address, privacy contact, refund/cancellation wording, and
governing jurisdiction against the approved values. Those public strings must
be hard-coded in the pages; never load them from a secret or environment
variable.

- [ ] **Step 3: Run legal-route tests to verify failure**

Run: `rtk pytest tests/website/test_static_site.py::test_legal_routes_use_approved_seller_identity_and_contacts -q`

Expected: FAIL because the public legal routes do not yet exist.

- [ ] **Step 4: Implement legal routes and footer links**

Write semantic legal pages using the approved values, keeping the existing open-core license boundary accurate. The terms must identify the seller as the approved legal entity trading as/operating PitchToShip and state that CutCtx is a product offering. The privacy page must preserve the local-first and no-prompt-collection claims only where they remain implementation-aligned. The refund page must match the owner-approved payment/refund policy exactly. Add `/terms/`, `/privacy/`, and `/refunds/` footer links to all public pages.

- [ ] **Step 5: Run all legal and static tests**

Run: `rtk pytest tests/website/test_static_site.py -q`

Expected: PASS with no legacy identity strings, placeholders, payment secrets, or missing legal links.

- [ ] **Step 6: Commit legal routes**

```bash
rtk git add website tests/website/test_static_site.py
rtk git commit -m "feat: add CutCtx legal pages"
```

### Task 6: Perform local visual, link, accessibility, and content verification

**Files:**
- Modify: `tests/website/test_static_site.py`
- Modify: `docs/launch/cutctx-cloudflare-runbook.md`

**Interfaces:**
- Consumes: all static routes and deployment contracts.
- Produces: verified source archive ready for one isolated Cloudflare Pages project.

- [ ] **Step 1: Write failing cross-page tests**

```python
def test_every_public_page_has_canonical_url_and_legal_footer():
    routes = ["index.html", "pricing/index.html", "docs/index.html", "security/index.html", "terms/index.html", "privacy/index.html", "refunds/index.html"]
    for route in routes:
        page = Path("website", route).read_text(encoding="utf-8")
        assert 'rel="canonical" href="https://cutctx.com' in page
        assert 'href="/terms/"' in page
        assert 'href="/privacy/"' in page
        assert 'href="/refunds/"' in page


def test_no_page_claims_a_guaranteed_savings_rate_or_certification():
    rendered = "\n".join(path.read_text(encoding="utf-8") for path in Path("website").rglob("*.html"))
    assert "guaranteed savings" not in rendered.lower()
    assert "SOC 2 certified" not in rendered
    assert "HIPAA compliant" not in rendered
```

- [ ] **Step 2: Run the cross-page tests to verify failure**

Run: `rtk pytest tests/website/test_static_site.py -q`

Expected: FAIL until canonical tags and footer links exist on every route.

- [ ] **Step 3: Add canonical metadata and validate visible UI locally**

Add a route-specific `<link rel="canonical">`, title, description, and Open Graph URL to each public route. Start a local static server with `rtk proxy python3 -m http.server 4180 --directory website`; inspect desktop and a mobile viewport using the browser tool. Verify navigation, keyboard focus, CTA targets, code-block readability, the pricing layout, and no horizontal overflow. Record the result, tested URLs, and unresolved issues in the runbook.

- [ ] **Step 4: Run the full static test suite and inspect source status**

Run: `rtk pytest tests/website/test_static_site.py -q && rtk git diff --check && rtk git status --short`

Expected: all static tests pass, no whitespace errors, and only intentional CutCtx launch files are unstaged/staged.

- [ ] **Step 5: Commit verification changes**

```bash
rtk git add website tests/website/test_static_site.py docs/launch/cutctx-cloudflare-runbook.md
rtk git commit -m "test: verify CutCtx launch site"
```

### Task 7: Create the isolated Cloudflare zone and delegate only CutCtx DNS

**Files:**
- Modify: `docs/launch/cutctx-cloudflare-runbook.md`

**Interfaces:**
- Consumes: verified source from Task 6 and a signed-in Cloudflare/BigRock browser session.
- Produces: an active Cloudflare zone for `cutctx.com` with only Cloudflare-provided authoritative nameservers delegated from BigRock.

- [ ] **Step 1: Capture current state before changes**

In Cloudflare, inspect the account zone list and confirm `cutctx.com` is absent. In BigRock, inspect `cutctx.com` and record the four current `dns1.bigrock.in` through `dns4.bigrock.in` nameservers plus any existing DNS records. Do not alter them during this step.

- [ ] **Step 2: Obtain action-time confirmation**

Ask the owner exactly: `Cloudflare will create a new zone for cutctx.com, and BigRock will replace only cutctx.com's four BigRock nameservers with Cloudflare's two assigned nameservers. Existing PitchToShip Cloudflare resources and DNS will not be changed. Confirm this DNS delegation change?`

- [ ] **Step 3: Add the Cloudflare zone and copy the assigned nameservers**

Create the zone using `cutctx.com` in the existing Cloudflare account. Copy the two nameservers Cloudflare displays exactly; do not infer or reuse nameservers from `pitchtoship.com`.

- [ ] **Step 4: Change only CutCtx nameservers in BigRock**

In BigRock's `cutctx.com` management page, replace the current four authoritative nameservers with exactly the two values Cloudflare assigned. Save the nameserver change. Do not change the `pitchtoship.com` card, BigRock account defaults, existing email products, or contact/WHOIS details.

- [ ] **Step 5: Validate delegation and record rollback state**

Wait for Cloudflare to show the new zone as active, then use `dig NS cutctx.com` and `dig SOA cutctx.com` to confirm public delegation. Add the exact old BigRock nameservers, new Cloudflare nameservers, timestamps, and observed activation status to the runbook. If activation fails, restore only the recorded four BigRock nameservers after explicit owner confirmation.

- [ ] **Step 6: Commit the finalized runbook record**

```bash
rtk git add docs/launch/cutctx-cloudflare-runbook.md
rtk git commit -m "docs: record CutCtx DNS delegation"
```

### Task 8: Create and deploy the dedicated Cloudflare Pages project

**Files:**
- Modify: `docs/launch/cutctx-cloudflare-runbook.md`

**Interfaces:**
- Consumes: active `cutctx.com` Cloudflare zone and `website/` static directory.
- Produces: one new Pages project, one preview URL, and one production deployment for CutCtx only.

- [ ] **Step 1: Verify project isolation before creation**

Open Cloudflare Workers & Pages. Confirm there is no existing project named `cutctx`. Confirm the existing `pitchtoship` Worker is not selected and will not be edited.

- [ ] **Step 2: Obtain action-time confirmation**

Ask the owner exactly: `Cloudflare will create a new Pages project named cutctx and upload only the website/ static directory from this repository. It will not edit the existing pitchtoship Worker or any existing zone. Confirm this deployment?`

- [ ] **Step 3: Create the Pages project and deploy a preview**

Create the `cutctx` Pages project as a direct-upload static project. Upload only the contents of `website/`, preserving `_headers`, `_redirects`, `robots.txt`, and `sitemap.xml` at the deployment root. Open the assigned preview URL and verify `/`, `/pricing/`, `/docs/`, `/security/`, `/terms/`, `/privacy/`, and `/refunds/` all return the expected static pages.

- [ ] **Step 4: Bind custom domains safely**

Add `cutctx.com` to the new Pages project, wait for successful validation and TLS issuance, then add `www.cutctx.com`. Leave the `www` redirect in `_redirects`; do not create a second project or modify another zone to implement it.

- [ ] **Step 5: Perform production verification**

For each canonical route, verify HTTP-to-HTTPS behaviour, valid certificate, canonical tag, title, description, primary CTA target, legal footer, and no browser console errors. Verify `www.cutctx.com/pricing/` redirects to `https://cutctx.com/pricing/`. Verify both payment CTAs open the correct PitchToShip product/plan link without submitting a payment or exposing credentials.

- [ ] **Step 6: Record deployment evidence**

Record the Pages project name, production URL, custom-domain validation status, deployment timestamp, preview URL, and verification results in the runbook. Do not record account credentials, payment data, API tokens, or customer data.

- [ ] **Step 7: Commit deployment evidence**

```bash
rtk git add docs/launch/cutctx-cloudflare-runbook.md
rtk git commit -m "docs: record CutCtx Pages launch"
```

## Final evidence checklist

- [ ] `cutctx.com` zone is active in Cloudflare and only its own BigRock delegation changed.
- [ ] Existing Cloudflare zones and the `pitchtoship` Worker are unchanged.
- [ ] The Pages project is named `cutctx` and serves a static preview before production.
- [ ] Home, pricing, docs, security, terms, privacy, and refunds routes load over HTTPS.
- [ ] Builder, Team, and Business routes point to the correct PitchToShip destination.
- [ ] Legal identity, contacts, tax/refund wording, and jurisdiction are owner-approved and visible.
- [ ] Static tests, link inspection, mobile inspection, and source whitespace checks pass.
- [ ] The launch runbook contains cutover/rollback values and no sensitive data.
