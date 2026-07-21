# CutCtx Website Evolve Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evolve every public CutCtx route into a responsive technical editorial cockpit that makes `Start free` the dominant conversion while preserving verified capability claims, PitchToShip commerce/legal contracts, and the existing Cloudflare Pages deployment.

**Architecture:** Keep the existing static HTML/CSS/JavaScript delivery model. Replace the shared stylesheet with a focused token and component system, evolve each route's semantic HTML to use those components, and retain `site.js` only for mobile navigation plus privacy-respecting CTA events. Verification combines static contract tests, local HTTP/browser checks at representative viewports, and live Cloudflare acceptance checks after pushing `main`.

**Tech Stack:** Static HTML5, CSS custom properties and responsive layout, vanilla JavaScript, inline semantic SVG/CSS visualization, Python `pytest`, local HTTP server, Cloudflare Pages, GitHub.

## Global Constraints

- `cutctx.com` remains a static site deployed from `main` with output directory `website`.
- Do not remove or replace unrelated Cloudflare zones, DNS records, Workers, Pages projects, or any `pitchtoship.com` resource.
- PitchToShip remains the legal entity and commerce authority; preserve all verified checkout URLs, billing parameters, merchant disclosure, company identity, contacts, and legal meaning.
- Make `Start free` the dominant header, hero, evidence, and final-band action.
- Do not claim universal savings, guarantees, formal certifications, partnerships, or unsupported functionality.
- Do not add external fonts, images, analytics, frontend frameworks, or production dependencies.
- Preserve the current CSP, HSTS, HTTPS, redirect, and static-route contracts.
- Preserve `/`, `/pricing/`, `/docs/`, `/security/`, `/terms/`, `/privacy/`, and `/refunds/`.
- Use CSS/SVG-first visuals, small non-blocking JavaScript, semantic HTML, visible focus, reduced-motion support, and at least 44px mobile touch targets.
- Run every shell command with the repository-required `rtk` prefix; for unfiltered Git diagnostics use `rtk proxy git ...`.

## File responsibility map

- `website/assets/site.css`: all public-site design tokens, layout primitives, responsive rules, animation, focus treatment, and route components.
- `website/assets/site.js`: mobile navigation state and placement-aware `cutctx:cta` events only.
- `website/index.html`: conversion homepage, product visualization, workflow explanation, compatibility, evidence, security, pricing preview, and final CTA.
- `website/pricing/index.html`: plan hierarchy, verified PitchToShip checkout paths, merchant context, and evaluation CTA.
- `website/docs/index.html`: scannable installation-to-report quick start with anchorable steps.
- `website/security/index.html`: local-first trust summary, data flow, deployment, governance, and enterprise contact.
- `website/terms/index.html`, `website/privacy/index.html`, `website/refunds/index.html`: shared evolved shell and styling without changing legal meaning.
- `tests/website/test_static_site.py`: durable structural, conversion, commerce, legal, security, and asset-policy contracts.
- `docs/superpowers/specs/2026-07-21-cutctx-website-evolve-design.md`: approved source of truth; no implementation edits expected.

## Evidence path

The core claim is that the deployed site is visibly evolved, responsive, accessible at a practical static-site level, and conversion-led while its commerce/legal/security contracts remain unchanged. Static tests can establish the route structure, CTA hierarchy, no-remote-asset rule, billing links, and preserved claims. Browser screenshots and DOM inspection at 390px, 768px, 1440px, and a wide desktop establish layout, hierarchy, overflow, mobile navigation, and visualization behaviour. Live HTTPS and CTA checks establish the GitHub-to-Cloudflare boundary. Static tests cannot establish subjective visual quality alone, so screenshot review is a required complementary evidence path.

---

### Task 1: Encode the evolved-site contracts as failing tests

**Files:**
- Modify: `tests/website/test_static_site.py`

**Interfaces:**
- Consumes: current static HTML routes and approved design specification.
- Produces: contract tests that later HTML/CSS tasks must satisfy.

- [ ] **Step 1: Add shared page loading and public-route fixtures**

Add these definitions after the imports:

```python
PUBLIC_PAGES = [
    Path("website/index.html"),
    Path("website/pricing/index.html"),
    Path("website/docs/index.html"),
    Path("website/security/index.html"),
    Path("website/terms/index.html"),
    Path("website/privacy/index.html"),
    Path("website/refunds/index.html"),
]


def read_page(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")
```

- [ ] **Step 2: Add failing conversion and product-flow tests**

Append:

```python
def test_homepage_uses_evolved_conversion_structure():
    home = read_page("website/index.html")
    assert 'class="hero hero-split"' in home
    assert 'data-product-flow' in home
    assert 'id="how-it-works"' in home
    assert all(stage in home for stage in ("Observe", "Compress", "Retrieve", "Prove"))
    assert home.count('data-cta="start-free') >= 3
    assert 'href="/docs/#quick-start"' in home


def test_homepage_visualization_avoids_unsupported_savings_claims():
    home = read_page("website/index.html")
    assert "Illustrative workflow" in home
    assert "guaranteed" not in home.lower()
    assert "typical savings" not in home.lower()
    assert "% saved" not in home.lower()


def test_homepage_exposes_verified_compatibility():
    home = read_page("website/index.html")
    for label in ("OpenAI", "Anthropic", "Gemini / Vertex", "Amazon Bedrock", "Claude Code", "Codex", "Cursor"):
        assert label in home
```

- [ ] **Step 3: Add failing shared-shell, accessibility, and asset-policy tests**

Append:

```python
def test_public_routes_share_the_evolved_shell():
    for page in PUBLIC_PAGES:
        html = page.read_text(encoding="utf-8")
        assert 'class="site-header"' in html
        assert 'data-mobile-nav-toggle' in html
        assert 'href="/docs/#quick-start"' in html
        assert 'class="site-footer"' in html
        assert "CutCtx is a product of PitchToShip" in html


def test_public_pages_keep_local_assets_and_semantic_entry_points():
    for page in PUBLIC_PAGES:
        html = page.read_text(encoding="utf-8")
        assert 'href="/assets/site.css"' in html
        assert 'src="/assets/site.js"' in html
        assert "fonts.googleapis.com" not in html
        assert "fonts.gstatic.com" not in html
        assert 'class="skip-link"' in html
        assert 'id="main-content"' in html


def test_stylesheet_defines_responsive_accessible_contracts():
    css = read_page("website/assets/site.css")
    assert "prefers-reduced-motion: reduce" in css
    assert "min-height: 2.75rem" in css
    assert ".hero-split" in css
    assert ".product-flow" in css
    assert ".process-grid" in css
```

- [ ] **Step 4: Add failing route-specific evolution tests**

Append:

```python
def test_pricing_preserves_commerce_and_adds_recommendation_hierarchy():
    pricing = read_page("website/pricing/index.html")
    assert 'class="price-card featured"' in pricing
    assert "Recommended for teams" in pricing
    assert "Start with a measured evaluation" in pricing
    assert "https://pitchtoship.com/billing?product=cutctx&amp;plan=starter&amp;billing=monthly" in pricing
    assert "https://pitchtoship.com/billing?product=cutctx&amp;plan=studio&amp;billing=monthly" in pricing


def test_docs_has_anchorable_install_to_report_flow():
    docs = read_page("website/docs/index.html")
    assert 'id="quick-start"' in docs
    assert 'id="install"' in docs
    assert 'id="wrap"' in docs
    assert 'id="measure"' in docs
    assert "pip install" in docs
    assert "cutctx wrap" in docs
    assert "cutctx savings report" in docs


def test_security_has_trust_flow_and_enterprise_path_without_certification_claims():
    security = read_page("website/security/index.html")
    assert 'class="trust-grid"' in security
    assert "Your environment" in security
    assert "Your provider" in security
    assert "Your retention" in security
    assert "mailto:hello@aoexl.com?subject=CutCtx%20Enterprise" in security
    assert "SOC 2 certified" not in security
    assert "HIPAA compliant" not in security
```

- [ ] **Step 5: Run the new tests and confirm they fail for structural reasons**

Run:

```bash
rtk pytest tests/website/test_static_site.py -q
```

Expected: existing tests pass and the new tests fail on missing evolved classes, anchors, CTA placement, and content—not on import or syntax errors.

- [ ] **Step 6: Commit the red tests**

```bash
GIT_TERMINAL_PROMPT=0 rtk git add tests/website/test_static_site.py
GIT_TERMINAL_PROMPT=0 GIT_EDITOR=true rtk proxy git commit -m "test: define CutCtx website evolve contracts"
```

### Task 2: Build the shared technical editorial design system

**Files:**
- Modify: `website/assets/site.css`
- Modify: `website/assets/site.js`
- Test: `tests/website/test_static_site.py`

**Interfaces:**
- Consumes: class contracts from Task 1.
- Produces: reusable `.site-shell`, `.hero-split`, `.product-flow`, `.process-grid`, `.bento-grid`, `.trust-grid`, `.price-card`, `.docs-layout`, `.legal-copy`, and CTA styles used by later pages.

- [ ] **Step 1: Replace the root token block and body foundation**

Use this token contract at the top of `site.css` and retain a system-only font stack:

```css
:root {
  --ink: #f7f9ff;
  --ink-soft: #c5cede;
  --ink-faint: #8794aa;
  --night: #050a12;
  --surface: #08111d;
  --surface-raised: #0d1928;
  --surface-soft: #122238;
  --mint: #70edbd;
  --mint-strong: #36d79b;
  --cyan: #76cfff;
  --line: rgba(183, 204, 230, 0.16);
  --line-strong: rgba(112, 237, 189, 0.34);
  --focus: #a9c9ff;
  --shadow: 0 28px 90px rgba(0, 0, 0, 0.34);
  --radius-sm: 0.65rem;
  --radius-md: 1rem;
  --radius-lg: 1.5rem;
  --max-width: 76rem;
}

body {
  margin: 0;
  min-width: 20rem;
  overflow-x: hidden;
  background:
    radial-gradient(circle at 12% 0%, rgba(112, 237, 189, 0.11), transparent 28rem),
    radial-gradient(circle at 90% 12%, rgba(118, 207, 255, 0.09), transparent 32rem),
    var(--night);
  color: var(--ink);
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  line-height: 1.6;
}
```

- [ ] **Step 2: Implement the reusable component contracts**

Define styles for these exact classes in coherent sections of `site.css`:

```css
.site-header { position: sticky; top: 0; z-index: 20; border-bottom: 1px solid var(--line); background: rgba(5, 10, 18, 0.78); backdrop-filter: blur(18px); }
.button { min-height: 2.75rem; border-radius: var(--radius-sm); }
.hero-split { display: grid; grid-template-columns: minmax(0, 1.03fr) minmax(24rem, 0.97fr); gap: clamp(2rem, 5vw, 5rem); align-items: center; padding: clamp(4.5rem, 9vw, 8rem) 0 3rem; }
.product-flow { position: relative; overflow: hidden; border: 1px solid var(--line-strong); border-radius: var(--radius-lg); background: linear-gradient(155deg, rgba(18, 34, 56, 0.96), rgba(5, 10, 18, 0.98)); box-shadow: var(--shadow); }
.process-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1px; overflow: hidden; border: 1px solid var(--line); border-radius: var(--radius-lg); background: var(--line); }
.bento-grid { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 1rem; }
.bento-primary { grid-column: span 7; }
.bento-secondary { grid-column: span 5; }
.trust-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1rem; }
.docs-layout { display: grid; grid-template-columns: minmax(12rem, 0.28fr) minmax(0, 0.72fr); gap: clamp(2rem, 5vw, 5rem); align-items: start; }
```

Also define the exact supporting classes used later: `.nav`, `.nav-links`, `.nav-toggle`, `.hero-copy`, `.hero-actions`, `.eyebrow`, `.lede`, `.flow-head`, `.flow-body`, `.flow-row`, `.flow-node`, `.flow-arrow`, `.signal`, `.chip-row`, `.chip`, `.section`, `.section-heading`, `.process-step`, `.step-index`, `.bento-card`, `.metric-rail`, `.command-card`, `.evidence-steps`, `.evidence-step`, `.price-card`, `.plan-badge`, `.merchant-panel`, `.page-hero`, `.content-panel`, `.trust-card`, `.docs-nav`, `.docs-step`, `.callout`, `.cta-band`, `.site-footer`, `.footer-grid`, `.footer-links`, and `.legal-copy`.

- [ ] **Step 3: Add responsive and reduced-motion rules**

Add these breakpoint behaviours, expanding selectors where necessary:

```css
@media (max-width: 64rem) {
  .hero-split, .docs-layout { grid-template-columns: 1fr; }
  .product-flow { max-width: 46rem; }
  .bento-primary, .bento-secondary { grid-column: span 12; }
}

@media (max-width: 48rem) {
  .site-shell { width: min(calc(100% - 2rem), var(--max-width)); }
  .nav { flex-wrap: wrap; }
  .nav-toggle { display: inline-flex; min-height: 2.75rem; }
  .nav-links { display: none; width: 100%; flex-direction: column; align-items: stretch; padding: 0 0 1rem; }
  .nav-links[data-open="true"] { display: flex; }
  .nav-links .button { width: 100%; }
  .hero-split { padding-top: 3.5rem; }
  .process-grid, .trust-grid, .pricing-grid { grid-template-columns: 1fr; }
  .flow-row { grid-template-columns: 1fr; }
  .flow-arrow { transform: rotate(90deg); }
  .hero-actions .button, .inline-actions .button { min-height: 3rem; }
}

@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  *, *::before, *::after { animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; transition-duration: 0.01ms !important; }
}
```

- [ ] **Step 4: Keep JavaScript narrow and add placement-aware CTA events**

Replace `site.js` with:

```javascript
(() => {
  const toggle = document.querySelector("[data-mobile-nav-toggle]");
  const nav = document.querySelector("[data-mobile-nav]");

  if (toggle && nav) {
    toggle.addEventListener("click", () => {
      const nextOpen = nav.dataset.open !== "true";
      nav.dataset.open = String(nextOpen);
      toggle.setAttribute("aria-expanded", String(nextOpen));
    });
  }

  document.querySelectorAll("[data-cta]").forEach((element) => {
    element.addEventListener("click", () => {
      window.dispatchEvent(new CustomEvent("cutctx:cta", {
        detail: {
          action: element.dataset.cta,
          placement: element.dataset.ctaPlacement || "unspecified",
        },
      }));
    });
  });
})();
```

- [ ] **Step 5: Run shared asset tests**

```bash
rtk pytest tests/website/test_static_site.py::test_stylesheet_defines_responsive_accessible_contracts tests/website/test_static_site.py::test_public_pages_keep_local_assets_and_semantic_entry_points -q
```

Expected: the stylesheet contract passes; the public-page shell test may remain red until Tasks 3–6.

- [ ] **Step 6: Commit the shared system**

```bash
GIT_TERMINAL_PROMPT=0 rtk git add website/assets/site.css website/assets/site.js
GIT_TERMINAL_PROMPT=0 GIT_EDITOR=true rtk proxy git commit -m "feat: evolve CutCtx public design system"
```

### Task 3: Rebuild the homepage around product evidence and Start free

**Files:**
- Modify: `website/index.html`
- Test: `tests/website/test_static_site.py`

**Interfaces:**
- Consumes: shared classes from Task 2.
- Produces: homepage anchors `#how-it-works` and `#capabilities`, responsive `[data-product-flow]`, and repeated placement-aware Start free CTAs.

- [ ] **Step 1: Replace the header CTA hierarchy**

Use Product, Pricing, Docs, Security, and this exact primary action:

```html
<a class="button button-primary" data-cta="start-free-header" data-cta-placement="header" href="/docs/#quick-start">Start free</a>
```

- [ ] **Step 2: Replace the current hero and proof cards with the split hero**

The hero must use this semantic structure and copy:

```html
<section class="hero hero-split">
  <div class="hero-copy">
    <div class="eyebrow">Context efficiency for serious AI work</div>
    <h1>Send models less context. Keep what matters within reach.</h1>
    <p class="lede">CutCtx is a local-first control layer for AI agents and LLM applications. Reduce context overhead, retain access to useful information, and measure the result on your own traffic.</p>
    <div class="hero-actions">
      <a class="button button-primary" data-cta="start-free-hero" data-cta-placement="hero" href="/docs/#quick-start">Start free</a>
      <a class="button button-secondary" data-cta="see-how" data-cta-placement="hero" href="#how-it-works">See how it works</a>
    </div>
    <p class="hero-note">Local-first · Provider-flexible · Measured on your workload</p>
  </div>
  <div class="product-flow" data-product-flow aria-label="Illustrative CutCtx workflow">
    <div class="flow-head"><span>Illustrative workflow</span><span class="signal">Evaluation active</span></div>
    <div class="flow-body">
      <div class="flow-row">
        <div class="flow-node"><span class="flow-label">Incoming context</span><strong>Agent history + tools</strong></div>
        <span class="flow-arrow" aria-hidden="true">→</span>
        <div class="flow-node flow-node-accent"><span class="flow-label">CutCtx</span><strong>Compress + retrieve</strong></div>
        <span class="flow-arrow" aria-hidden="true">→</span>
        <div class="flow-node"><span class="flow-label">Selected model</span><strong>Focused payload</strong></div>
      </div>
      <div class="metric-rail" aria-label="CutCtx evaluation signals">
        <span>Useful context retained</span><span>Provider route preserved</span><span>Report available</span>
      </div>
    </div>
  </div>
</section>
```

- [ ] **Step 3: Add compatibility chips and the four-stage product explanation**

Add a compatibility section containing these exact visible labels: OpenAI, Anthropic, Gemini / Vertex, Amazon Bedrock, Chosen endpoint, Claude Code, Codex, Cursor, Cline, Aider. Then add `<section class="section" id="how-it-works">` with a `.process-grid` of four `.process-step` articles titled Observe, Compress, Retrieve, and Prove, each with one concise explanatory paragraph grounded in the approved spec.

Use numbered labels `01` through `04`, and ensure the section remains fully readable without JavaScript.

- [ ] **Step 4: Add asymmetric capability, evidence, security, and pricing sections**

Use:

```html
<div class="bento-grid" id="capabilities">
  <article class="bento-card bento-primary">
    <div class="eyebrow">Context control</div>
    <h3>Reduce overhead without losing the thread.</h3>
    <p>Protocol-aware compression works with retrieval, memory, and cache-aware controls so useful information remains available when the workflow needs it.</p>
  </article>
  <article class="bento-card bento-secondary">
    <div class="eyebrow">Fits your stack</div>
    <h3>Keep the agents and providers you already use.</h3>
    <p>Wrap supported coding agents and route compatible OpenAI, Anthropic, Gemini/Vertex, Bedrock, and chosen-endpoint traffic through one control layer.</p>
  </article>
  <article class="bento-card bento-secondary">
    <div class="eyebrow">Operational evidence</div>
    <h3>Inspect the result on your traffic.</h3>
    <p>Use the local dashboard, telemetry, and savings reports to understand the result before selecting a commercial path.</p>
  </article>
  <article class="bento-card bento-primary">
    <div class="eyebrow">Deployment control</div>
    <h3>Start locally. Deploy where your environment requires.</h3>
    <p>Use the CLI and local proxy, Docker or Docker Compose, Kubernetes, or an air-gapped deployment path.</p>
  </article>
</div>
```

Add a four-step `.evidence-steps` sequence: Install, Wrap, Run, Inspect. Its primary link must be:

```html
<a class="button button-primary" data-cta="start-free-evidence" data-cta-placement="evidence" href="/docs/#quick-start">Run it on your workflow</a>
```

Add a compact security/deployment section linking to `/security/`, then a three-path pricing preview for Builder, Team, and Enterprise linking to `/pricing/`. Do not put PitchToShip checkout links directly on the homepage.

- [ ] **Step 5: Add the final conversion band and preserve merchant disclosure**

The final band must include:

```html
<a class="button" data-cta="start-free-final" data-cta-placement="final" href="/docs/#quick-start">Start free</a>
<a class="button button-quiet" data-cta="view-pricing-final" data-cta-placement="final" href="/pricing/">View pricing</a>
```

Retain the exact PitchToShip merchant sentence in the footer.

- [ ] **Step 6: Run homepage tests**

```bash
rtk pytest tests/website/test_static_site.py::test_homepage_uses_evolved_conversion_structure tests/website/test_static_site.py::test_homepage_visualization_avoids_unsupported_savings_claims tests/website/test_static_site.py::test_homepage_exposes_verified_compatibility tests/website/test_static_site.py::test_homepage_has_product_and_merchant_disclosure -q
```

Expected: PASS.

- [ ] **Step 7: Commit the homepage**

```bash
GIT_TERMINAL_PROMPT=0 rtk git add website/index.html tests/website/test_static_site.py
GIT_TERMINAL_PROMPT=0 GIT_EDITOR=true rtk proxy git commit -m "feat: rebuild CutCtx homepage around evaluation"
```

### Task 4: Evolve Pricing without changing commerce contracts

**Files:**
- Modify: `website/pricing/index.html`
- Test: `tests/website/test_static_site.py`

**Interfaces:**
- Consumes: shared pricing and merchant-panel components.
- Produces: four verified plan cards and unchanged PitchToShip deep links.

- [ ] **Step 1: Apply the shared navigation with Start free**

Use `/docs/#quick-start` for the header CTA and include Product, Docs, and Security links.

- [ ] **Step 2: Recompose the page hero and plan hierarchy**

Use the eyebrow `Start free. Scale with evidence.` and the headline `Choose the control your workflow needs.` Add a compact evaluation panel titled `Start with a measured evaluation` before the paid plans.

Keep four plan articles: Builder, Team, Business, Enterprise. Add this badge inside Team:

```html
<div class="plan-badge">Recommended for teams</div>
```

Keep the current prices and feature meaning. Preserve the exact Team and Business checkout URLs and the exact enterprise mailto address.

- [ ] **Step 3: Add explicit merchant context near paid actions**

Add a `.merchant-panel` beneath the pricing grid containing the full merchant disclosure and links to Terms, Privacy, and Refunds. Do not mention Razorpay or include payment secrets.

- [ ] **Step 4: Run pricing tests**

```bash
rtk pytest tests/website/test_static_site.py::test_pricing_preserves_commerce_and_adds_recommendation_hierarchy tests/website/test_static_site.py::test_pricing_routes_to_pitchtoship_without_payment_secrets tests/website/test_static_site.py::test_pricing_uses_the_verified_company_contact -q
```

Expected: PASS.

- [ ] **Step 5: Commit Pricing**

```bash
GIT_TERMINAL_PROMPT=0 rtk git add website/pricing/index.html
GIT_TERMINAL_PROMPT=0 GIT_EDITOR=true rtk proxy git commit -m "feat: clarify CutCtx pricing journey"
```

### Task 5: Turn Docs and Security into product-led evaluation pages

**Files:**
- Modify: `website/docs/index.html`
- Modify: `website/security/index.html`
- Test: `tests/website/test_static_site.py`

**Interfaces:**
- Consumes: `.docs-layout`, `.docs-nav`, `.docs-step`, `.trust-grid`, `.trust-card`, `.content-panel`, and shared shell.
- Produces: homepage target `/docs/#quick-start`, anchorable steps, and enterprise trust route.

- [ ] **Step 1: Rebuild Docs around anchorable quick-start steps**

Set the main quick-start section to `id="quick-start"`. Add a sticky `.docs-nav` with links to `#install`, `#initialize`, `#wrap`, and `#measure`. Use four `.docs-step` sections with those IDs and preserve these commands exactly:

```text
pip install "cutctx-ai[all]"
cutctx init
cutctx wrap codex
cutctx savings report
```

Keep the current supported-agent list and GitHub documentation link. Add one callout explaining that the user should run a normal workflow before inspecting their report; do not promise a result.

- [ ] **Step 2: Rebuild Security around ownership and boundaries**

Add a `.trust-grid` immediately after the hero with cards titled `Your environment`, `Your provider`, and `Your retention`. Preserve the existing factual data-handling bullets and formal-validation disclaimer.

Group the remaining content under Data flow, Governance capabilities, Deployment choices, and External validation. Add:

```html
<a class="button button-secondary" data-cta="enterprise-security" data-cta-placement="security" href="mailto:hello@aoexl.com?subject=CutCtx%20Enterprise">Discuss an enterprise deployment</a>
```

- [ ] **Step 3: Run Docs and Security tests**

```bash
rtk pytest tests/website/test_static_site.py::test_docs_has_anchorable_install_to_report_flow tests/website/test_static_site.py::test_docs_provides_a_fast_evaluation_path tests/website/test_static_site.py::test_security_has_trust_flow_and_enterprise_path_without_certification_claims tests/website/test_static_site.py::test_security_page_makes_only_supported_claims -q
```

Expected: PASS.

- [ ] **Step 4: Commit the evaluation and trust pages**

```bash
GIT_TERMINAL_PROMPT=0 rtk git add website/docs/index.html website/security/index.html
GIT_TERMINAL_PROMPT=0 GIT_EDITOR=true rtk proxy git commit -m "feat: improve CutCtx evaluation and trust pages"
```

### Task 6: Apply the evolved shell to legal pages without changing meaning

**Files:**
- Modify: `website/terms/index.html`
- Modify: `website/privacy/index.html`
- Modify: `website/refunds/index.html`
- Test: `tests/website/test_static_site.py`

**Interfaces:**
- Consumes: shared header, page hero, legal copy, and footer styles.
- Produces: visually consistent legal routes with unchanged verified content.

- [ ] **Step 1: Replace only the header/footer shell on all three pages**

Use the same navigation pattern as the other public pages and make the header CTA:

```html
<a class="button button-primary" data-cta="start-free-header" data-cta-placement="header" href="/docs/#quick-start">Start free</a>
```

Retain every legal paragraph's substantive text, effective date, company name, address, email, refund period, governing law, and jurisdiction. Reflow markup for readability but do not rewrite legal meaning.

- [ ] **Step 2: Add a legal document frame**

Wrap each legal body in `.content-panel legal-panel` beneath its `.page-hero`. Preserve semantic `<h2>`, paragraph, list, and link elements.

- [ ] **Step 3: Run legal and shared-shell tests**

```bash
rtk pytest tests/website/test_static_site.py::test_public_legal_pages_do_not_contain_unapproved_legacy_identity tests/website/test_static_site.py::test_public_routes_share_the_evolved_shell -q
```

Expected: PASS.

- [ ] **Step 4: Commit the legal shell**

```bash
GIT_TERMINAL_PROMPT=0 rtk git add website/terms/index.html website/privacy/index.html website/refunds/index.html
GIT_TERMINAL_PROMPT=0 GIT_EDITOR=true rtk proxy git commit -m "style: align CutCtx legal pages with public site"
```

### Task 7: Complete local automated and visual verification

**Files:**
- Modify only if a verified defect is found: `website/**/*.html`, `website/assets/site.css`, `website/assets/site.js`, `tests/website/test_static_site.py`

**Interfaces:**
- Consumes: complete evolved static site.
- Produces: evidence that local contracts and representative responsive layouts work.

- [ ] **Step 1: Run formatting and full static-site tests**

```bash
rtk git diff --check
rtk pytest tests/website/test_static_site.py -q
```

Expected: no whitespace errors and all tests pass.

- [ ] **Step 2: Start a local non-interactive static server**

```bash
rtk proxy python -m http.server 4173 --directory website
```

Run this in a managed PTY/session so it can be polled and terminated after browser verification. Expected: server listens on `http://127.0.0.1:4173`.

- [ ] **Step 3: Verify desktop and mobile layouts in the browser**

Inspect `/`, `/pricing/`, `/docs/`, `/security/`, and one legal page at 390×844, 768×1024, 1440×900, and a wide desktop viewport. For each representative route verify:

- no horizontal page overflow;
- header, navigation, CTA, hero, visualization, and footer are visible;
- the product flow remains understandable on mobile;
- the mobile menu opens, reports `aria-expanded="true"`, and exposes its links;
- code blocks scroll internally rather than widening the page;
- all primary touch controls are at least 44 CSS pixels high;
- `prefers-reduced-motion` leaves all content visible and understandable.

Capture full-page desktop and mobile screenshots of the homepage plus focused screenshots of Pricing, Docs, and Security for review.

- [ ] **Step 4: Verify links and browser console**

Use DOM inspection to confirm the homepage's internal `#how-it-works` and `/docs/#quick-start` targets exist. Confirm PitchToShip links on Pricing are unchanged without submitting checkout. Confirm there are no unexpected console errors on each primary route.

- [ ] **Step 5: Fix only observed defects, then repeat affected evidence**

For any observed issue, first add or tighten the smallest relevant test when the defect is structurally testable. Apply the minimal HTML/CSS/JS patch, rerun the affected test, and recapture the affected viewport. Do not perform speculative redesign beyond the approved specification.

- [ ] **Step 6: Stop the local server and commit verification fixes if any**

```bash
GIT_TERMINAL_PROMPT=0 rtk git add website tests/website/test_static_site.py
GIT_TERMINAL_PROMPT=0 GIT_EDITOR=true rtk proxy git commit -m "fix: polish CutCtx responsive website"
```

Skip this commit if Step 5 produced no changes.

### Task 8: Review, push main, and verify the Cloudflare deployment

**Files:**
- No planned source changes.
- Modify implementation files only if live verification reveals a reproducible deployment-specific defect.

**Interfaces:**
- Consumes: locally verified `main` branch and configured `github-personal` SSH profile.
- Produces: deployed and verified `https://cutctx.com` release.

- [ ] **Step 1: Perform the pre-push review gate**

Run:

```bash
rtk git status --short
rtk git log --oneline --decorate -8
rtk git diff origin/main...HEAD -- website tests/website docs/superpowers
rtk pytest tests/website/test_static_site.py -q
```

Expected: only intentional site, test, spec, and plan commits differ from `origin/main`; tests pass; no uncommitted changes remain.

- [ ] **Step 2: Verify the personal GitHub SSH destination without changing remotes unnecessarily**

Inspect `git remote -v` and SSH configuration through `rtk`. The push destination must resolve through the configured `github-personal` profile and the correct repository/account, not `aryansingh0203`. If the current remote already meets that contract, preserve it.

- [ ] **Step 3: Push `main` non-interactively**

```bash
GIT_TERMINAL_PROMPT=0 rtk proxy git push github-personal main
```

If `github-personal` is an SSH host rather than a remote name, use the already configured remote URL that contains that host. Do not create or overwrite credentials.

- [ ] **Step 4: Wait for the existing Cloudflare Pages deployment**

Use the currently logged-in Cloudflare browser session or the existing project dashboard only to observe the `cutctx-web` deployment sourced from `main`. Do not delete, recreate, or edit unrelated Cloudflare resources. Confirm the deployment commit matches the final local commit.

- [ ] **Step 5: Verify live public behaviour**

On `https://cutctx.com/`, `/pricing/`, `/docs/`, `/security/`, `/terms/`, `/privacy/`, and `/refunds/`, verify:

- HTTP success over HTTPS;
- correct canonical route and content;
- homepage desktop/mobile visual acceptance;
- `Start free` routes to `/docs/#quick-start`;
- Team and Business links still point to the exact PitchToShip billing URLs;
- enterprise contact uses `hello@aoexl.com`;
- merchant disclosure and legal navigation are visible;
- `https://www.cutctx.com/...` redirects to the matching apex route;
- no unrelated Cloudflare resource was modified.

- [ ] **Step 6: Report the evidence and remaining limits**

Report the final commit, push result, Cloudflare deployment status, routes checked, test result, representative viewports, and any remaining uncertainty. Do not claim conversion improvement as measured business evidence until real customer analytics exist; claim only that the approved conversion hierarchy and UX were deployed and verified.
