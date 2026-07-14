# Product Manager Audit: Cutctx

**Date:** 2026-07-14  
**Scope:** Current repository state, user-facing documentation, CLI onboarding,
billing-operational documentation, and deployment artifacts. This is a codebase
audit, not evidence that hosted services or legal/compliance claims are live.

## Executive summary

Cutctx has a differentiated, technically mature core: local-first reversible
context compression, broad agent/proxy support, cross-agent memory, and strong
operator controls. Since the previous product audit, several formerly reported
documentation and platform gaps are now addressed: a unified `cutctx setup`
command exists, a troubleshooting guide exists, direct Stripe Checkout/Portal
helpers are documented, and Kubernetes backup assets are present.

The main user-facing gap is now **truthful onboarding completion**. The setup
command presents a success heading even when it cannot start a healthy proxy,
and it does not give an actionable next step for all partial setup outcomes.
This undermines time-to-value at the first moment that matters. It is the
highest-confidence in-repository remediation.

**Recommendation:** Address onboarding completion before expanding the setup
surface. Keep commercial-readiness claims conditional until a real Stripe
test-mode lifecycle and legal/compliance work are independently verified.

## Product today

| Area | Evidence | Assessment |
|---|---|---|
| Core value | `README.md`, compression pipeline, CCR, agent wrappers | Strong, differentiated value proposition. |
| Onboarding | `cutctx/cli/setup.py`, `cutctx wrap`, installation and quickstart docs | Improved, but completion state is misleading on failure. |
| Support | `docs/content/docs/troubleshooting.mdx` | Common setup failures have documented remedies. |
| Billing architecture | `docs/BILLING_INTEGRATION.md` | Direct Stripe paths are implemented/documented; live readiness remains unverified. |
| Operations | `k8s/backup-cronjob.yaml`, `k8s/README.md`, health endpoints | Good foundation; recovery guidance remains fragmented. |
| Enterprise controls | RBAC, audit, SSO/SCIM, retention modules and docs | Strong product foundation, subject to distribution and deployment verification. |

## User journey assessment

### 1. Discover and evaluate

**What works**

- The README quickly explains the proxy, wrapper, library, MCP, and memory
  value paths.
- Product positioning is specific: local-first processing and reversible
  retrieval distinguish Cutctx from gateway-only alternatives.

**Friction**

- The primary README quickstart starts with a manual mode choice (`wrap`,
  `proxy`, or global routing), while a unified setup command exists but is not
  the primary call to action.
- A new user can still be unsure which route is appropriate for an agent versus
  an SDK integration.

### 2. First value / onboarding

**What works**

- `cutctx setup` checks installation, detects common agents, attempts supported
  MCP registration, starts a local proxy, and performs a health check.
- Troubleshooting documentation provides concrete proxy and wrapper remedies.

**Gap P0 — misleading completion state**

`cutctx/cli/setup.py` prints **“Setup Complete!”** even when proxy startup or
the final health check fails. The output does show `Not running`, but the
headline contradicts the state and does not distinguish a complete setup from
a partial configuration. A first-time user can reasonably stop there without
ever reaching a working compressed request.

**Remediation completed — 2026-07-14**

- The final status is now explicit: only a healthy final proxy check produces
  `Setup Complete!`; a failed requested startup produces `Setup needs attention`.
- Unhealthy outcomes print an exact port-specific recovery command and the
  troubleshooting documentation URL.
- Requested startup now exits non-zero when the final health check fails;
  deliberate `--no-start` usage remains successful and is labelled as skipped.
- CLI regression tests cover healthy startup, an already-running proxy, failed
  startup, deliberate no-start, and the README entry point.

### 3. Operate and retain

**What works**

- Health, metrics, dashboard, budget, firewall, and outbound webhook surfaces
  offer a credible operations baseline.
- Kubernetes backup automation exists and includes several persisted stores.

**Gap P1 — recovery story is fragmented**

Backup assets, a draft disaster-recovery spec, and a Kubernetes readme exist,
but there is no single customer-facing backup/restore runbook that defines the
authoritative stores, verification procedure, RPO/RTO assumptions, and restore
ownership. This creates avoidable renewal and security-review friction.

**Recommended remediation**

Publish one operator runbook after confirming the supported storage topology.
This should not be claimed complete from static code inspection alone.

## Competitive view

| Dimension | Cutctx advantage | Remaining exposure |
|---|---|---|
| Context efficiency | Specialized compression with CCR retrieval | Competitors can offer simpler hosted onboarding. |
| Privacy | Local-first and air-gap support | Buyers still need clear recovery and support documentation. |
| Agent workflows | Broad wrapper and proxy support | First-run complexity weakens the “one command” message. |
| Commercial conversion | Stripe helper paths and enterprise webhook support | Customer-facing Checkout, Portal, and webhook lifecycle are not verified in this audit. |

## Prioritized gap register

| Priority | Gap | User/business impact | Status |
|---|---|---|---|
| Resolved P0 | Setup reported completion despite failed proxy startup | Users could churn before first successful compression; automation could not reliably detect failure | Fixed and regression-tested on 2026-07-14 |
| P1 | Unified setup is not the README’s primary entry point | Avoidable decision paralysis for new users | Documentation follow-up recommended with P0 |
| P1 | Backup/restore guidance is fragmented | Enterprise security and renewal friction | Requires validated operational ownership |
| P1 | Hosted billing is documented as transitional | Cannot claim self-serve conversion readiness without live Stripe verification | Requires authorized external verification |
| P2 | Product analytics for onboarding completion | Hard to quantify activation/drop-off | Requires a privacy-reviewed telemetry decision |
| P2 | Legal/compliance readiness | Enterprise procurement constraint | Requires counsel and external assurance, not code-only work |

## Success measures

- `cutctx setup` exits `0` only when the requested end state is healthy.
- Users with a failed setup receive an exact next command and support route.
- README’s first-run path reflects the supported unified setup journey.
- Track install-to-first-healthy-proxy and first-successful-compression rates
  only after privacy and consent requirements are defined.

## Scope boundaries

This audit does not certify Stripe, legal terms, SOC 2, disaster recovery, or
production deployment readiness. Those outcomes require live credentials,
operational owners, and/or external review. The identified onboarding defect is
fully observable and remediable within this repository.
