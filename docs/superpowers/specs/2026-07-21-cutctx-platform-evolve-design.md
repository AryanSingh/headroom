# CutCtx Platform Evolve Website Design

**Date:** 2026-07-21  
**Status:** Approved direction; implementation plan pending written-spec review  
**Scope:** Public website under `website/`, including homepage, pricing, docs,
security, and new routing/integrations public destinations.

## Goal

Reposition CutCtx from a compression-first utility to a coherent,
local-first **context-efficiency and intelligent-routing layer for LLM and
coding-agent workloads**. The website must make model routing a first-class,
accurately scoped capability while preserving the existing Evolve quality,
PitchToShip commerce path, legal meaning, and customer-controlled deployment
story.

## Evidence and product boundary

The public story is grounded in repository evidence:

- `cutctx/` supplies the Python runtime, CLI, proxy, context transforms,
  memory/retrieval, providers, routing, telemetry, and operational surfaces.
- `cutctx/proxy/model_router.py` and
  `docs/content/docs/model-routing-presets.mdx` define opt-in, conservative,
  capability-safe routing. The canonical public preset is
  `codex-gpt54mini-high`; `codex-opencode-slim` and `oh-my-opencode-slim` are
  compatibility aliases only.
- `dashboard/` supplies the operator console for health, savings, routing,
  capabilities, governance, memory, replay, and diagnostics.
- `sdk/`, `plugins/`, and `extensions/` provide verified application, agent,
  MCP, gateway, and IDE integrations.
- `cutctx_ee/` is optional proprietary enterprise functionality for tenancy,
  identity, policy, audit, retention, entitlements, billing, and related
  governance controls.
- `crates/` provides native Rust compression, proxy, Python bindings, and
  parity tooling. It is implementation strength, not a separate commercial
  product.

No website claim may add a universal provider count, savings percentage,
certificate, guaranteed routing result, pricing entitlement, or commercial
availability claim that the source does not establish.

## Audience and conversion path

### Technical evaluator

Needs a fast proof that CutCtx works with an existing agent or LLM workflow.
The route is: Homepage → Docs quick start → Install → wrap workflow → inspect
savings and routing status → Pricing when shared operation is needed.

### Platform or engineering lead

Needs to understand routing safety, provider compatibility, observability,
and integration fit. The route is: Homepage → Routing or Integrations → Docs
→ Pricing or Enterprise contact.

### Security or enterprise buyer

Needs clear boundaries around execution, egress, retention, audit, and
optional governance. The route is: Homepage → Security → Pricing → Enterprise
contact.

## Art direction

**Mode:** Evolve. Preserve the existing dark technical-editorial character,
but replace the compression-only visual story with an operating-system view of
the platform.

**Typography:** self-hosted Instrument Sans for display, body, navigation, and
interface text; self-hosted JetBrains Mono for commands, model names, routing
receipts, and technical labels. Keep robust system-font fallbacks. Do not add
remote font loading, third-party analytics, or external media dependencies.

**Visual language:** dense but readable technical diagrams, quiet grid lines,
high-contrast decision states, restrained accent color, and purposeful
monospace metadata. This differentiates CutCtx from generic AI-gateway dark
gradients and generic observability dashboards without sacrificing clarity.

## Information architecture

| Destination | Job | Required content |
| --- | --- | --- |
| `/` | Establish complete platform story and evaluation path. | Hero with routing prominence; platform flow; offering map; provider/agent compatibility; staged commercial path. |
| `/routing/` | Explain intelligent routing without overpromising. | Opt-in model routing; safe retention; capability/provider/account gates; routing status/evidence; canonical preset; compatibility aliases; CTA to evaluate. |
| `/integrations/` | Make verified access surfaces discoverable. | SDKs; compatible proxy contracts; CLI/wrappers; agent/MCP/gateway plugins; IDE integrations; provider compatibility, all properly scoped. |
| `/docs/` | Make initial local evaluation and routing evaluation actionable. | Existing install/wrap/report path plus a verified routing-status step; full-docs link. |
| `/pricing/` | Explain the stage-based commercial journey truthfully. | Evaluation, coordination, business, and governance path; verified PitchToShip URLs; no unverified routing entitlement or quota claims. |
| `/security/` | Explain technical boundaries and enterprise posture. | Customer environment, chosen provider, retention, fail-closed/routing controls, optional enterprise governance, no unsupported certifications. |

Primary navigation will expose **Platform**, **Routing**, **Integrations**,
**Docs**, **Pricing**, and **Security**, with the existing Start free CTA
retained. Mobile navigation must expose the same destinations.

## Homepage system flow

The existing `Observe → Compress → Retrieve → Prove` sequence will be replaced
with a connected platform flow:

```text
Observe → Understand → Compress / Recover → Route or retain → Forward → Measure → Govern
```

Each stage uses bounded, customer-facing language:

- **Observe:** see context, token, and workflow signals.
- **Understand:** classify protocol and request context.
- **Compress / Recover:** reduce overhead and retrieve useful context as
  needed.
- **Route or retain:** opt-in routing chooses an eligible lower-cost target
  only for clearly suitable requests; otherwise the requested model remains.
- **Forward:** use the team-selected provider or compatible endpoint.
- **Measure:** inspect savings, latency, budgets, and routing evidence.
- **Govern:** add policy, identity, audit, retention, and tenancy only when the
  deployment requires optional enterprise controls.

The hero will state this combined premise in the first major product section:
CutCtx makes each agent turn earn both its context and model choice. The
supporting copy will explicitly describe local-first context efficiency and
intelligent routing rather than promising a guaranteed cost result.

## Offering model

| Layer | Public representation | Availability framing |
| --- | --- | --- |
| Core runtime | Context observation, protocol-aware compression, retrieval, proxying, CLI, local evaluation, and telemetry. | Core workflow. |
| Intelligent optimization | Opt-in routing, conservative complexity handling, capability-safe candidate selection, and transparent reasons for retention. | Core capability with explicit safety constraints; do not imply all routes apply in all transports. |
| Operator layer | Savings, latency, routing, budgets, health, diagnostics, dashboard, and evidence. | Runtime/operator surfaces; feature detail follows deployment/configuration. |
| Developer and agent access | Python, TypeScript, and Go SDKs; compatible provider paths; CLI/wrappers; agent plugins; MCP; IDE integrations. | Verified integrations only; no universal compatibility claim. |
| Enterprise controls | Identity, RBAC, policy, audit, retention, tenancy, entitlements, billing, and lifecycle services. | Optional commercial/enterprise layer. |
| Native foundation | Rust compression, proxy, bindings, and parity tools. | Performance and implementation foundation, not a plan card. |

## Routing content contract

- The canonical preset is `codex-gpt54mini-high`.
- `codex-opencode-slim` and `oh-my-opencode-slim` are compatibility aliases.
- Routing is opt-in and intentionally conservative.
- Clearly low-complexity eligible GPT tasks may route to `gpt-5.4-mini`; the
  requested model remains for high-risk, broad, ambiguous, tool-heavy, or
  incompatible work.
- Eligible candidates are constrained by provider/account/transport proof,
  required request capabilities, readiness/certification, availability, and
  cost. When a gate fails, CutCtx retains the request model rather than
  bypassing the decision.
- Routing reasons and outcomes are inspectable. Public copy may mention clear
  reasons such as `no_route_for_model`, `confidence_below_threshold`,
  `workload_not_downgradeable`, and capability blocking, but should not expose
  internal implementation detail unnecessarily.
- Website copy must not promise a universal downgrade, exact monetary saving,
  or cross-provider routing outcome.

## Docs and pricing changes

The Docs quick start gains a routing evaluation step that uses the verified
read-only command:

```bash
cutctx routing status --proxy-url http://127.0.0.1:8787
```

The current install, initialization, agent wrap, and savings-report steps stay
intact. Pricing retains Builder, Team, Business, and Enterprise paths and the
exact existing PitchToShip billing URLs. Routing may be explained as an
opt-in capability but cannot be assigned to a public paid plan until entitlement
evidence is confirmed.

## Security and accessibility

- Preserve customer-environment processing, team-selected provider/egress, and
  customer-managed retention framing.
- Explain that capability and transport safety gates protect routing decisions;
  do not convert this into a formal compliance claim.
- Preserve skip links, semantic landmarks, focus visibility, reduced-motion
  behavior, mobile navigation state, and 44px+ touch targets.
- Every new page uses the same CSP-compatible, self-hosted assets and Evolve
  shell.

## Regression and production verification

1. Expand static-site tests for platform messaging, routing canonical/alias
   terms, new route availability, navigation, exact billing URLs, merchant
   disclosure, and prohibited claims.
2. Run responsive browser checks at mobile, tablet, laptop, and desktop
   widths. Verify navigation, links, overflow, touch targets, keyboard/focus,
   reduced motion, and console health.
3. Commit website-only changes to `main` using `github-personal`; retain
   unrelated working-tree changes.
4. Verify Cloudflare Pages production routes, exact PitchToShip targets, and
   the `www` → apex permanent redirect with path/query preservation.

## Deliberate exclusions

- No public “100+ providers” equivalence claim.
- No competitor-derived certification, retention, plan limit, or usage-pricing
  claim.
- No claim that every CutCtx deployment includes enterprise functionality.
- No external analytics collector, remote font, or external media dependency.
