# CutCtx website “Evolve” design

**Status:** Approved
**Date:** 2026-07-21
**Deployment target:** `https://cutctx.com`
**Primary conversion:** Start free / local technical evaluation

## Objective

Evolve the existing CutCtx public website into a best-in-class, conversion-led
technical product experience without replacing its established identity,
commerce model, legal structure, or Cloudflare deployment. The redesign should
help a technical buyer understand the product quickly, see how it fits into an
existing workflow, and begin a local evaluation with minimal friction.

The primary customer journey is:

> Understand the outcome → see how CutCtx works → verify compatibility and
> trust → run it on an existing workflow → inspect measured results → select a
> commercial plan when appropriate.

The site will optimize its strongest and most repeated call to action for
`Start free`. Pricing remains a visible secondary path, and enterprise contact
appears after the product, deployment, and security story has established
enough context.

## Constraints and preserved contracts

The redesign must preserve the following production contracts:

- `cutctx.com` remains a static site deployed through the existing isolated
  Cloudflare Pages project from the repository's `main` branch and `website`
  output directory.
- No unrelated Cloudflare zone, DNS record, Worker, Pages project, or
  `pitchtoship.com` resource may be removed or replaced.
- PitchToShip remains the legal entity and commerce authority. CutCtx is the
  product and public brand.
- Existing PitchToShip checkout links, billing parameters, merchant disclosure,
  company identity, legal contacts, and published legal text remain intact
  unless a factual inconsistency is independently verified.
- The site must not claim universal savings, unsupported certifications,
  guaranteed outcomes, or functionality not represented by the product.
- External font, image, analytics, and frontend runtime dependencies should not
  be introduced. The current conservative content-security posture should be
  preserved.
- Existing routes remain valid: `/`, `/pricing/`, `/docs/`, `/security/`,
  `/terms/`, `/privacy/`, and `/refunds/`.

## Chosen design direction

The selected direction is a **technical editorial cockpit**. It retains the
existing dark navy and mint CutCtx identity, but introduces clearer product
evidence, stronger hierarchy, asymmetric composition, and restrained technical
interface details.

Two alternatives were considered and rejected as the primary direction:

1. A minimal enterprise infrastructure treatment would be credible and calm,
   but would not make CutCtx sufficiently memorable or explain the product as
   quickly.
2. A dense neon command-center treatment would be visually distinctive, but
   could feel gimmicky, reduce readability, and distract from commercial trust.

The chosen direction should feel advanced without appearing experimental. It
is an evolution of the current site rather than a wholesale rebrand.

## Audience and message hierarchy

The website serves two related audiences:

1. Individual engineers and technical evaluators who want a quick installation,
   compatibility with existing agents and providers, local control, and a way
   to measure their own workload.
2. Engineering, platform, and AI leaders who need shared reporting, policy,
   deployment flexibility, governance, and a credible commercial path.

The homepage must communicate the following in order:

1. CutCtx reduces context overhead while preserving access to useful context.
2. It works as a control layer around existing AI-agent and LLM workflows.
3. It supports the buyer's chosen providers and deployment model.
4. It provides measurement on the buyer's own traffic rather than relying on a
   generic savings promise.
5. A local evaluation is the lowest-friction next step.

Copy should be direct, compact, and technical. Outcome language should precede
feature inventories. Search-relevant phrases such as LLM context compression,
AI-agent context, token usage, proxy, retrieval, local-first, and supported
providers may be used naturally, but keyword density must not undermine
clarity.

## Homepage information architecture

### 1. Navigation

Use a sticky, subtly translucent navigation bar that remains visually quiet.
It contains the CutCtx brand, Product, Pricing, Docs, and Security destinations,
plus a persistent `Start free` primary button. Enterprise contact should remain
available through the Pricing or Security journey without competing in the
global header.

The mobile navigation must retain semantic button state, keyboard operation,
large touch targets, and a clear expanded panel. The brand and primary action
should remain recognizable at small widths.

### 2. Split hero

The hero becomes a two-column composition on desktop:

- The editorial side contains an outcome-led headline, one concise supporting
  paragraph, `Start free` as the primary action, and `See how it works` as the
  secondary action.
- The product side contains a lightweight CSS/SVG interface that illustrates
  context entering CutCtx, compression and retrievability, a smaller payload
  reaching the selected model, and measurement appearing in a report.

The visualization must represent actual product concepts and must not display
unsupported performance claims. If example quantities are useful, they must be
explicitly labelled as an illustrative evaluation rather than a typical or
guaranteed result. Prefer qualitative state and process signals if a number is
not needed.

On tablet, the visualization moves beneath the editorial copy. On mobile, it
becomes a compact vertical flow rather than disappearing.

### 3. Compatibility and trust strip

Present supported provider and agent families as restrained text chips or
compact labels. The initial set may include OpenAI, Anthropic, Gemini/Vertex,
Amazon Bedrock, local or chosen endpoints, Claude Code, Codex, Cursor, Cline,
Aider, and other verified integrations.

Avoid an oversized logo wall, externally hosted marks, or implying formal
partnerships. The purpose is fast compatibility recognition.

### 4. How CutCtx works

Explain the product with a four-stage visual sequence:

> Observe → Compress → Retrieve → Prove

- **Observe:** accept compatible traffic and understand workload context.
- **Compress:** reduce unnecessary context overhead using protocol-aware
  controls.
- **Retrieve:** preserve access to useful information through retrieval,
  memory, and related context controls.
- **Prove:** expose telemetry and reports so buyers can evaluate their own
  traffic.

This section is the conceptual bridge between the hero and the feature detail.
It should remain understandable without animation or JavaScript.

### 5. Product capabilities

Replace repeated equal-width card grids with an asymmetric capability layout.
Context efficiency is the visually dominant capability. Supporting areas may
include:

- proxy and provider compatibility;
- coding-agent wrapping and integrations;
- retrieval, memory, and cache-aware controls;
- routing and policy control;
- local dashboard, telemetry, and reporting;
- local, Docker, Kubernetes, and air-gapped deployment paths.

Different content types should use different component proportions and
presentations. Not every feature should be forced into the same card template.

### 6. Evaluation and evidence

Create a conversion-focused section that shows the shortest credible path:

1. Install CutCtx locally.
2. Wrap or route an existing supported workflow.
3. Run normal traffic.
4. Inspect the resulting savings report and operational telemetry.

The primary action is `Run it on your workflow` or equivalent, linking directly
to the relevant quick-start location. This section must reinforce that the
buyer evaluates results on their own workload.

### 7. Security and deployment

Summarize local-first processing, customer-controlled deployment, provider
flexibility, Docker and Kubernetes support, and air-gapped options where
accurate. Link to the dedicated Security page for details.

Do not claim formal compliance certifications. Distinguish core local-first
behaviour from commercial governance features when necessary.

### 8. Commercial path and final conversion

Include a concise pricing preview for Builder, Team, and Enterprise journeys.
Builder is the easiest evaluation path; Team focuses on shared analytics,
policy, and budget control; Enterprise focuses on governance, deployment, and
support.

The final conversion band repeats `Start free`, with Pricing as a secondary
route. Retain the visible disclosure:

> CutCtx is a product of PitchToShip. Payments, invoices, licensing, and
> customer account management are provided by PitchToShip.

## Visual system

### Colour and surfaces

- Preserve a deep navy page foundation and mint brand accent.
- Use mint more selectively than the current site so primary actions and key
  process states carry stronger meaning.
- Add restrained blue-green illumination and layered surfaces for depth.
- Use off-white primary text and cooler muted text with verified contrast.
- Prefer thin technical borders and controlled shadows over heavily glowing
  or glass-heavy panels.

### Typography

- Use large, tightly composed display headlines with deliberately controlled
  line breaks at key breakpoints.
- Keep body copy compact, readable, and narrower than the full section width.
- Reserve monospace styling for commands, tokens, providers, state labels, and
  interface evidence.
- Use locally available or system font stacks to preserve performance, privacy,
  and the content-security policy.

### Components and layout

- Use a consistent spacing, radius, border, and colour token system across all
  public routes.
- Introduce asymmetric editorial grids, process lines, status indicators,
  compact chips, code blocks, evidence panels, and an intentionally emphasized
  pricing path.
- Avoid reproducing the same bordered card for every section.
- Keep the footer visually quieter than the conversion content while preserving
  all legal navigation and merchant disclosure.

## Motion and progressive enhancement

Motion is decorative and explanatory, never required to understand or use the
page.

- The hero visualization may use subtle staged state changes.
- Buttons, navigation, chips, and panels may use short hover and focus
  transitions.
- Section reveals may be used sparingly to guide attention.
- Continuous, distracting, or high-amplitude animation is out of scope.
- `prefers-reduced-motion` must disable non-essential animation and smooth
  scrolling.
- The complete content hierarchy and every navigation or conversion path must
  work without JavaScript, except for the existing mobile menu enhancement.

## Conversion and measurement

The repeated CTA hierarchy is:

- Header: `Start free`
- Hero: `Start free`; secondary `See how it works`
- Evidence section: `Run it on your workflow`
- Pricing: plan-specific actions
- Final band: `Start free`; secondary Pricing

Preserve the existing privacy-respecting custom-event model and extend CTA
labels only where useful to distinguish placement. Do not introduce invasive
third-party analytics or any mechanism that captures prompt or customer
content. Avoid forced email gates, autoplay media, popups, and modal-first
conversion patterns.

## Route-specific evolution

### Pricing

- Improve plan comparison and recommendation hierarchy.
- Position Builder as the lowest-friction evaluation route.
- Position Team around shared analytics, policy, and budget control.
- Position Enterprise around governance, deployment, and support.
- Preserve all current PitchToShip checkout destinations and encoded billing
  parameters.
- Keep merchant disclosure explicit near checkout-adjacent content.
- Do not invent plan availability, prices, guarantees, or features.

### Docs

- Surface installation immediately.
- Present a clear sequence from install to proxy setup, agent wrapping, normal
  use, and savings-report inspection.
- Improve scanning, code blocks, callouts, and anchorable quick-start steps.
- Route homepage evaluation CTAs to the most relevant start point.

### Security

- Put the local-first trust summary above the fold.
- Group deployment control, data handling, governance, and operational controls
  logically.
- Keep claims constrained to verified implementation and published policy.
- Provide a clear path to enterprise contact after sufficient detail.

### Legal pages

- Apply shared navigation, typography, spacing, focus behaviour, and footer
  tokens.
- Do not creatively rewrite legal meaning.
- Preserve the verified legal entity, address, contact, governing-law, refund,
  and merchant information.

## Accessibility and responsive requirements

- Preserve the skip link, landmarks, semantic navigation, and logical heading
  order.
- Maintain visible keyboard focus with sufficient contrast.
- Ensure interactive controls are at least 44 CSS pixels in their primary touch
  dimension on mobile.
- Verify text and meaningful interface graphics against appropriate contrast
  expectations.
- Keep the mobile product flow visible and understandable.
- Prevent horizontal overflow in headlines, compatibility chips, code blocks,
  pricing content, and footer links.
- Manually tune headline sizes and line breaks rather than relying only on one
  fluid clamp.
- Test at representative small mobile, large mobile, tablet, laptop, and wide
  desktop widths.

## Performance and security requirements

- Retain the static HTML/CSS/JavaScript architecture.
- Prefer CSS and inline or self-hosted SVG interface visuals over raster assets.
- Avoid new production dependencies and large media payloads.
- Keep JavaScript small and non-blocking.
- Preserve current HTTPS, CSP, HSTS, MIME-sniffing, and redirect contracts.
- Avoid layout shift by reserving visualization dimensions and using stable font
  stacks.
- Do not load remote fonts, trackers, or interface assets.

## Testing and acceptance criteria

Implementation is complete only when all of the following are demonstrated:

1. The homepage visibly follows the approved technical editorial cockpit
   direction and no longer relies primarily on repeated equal card grids.
2. `Start free` is the dominant action in navigation, hero, evidence, and final
   conversion areas.
3. The hero contains a responsive product visualization that reflects verified
   CutCtx concepts without unsupported numerical claims.
4. The Observe → Compress → Retrieve → Prove flow is understandable with
   JavaScript and animation disabled.
5. Pricing, Docs, Security, and legal routes share the evolved visual system.
6. Existing PitchToShip checkout URLs, merchant disclosure, legal entity, and
   legal contacts remain correct.
7. Desktop and representative mobile layouts have no horizontal overflow,
   obscured controls, broken navigation, or unreadable sections.
8. Keyboard navigation, focus presentation, reduced motion, semantic headings,
   and mobile touch targets are verified.
9. Static-site tests pass and include assertions for the primary CTA,
   product-flow structure, merchant disclosure, billing links, and supported
   security claims.
10. Production verification confirms successful Cloudflare deployment from
    `main`, valid HTTPS, correct apex and `www` behaviour, working CTAs, and no
    modification to unrelated Cloudflare resources.

## Delivery sequence

After this specification is reviewed and accepted:

1. Create a detailed implementation plan with file-level tasks and verification
   checkpoints.
2. Update or add tests before behavioural implementation where practical.
3. Implement shared design tokens and components, then route-specific content.
4. Verify locally across the complete static-site test suite and representative
   breakpoints.
5. Commit the implementation intentionally to `main` and push through the
   configured personal GitHub identity.
6. Allow the existing Cloudflare Pages integration to deploy from `main`.
7. Verify the live public routes and conversion destinations without altering
   unrelated Cloudflare state.

## Out of scope

- Rebranding CutCtx or replacing the CutCtx/PitchToShip relationship.
- Rebuilding the marketing site in React or another frontend framework.
- Replacing PitchToShip checkout or handling payment credentials on CutCtx.
- Introducing customer-content analytics, session replay, or prompt capture.
- Publishing unsupported benchmarks, guarantees, certifications, or partner
  claims.
- Redesigning the operational React dashboard as part of the public website
  evolution.
