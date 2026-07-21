# CutCtx Platform Evolve Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the CutCtx public website around verified context efficiency, intelligent routing, integrations, and optional governance while preserving the existing commercial and deployment contract.

**Architecture:** The static site remains dependency-light HTML/CSS/JavaScript under `website/`. A shared self-hosted font and navigation system supports all public pages; the homepage becomes the platform overview, while new Routing and Integrations pages own detailed capability explanations. Regression tests assert public copy contracts and route links before visual QA verifies responsive behavior and production acceptance.

**Tech Stack:** Static HTML, CSS, vanilla JavaScript, local WOFF2 assets, pytest static-site assertions, Cloudflare Pages.

## Global Constraints

- Preserve the existing dark Evolve art direction while replacing the compression-only narrative with a platform narrative.
- Use self-hosted Instrument Sans and JetBrains Mono WOFF2 assets only; no remote fonts, trackers, or external media.
- Keep `CutCtx is a product of PitchToShip` disclosure and the exact existing PitchToShip billing URLs.
- Never claim a universal provider count, savings percentage, certification, guaranteed routing result, or unverified plan entitlement.
- Call `codex-gpt54mini-high` the canonical routing preset; label `codex-opencode-slim` and `oh-my-opencode-slim` only as compatibility aliases.
- Describe routing as opt-in, conservative, and fail-closed when provider/account/transport/capability/readiness gates do not permit a route.
- Separate core runtime, intelligent optimization, operator layer, integrations, and optional enterprise controls.
- Retain all existing legal meaning, security caveats, accessibility behavior, mobile navigation, and 44px+ touch targets.
- Preserve unrelated dirty working-tree files; stage only files owned by each task.
- Use `github-personal` for push and do not delete or change unrelated Cloudflare resources.

---

### Task 1: Define platform and routing website contracts

**Files:**
- Modify: `tests/website/test_static_site.py`

**Interfaces:**
- Consumes: public HTML files under `website/`.
- Produces: regression contracts for routing, integrations, shared navigation, local fonts, exact commerce links, and non-claim boundaries.

- [ ] **Step 1: Write failing contracts for the new public surfaces**

```python
def test_public_platform_navigation_and_routes_are_present():
    home = read_page("website/index.html")
    routing = read_page("website/routing/index.html")
    integrations = read_page("website/integrations/index.html")
    for page in (home, routing, integrations):
        assert 'href="/routing/"' in page
        assert 'href="/integrations/"' in page
        assert "CutCtx is a product of PitchToShip" in page


def test_routing_page_uses_only_verified_routing_language():
    routing = read_page("website/routing/index.html")
    assert "codex-gpt54mini-high" in routing
    assert "codex-opencode-slim" in routing
    assert "oh-my-opencode-slim" in routing
    assert "opt-in" in routing.lower()
    assert "capability" in routing.lower()
    assert "guaranteed" not in routing.lower()


def test_docs_include_the_verified_routing_status_evaluation():
    docs = read_page("website/docs/index.html")
    assert "cutctx routing status --proxy-url http://127.0.0.1:8787" in docs


def test_public_pages_use_self_hosted_platform_fonts():
    css = read_page("website/assets/site.css")
    assert "@font-face" in css
    assert "/assets/fonts/" in css
    assert "fonts.googleapis.com" not in css
```

- [ ] **Step 2: Expand existing route and sitemap contracts**

```python
PUBLIC_PAGES = [
    Path("website/index.html"),
    Path("website/routing/index.html"),
    Path("website/integrations/index.html"),
    Path("website/pricing/index.html"),
    Path("website/docs/index.html"),
    Path("website/security/index.html"),
    Path("website/terms/index.html"),
    Path("website/privacy/index.html"),
    Path("website/refunds/index.html"),
]

def test_sitemap_includes_all_cutctx_public_destinations():
    sitemap = Path("website/sitemap.xml").read_text(encoding="utf-8")
    for path in ("/routing/", "/integrations/"):
        assert f"https://cutctx.com{path}" in sitemap
```

- [ ] **Step 3: Run the focused suite to verify failure**

Run: `rtk pytest tests/website/test_static_site.py -q`  
Expected: FAIL because the routing/integrations pages, font declarations, and routing status copy do not yet exist.

- [ ] **Step 4: Commit the red test contract**

```bash
rtk git add tests/website/test_static_site.py
rtk git commit -m "test: define CutCtx platform website contracts"
```

### Task 2: Establish shared typography, platform navigation, and visual primitives

**Files:**
- Create: `website/assets/fonts/instrument-sans-latin.woff2`
- Create: `website/assets/fonts/instrument-sans-latin-bold.woff2`
- Create: `website/assets/fonts/jetbrains-mono-latin.woff2`
- Modify: `website/assets/site.css`
- Modify: `website/index.html`
- Modify: `website/pricing/index.html`
- Modify: `website/docs/index.html`
- Modify: `website/security/index.html`
- Modify: `website/terms/index.html`
- Modify: `website/privacy/index.html`
- Modify: `website/refunds/index.html`

**Interfaces:**
- Consumes: Task 1’s local-font and shared-navigation contracts.
- Produces: `--font-sans`, `--font-mono`, shared navigation links, shared footer links, and reusable platform/decision-grid CSS classes used by later pages.

- [ ] **Step 1: Acquire only license-compatible WOFF2 font assets and verify the local paths**

```bash
rtk find website/assets/fonts
```

Expected: the three WOFF2 files above exist beneath `website/assets/fonts/`; no HTML page references an external font URL.

- [ ] **Step 2: Add the failing static asset assertions if asset naming differs from Task 1**

```python
def test_platform_font_assets_are_local_and_present():
    for asset in (
        "website/assets/fonts/instrument-sans-latin.woff2",
        "website/assets/fonts/instrument-sans-latin-bold.woff2",
        "website/assets/fonts/jetbrains-mono-latin.woff2",
    ):
        assert Path(asset).exists()
```

- [ ] **Step 3: Implement shared CSS font faces, variables, and new layout primitives**

```css
@font-face {
  font-family: "Instrument Sans";
  src: url("/assets/fonts/instrument-sans-latin.woff2") format("woff2");
  font-display: swap;
  font-style: normal;
  font-weight: 400 500;
}

@font-face {
  font-family: "Instrument Sans";
  src: url("/assets/fonts/instrument-sans-latin-bold.woff2") format("woff2");
  font-display: swap;
  font-style: normal;
  font-weight: 600 800;
}

@font-face {
  font-family: "JetBrains Mono";
  src: url("/assets/fonts/jetbrains-mono-latin.woff2") format("woff2");
  font-display: swap;
  font-style: normal;
  font-weight: 400 600;
}

:root {
  --font-sans: "Instrument Sans", ui-sans-serif, system-ui, sans-serif;
  --font-mono: "JetBrains Mono", "SFMono-Regular", Consolas, monospace;
}

body { font-family: var(--font-sans); }
.eyebrow, code, pre, .hero-note, .page-kicker, .chip, .flow-label {
  font-family: var(--font-mono);
}
```

Add reusable `.platform-map`, `.platform-card`, `.decision-flow`,
`.decision-step`, `.integration-grid`, and `.route-receipt` components with
the same border, contrast, motion, and breakpoint rules as the existing cards.

- [ ] **Step 4: Replace the shared navigation/footer link sets**

```html
<a href="/#platform">Platform</a>
<a href="/routing/">Routing</a>
<a href="/integrations/">Integrations</a>
<a href="/docs/">Docs</a>
<a href="/pricing/">Pricing</a>
<a href="/security/">Security</a>
```

Keep the existing Start free button unchanged and add Routing/Integrations to
each footer. Ensure every public page keeps `data-mobile-nav-toggle`,
`data-mobile-nav`, skip link, and `id="main-content"`.

- [ ] **Step 5: Run the focused suite to verify passing shared contracts**

Run: `rtk pytest tests/website/test_static_site.py -q`  
Expected: shared-font and shared-navigation assertions pass; page-content assertions not yet implemented may remain failing until their task.

- [ ] **Step 6: Commit the shared visual system**

```bash
rtk git add website/assets/fonts website/assets/site.css website/index.html website/pricing/index.html website/docs/index.html website/security/index.html website/terms/index.html website/privacy/index.html website/refunds/index.html tests/website/test_static_site.py
rtk git commit -m "style: establish CutCtx platform typography"
```

### Task 3: Rebuild the homepage around the complete platform flow

**Files:**
- Modify: `website/index.html`
- Modify: `tests/website/test_static_site.py`

**Interfaces:**
- Consumes: Task 2 platform CSS classes and shared navigation.
- Produces: `#platform` overview, `#how-it-works` connected operating flow, routing CTA, and clear core/optional offering labels.

- [ ] **Step 1: Write failing homepage content contracts**

```python
def test_homepage_positions_routing_as_a_core_capability():
    home = read_page("website/index.html")
    assert "intelligent routing" in home.lower()
    assert 'href="/routing/"' in home
    assert "Route or retain" in home
    assert "codex-gpt54mini-high" in home


def test_homepage_exposes_the_verified_platform_layers():
    home = read_page("website/index.html")
    for label in (
        "Core runtime",
        "Intelligent optimization",
        "Operator layer",
        "Developer and agent access",
        "Optional enterprise controls",
    ):
        assert label in home
```

- [ ] **Step 2: Run only the new homepage tests to verify failure**

Run: `rtk pytest tests/website/test_static_site.py -q`  
Expected: FAIL because the current homepage remains compression-first.

- [ ] **Step 3: Replace the hero and product-flow markup**

```html
<div class="eyebrow">Context efficiency + intelligent routing</div>
<h1>Make every agent turn earn its context and its model.</h1>
<p class="lede">CutCtx is a local-first platform for understanding agent context, reducing overhead, recovering useful state, and making conservative routing decisions on the workload you already run.</p>
<a class="button button-secondary" href="/routing/">Explore routing</a>
```

Use the seven flow stages exactly as the design specifies: Observe, Understand,
Compress / Recover, Route or retain, Forward, Measure, and Govern. Show
“requested model retained” as a valid routing outcome beside “eligible route
applied”; never use a savings percentage or a universal routing claim.

- [ ] **Step 4: Add the platform-offerings map and compatibility section**

```html
<section class="section" id="platform" aria-labelledby="platform-heading">
  <div class="section-heading">
    <div class="eyebrow">One operating layer, deliberate boundaries</div>
    <h2 id="platform-heading">Improve the context and the decision around it.</h2>
  </div>
  <div class="platform-map">
    <article class="platform-card"><div class="eyebrow">Core runtime</div><h3>Context that stays useful.</h3><p>Observe, compress, recover, proxy, and measure locally.</p></article>
    <article class="platform-card"><div class="eyebrow">Intelligent optimization</div><h3>Route or retain deliberately.</h3><p>Use opt-in routing only when the request and transport are eligible.</p></article>
    <article class="platform-card"><div class="eyebrow">Operator layer</div><h3>Inspect the result.</h3><p>Review savings, latency, budgets, routing, health, and diagnostics.</p></article>
    <article class="platform-card"><div class="eyebrow">Developer and agent access</div><h3>Meet existing workflows.</h3><p>Use SDKs, compatible proxies, CLI wrappers, MCP, agent plugins, and IDE integrations.</p></article>
    <article class="platform-card"><div class="eyebrow">Optional enterprise controls</div><h3>Govern when needed.</h3><p>Add identity, policy, audit, retention, tenancy, and entitlement controls deliberately.</p></article>
  </div>
</section>
```

- [ ] **Step 5: Run the static suite and inspect the home page locally**

Run: `rtk pytest tests/website/test_static_site.py -q`  
Expected: PASS for homepage platform/routing contracts.

- [ ] **Step 6: Commit the platform homepage**

```bash
rtk git add website/index.html tests/website/test_static_site.py
rtk git commit -m "feat: position CutCtx as a platform"
```

### Task 4: Add dedicated Routing and Integrations public destinations

**Files:**
- Create: `website/routing/index.html`
- Create: `website/integrations/index.html`
- Modify: `website/sitemap.xml`
- Modify: `tests/website/test_static_site.py`

**Interfaces:**
- Consumes: Task 2 shared shell/CSS and Task 1 routing contracts.
- Produces: public `/routing/` and `/integrations/` pages linked from all site navigation and the sitemap.

- [ ] **Step 1: Write failing content contracts for each destination**

```python
def test_integrations_page_maps_verified_access_surfaces():
    integrations = read_page("website/integrations/index.html")
    for label in (
        "Python", "TypeScript", "Go", "MCP", "VS Code", "JetBrains",
        "OpenAI", "Anthropic", "Gemini",
    ):
        assert label in integrations
    assert "100+ providers" not in integrations


def test_routing_page_describes_safe_retention_and_aliases():
    routing = read_page("website/routing/index.html")
    for label in (
        "requested model retained", "provider", "account", "transport",
        "codex-gpt54mini-high", "codex-opencode-slim", "oh-my-opencode-slim",
    ):
        assert label in routing
```

- [ ] **Step 2: Run the targeted static suite to verify failure**

Run: `rtk pytest tests/website/test_static_site.py -q`  
Expected: FAIL because neither public route exists.

- [ ] **Step 3: Implement `website/routing/index.html`**

Use the shared header/footer and include these exact content blocks:

```html
<div class="eyebrow">Intelligent routing, deliberately constrained</div>
<h1>Use a more efficient model only when the work earns it.</h1>
<p>CutCtx routing is opt-in. It keeps the requested model when the work is high-risk, ambiguous, tool-heavy, capability-incompatible, or not proven safe for the active provider, account, and transport.</p>
```

Add a decision grid covering request complexity, required capabilities,
provider/account/transport proof, readiness/certification, and an observable
outcome. Add a compact receipt visual containing “eligible route applied” and
“requested model retained.” Include canonical preset text and label aliases as
compatibility aliases. Link to `/docs/#routing-status` and never frame a route
as guaranteed.

- [ ] **Step 4: Implement `website/integrations/index.html`**

Use the shared shell and group verified surfaces into SDKs, compatible provider
paths, agent/CLI access, plugins/MCP/gateways, and IDE extensions. Mention
OpenAI, Anthropic, Gemini, TypeScript, Go, Python, Codex, Claude Code,
OpenCode, MCP, VS Code, and JetBrains only in a correctly scoped integration
context. Use “verified integration surfaces” rather than an unqualified
compatibility guarantee.

- [ ] **Step 5: Add canonical URLs and sitemap entries**

```xml
<url><loc>https://cutctx.com/routing/</loc></url>
<url><loc>https://cutctx.com/integrations/</loc></url>
```

Each new page must include its own canonical URL, Open Graph URL, versioned
favicon/CSS/JavaScript asset URLs, skip link, mobile navigation controls, and
PitchToShip footer disclosure.

- [ ] **Step 6: Run the static suite to verify passing public-route contracts**

Run: `rtk pytest tests/website/test_static_site.py -q`  
Expected: PASS.

- [ ] **Step 7: Commit the new public destinations**

```bash
rtk git add website/routing/index.html website/integrations/index.html website/sitemap.xml tests/website/test_static_site.py
rtk git commit -m "feat: add CutCtx routing and integrations pages"
```

### Task 5: Align docs, pricing, security, and legal shell with the platform story

**Files:**
- Modify: `website/docs/index.html`
- Modify: `website/pricing/index.html`
- Modify: `website/security/index.html`
- Modify: `website/terms/index.html`
- Modify: `website/privacy/index.html`
- Modify: `website/refunds/index.html`
- Modify: `tests/website/test_static_site.py`

**Interfaces:**
- Consumes: Task 2 shared navigation, Task 4 public route URLs, and the verified routing-status command.
- Produces: a consistent buyer journey across evaluation, pricing, security, and legal pages.

- [ ] **Step 1: Write failing cross-page contracts**

```python
def test_public_navigation_reaches_platform_destinations():
    for page in PUBLIC_PAGES:
        html = page.read_text(encoding="utf-8")
        assert 'href="/routing/"' in html
        assert 'href="/integrations/"' in html


def test_pricing_does_not_invent_routing_entitlements():
    pricing = read_page("website/pricing/index.html")
    assert "unlimited routing" not in pricing.lower()
    assert "guaranteed savings" not in pricing.lower()


def test_security_explains_routing_safety_without_certification_claims():
    security = read_page("website/security/index.html")
    assert "capability" in security.lower()
    assert "transport" in security.lower()
    assert "SOC 2 certified" not in security
```

- [ ] **Step 2: Run the static suite to verify failure**

Run: `rtk pytest tests/website/test_static_site.py -q`  
Expected: FAIL until navigation and content changes are in place.

- [ ] **Step 3: Add a fifth Docs quick-start step for read-only routing evaluation**

```html
<a href="#routing-status">05 Routing status</a>
...
<section class="docs-step" id="routing-status">
  <div class="eyebrow">Step 05</div>
  <h2>Inspect routing before changing it</h2>
  <p>When the optional Safe Savings status surface is enabled, inspect the active routing state and the latest privacy-safe decision without changing provider, account, transport, or model configuration.</p>
  <pre><code>cutctx routing status --proxy-url http://127.0.0.1:8787</code></pre>
</section>
```

- [ ] **Step 4: Update pricing and security copy without changing commerce contracts**

Pricing should explain evaluation → coordination → governed operation and link
to Routing/Integrations. Preserve the exact two PitchToShip billing URLs,
prices, plan names, merchant disclosure, and Enterprise mailto link.

Security should explain customer-controlled execution/egress/retention plus
the capability/provider/account/transport gates applied before optimization
routing. Retain the explicit absence of SOC 2/HIPAA certification claims.

- [ ] **Step 5: Add Routing and Integrations links to each legal-page shell only**

Do not alter legal body copy or commercial/legal meaning. Modify only shared
header/footer navigation so it matches the public site.

- [ ] **Step 6: Run the full static suite**

Run: `rtk pytest tests/website/test_static_site.py -q`  
Expected: PASS.

- [ ] **Step 7: Commit buyer-journey alignment**

```bash
rtk git add website/docs/index.html website/pricing/index.html website/security/index.html website/terms/index.html website/privacy/index.html website/refunds/index.html tests/website/test_static_site.py
rtk git commit -m "feat: align CutCtx evaluation journey"
```

### Task 6: Perform visual, accessibility, and production verification

**Files:**
- Modify only if a regression is found: `website/assets/site.css`, affected `website/*.html`, or `tests/website/test_static_site.py`

**Interfaces:**
- Consumes: completed public static site.
- Produces: evidence that the new platform story is responsive, accessible, deployed from `main`, and canonicalized correctly.

- [ ] **Step 1: Start a local static server and inspect every public route**

```bash
rtk proxy python3 -m http.server 4173 --directory website
```

Inspect `/`, `/routing/`, `/integrations/`, `/pricing/`, `/docs/`,
`/security/`, `/terms/`, `/privacy/`, and `/refunds/` at 390px, 768px, 1024px,
and 1440px widths.

- [ ] **Step 2: Verify responsive and interaction acceptance**

For each inspection, confirm:

```text
scrollWidth === viewportWidth
mobile menu changes aria-expanded and data-open
all navigation links are reachable by keyboard and touch
the primary CTA is at least 44px tall on mobile
the routing decision flow remains readable without clipped labels
reduced-motion media query disables nonessential transition duration
browser console has no warning or error entries
```

- [ ] **Step 3: Run final static checks**

```bash
rtk pytest tests/website/test_static_site.py -q
rtk proxy git diff --check
```

Expected: all static tests pass and diff check emits no whitespace errors.

- [ ] **Step 4: Commit any QA-only fixes separately**

```bash
rtk git add website tests/website/test_static_site.py
rtk git commit -m "fix: polish CutCtx platform website"
```

Only create this commit if QA produced a source change.

- [ ] **Step 5: Push the completed website to main through the approved SSH profile**

```bash
rtk git push origin main
```

Expected: output identifies `github-personal:AryanSingh/headroom.git` and
updates `main` successfully.

- [ ] **Step 6: Verify Cloudflare Pages production acceptance**

```bash
rtk proxy sh -lc 'set -eu; for path in / /routing/ /integrations/ /pricing/ /docs/ /security/ /terms/ /privacy/ /refunds/; do code=$(curl -sS -o /dev/null -w "%{http_code}" "https://cutctx.com${path}"); printf "%s %s\n" "$code" "$path"; test "$code" = 200; done; redirect=$(curl -sS -o /dev/null -w "%{http_code} %{redirect_url}" "https://www.cutctx.com/routing/?final=1"); printf "%s\n" "$redirect"; test "$redirect" = "301 https://cutctx.com/routing/?final=1"'
```

Expected: all routes return `200`; `www` returns a `301` to the matching apex
path with its query preserved. Do not change any Cloudflare resource other than
the existing Pages deployment triggered by `main`.

- [ ] **Step 7: Record release acceptance**

Update `audit/launch-readiness-cutctx-website-evolve-2026-07-21.md` with the
new implementation commit, routing/integrations route checks, platform
messaging acceptance, and exact canonical redirect evidence. Run the static
suite again, commit only that report, and push `main`.

---

## Plan Self-Review

### Spec coverage

- Platform-level positioning and seven-stage system flow: Task 3.
- Model routing and canonical/alias accuracy: Tasks 1 and 4.
- Verified integrations and public discoverability: Tasks 2 and 4.
- Documentation routing evaluation: Task 5.
- Truthful pricing, merchant, security, legal, and enterprise boundaries: Task 5.
- Self-hosted typography and Evolve visual system: Task 2.
- Static regression tests, responsive QA, deployment, and redirect acceptance: Tasks 1 and 6.

### Placeholder scan

The plan contains no unresolved markers, undefined public paths, invented
function signatures, or unspecified test commands. The one conditional QA
commit is intentionally explicit: it is created only when a QA source change
exists.

### Boundary and consistency check

All new routes use shared navigation, versioned local assets, shared footer
disclosure, and the same static test suite. Routing is described consistently
as opt-in, conservative, observable, and constrained; pricing does not promise
an entitlement that repository evidence does not establish.
