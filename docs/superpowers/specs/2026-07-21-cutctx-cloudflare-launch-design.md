# CutCtx Cloudflare launch design

**Status:** Approved direction pending written-spec review

## Objective

Launch `cutctx.com` as CutCtx's conversion-focused product domain without
altering the existing `pitchtoship.com` Cloudflare zone, Worker, DNS records,
or hosted commerce implementation. Convert technical evaluators into Builder
users, qualified Team/Business buyers, and Enterprise conversations as quickly
as practical.

## Product and buyer framing

CutCtx is a local-first context-efficiency layer for AI-agent and LLM
workloads. Its primary promise is to reduce context overhead while preserving
useful information and retaining a customer's choice of model provider.

The site will speak to two entry audiences:

1. **Individual engineers and evaluators** who need a quick local installation
   and evidence of savings.
2. **Engineering/platform leaders** who need team-level reporting,
   deployment options, and an enterprise security story.

The site must not claim a fixed savings percentage. It may describe verified
benchmark examples as examples with a methodology link, never as a universal
customer outcome.

## Launch surface

`cutctx.com` will contain a purpose-built static marketing site, deployed as a
new isolated Cloudflare Pages project (or, if Pages requires a build path not
available in this repository, a new isolated Cloudflare Worker). It is not the
operational CutCtx dashboard.

| Route | Purpose | Primary action |
| --- | --- | --- |
| `/` | Conversion landing page | Start free / View pricing |
| `/pricing` | Clear Builder, Team, Business, Enterprise packaging | Start with CutCtx / Talk to sales |
| `/docs` | Installation and evaluation entry point | Install CutCtx |
| `/security` | Local-first data handling and governance posture | Read security details |
| `/terms` | Published commercial terms after legal-entity correction and review | — |
| `/privacy` | Published privacy notice after contact/entity check | — |
| `/refunds` | Plain-language refund/cancellation policy matched to PitchToShip's policy | — |

The homepage will use a simple narrative: outcome, how it works, compatible
workflows/providers, proof and security, then price/CTA. It will prominently
present two conversion paths:

- `Start free`: the Builder installation/evaluation route.
- `Choose a plan`: the existing PitchToShip checkout URL with CutCtx plan and
  billing context.

`www.cutctx.com` redirects permanently to `cutctx.com`. All routes use HTTPS.

## Capability claims allowed on the site

The site may accurately present these verified capabilities:

- Compatible proxy paths for OpenAI, Anthropic, Gemini/Vertex, Bedrock, and
  OpenRouter-style provider flows.
- CLI wrapping and current integration coverage for major coding agents,
  including Claude Code, Codex, Cursor, Cline, Continue, Aider, OpenHands,
  Windsurf, Zed, OpenCode, OpenClaw, and Goose.
- Local-first proxy, CLI, MCP, memory/CCR, and real-time savings telemetry.
- Docker, Docker Compose, Kubernetes, and air-gapped deployment paths.
- Commercial tiers for analytics, reports, budgeting, organization/project
  models, SSO/OIDC, RBAC, audit export, retention controls, fleet APIs, and
  SCIM-style provisioning APIs.

It must not claim formal certifications, universal savings, a hosted prompt
analytics service, a complete enterprise admin UI, or specific privacy/legal
commitments that the final reviewed legal pages do not support.

## Commerce and legal disclosure

PitchToShip remains the merchant of record and the only hosted commerce
authority. CutCtx never handles Razorpay credentials or payment webhooks.

Every pricing/checkout-adjacent page will disclose:

> CutCtx is a product of PitchToShip. Payments, invoices, licensing, and
> customer account management are provided by PitchToShip.

Checkout actions will retain the existing deterministic PitchToShip deep-link
contract. Product pages will make the product being purchased explicit, while
invoices and the card descriptor will remain aligned with PitchToShip's
configured payment-processor identity.

Before publication, legal pages must replace stale references to `Cutctx Labs`,
`sales@payzli.com`, and any unverified governing-law/refund wording with the
actual legal identity, address, support contacts, tax treatment, and processor
policy approved by the owner or qualified counsel.

## Cloudflare and DNS plan

1. Add `cutctx.com` as a separate Cloudflare zone; do not touch any existing
   zone or Worker.
2. Cloudflare provides two assigned authoritative nameservers.
3. Change only the BigRock nameservers for `cutctx.com` to those two assigned
   values. Do not modify `pitchtoship.com` nameservers.
4. Create a new dedicated CutCtx Pages/Worker deployment and bind the apex
   custom domain after the zone becomes active.
5. Add only the DNS records required by the new CutCtx deployment, the `www`
   redirect, and approved email service verification. Preserve all existing
   CutCtx records; inspect for conflicts before every change.
6. Enable HTTPS, redirect `www` to apex, and add conservative static-site
   security headers.

## Measurement and conversion operations

Launch with privacy-respecting conversion measurement: outbound click events
for `Start free`, checkout, docs, and enterprise contact. Do not deploy
third-party analytics that capture prompt or customer content. The first
commercial success loop is install -> use -> savings report -> plan selection.

The content should set the expectation that a customer evaluates their own
traffic and reports rather than relying solely on benchmark claims.

## Error handling and rollback

- Validate that Cloudflare marks the new zone active before binding the custom
  domain.
- Preserve a preview deployment for each site release; make a production
  deployment only after layout, link, metadata, and checkout-link checks pass.
- If DNS validation fails, leave current BigRock DNS in place and report the
  expected versus observed nameservers rather than attempting alternate
  records.
- If a new publication fails, roll back only the dedicated CutCtx deployment;
  never roll back or redeploy PitchToShip as part of this work.

## Verification

1. Confirm Cloudflare zone activation and public authoritative nameservers.
2. Confirm apex and `www` resolve correctly with valid TLS.
3. Verify every CTA: Builder path, pricing checkout deep link, account portal,
   documentation, and enterprise contact route.
4. Verify mobile/desktop layout, accessibility basics, page metadata, and
   noindex removal only at production readiness.
5. Confirm visible merchant-of-record disclosure and final legal-page links.
6. Confirm no CutCtx deployment change altered the PitchToShip Worker, DNS,
   or customer checkout flow.
