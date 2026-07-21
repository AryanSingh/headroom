# CutCtx commercialization report

**Date:** 2026-07-21

## Recommendation

Use `cutctx.com` as the conversion surface and retain PitchToShip as the
merchant of record, checkout authority, license issuer, and account portal.
This is the shortest route to a focused product narrative without duplicating
payments, tax handling, entitlement logic, or support-account infrastructure.

## Offer architecture

| Audience | Offer | Proof needed | Conversion route |
| --- | --- | --- | --- |
| Engineer/evaluator | Free Builder | Local install and savings visibility | Docs/install |
| Engineering team | Team | Savings reporting and policy/budget controls | PitchToShip checkout |
| Platform organization | Business | Multi-project reporting and deployment support | PitchToShip checkout or sales |
| Regulated/procurement buyer | Enterprise | Local-first posture, identity/governance, review packet | Sales conversation |

The public price architecture remains Builder ($0), Team ($1,500/month or
$18,000/year), Business ($3,500/month or $42,000/year), and Enterprise
custom, subject to owner confirmation before publication. Annual contracts are
the default for paid tiers; do not publish a monthly price that conflicts with
the final PitchToShip catalogue.

## Value metric

The primary value metric is measurable token/context savings on customer
traffic. Supporting value comes from effective-context utility, fewer retries,
and governance/procurement controls. Sales and product copy should avoid a
guaranteed percentage; direct buyers to their own CutCtx savings reports.

## Immediate upsell and retention loop

1. The user installs or wraps an existing coding-agent workflow.
2. The product exposes savings telemetry and a report.
3. A team upgrades for shared visibility, policies, and budget controls.
4. A larger organization upgrades when reporting, identity, audit, retention,
   fleet, and deployment requirements arise.

Optional paid services remain onboarding, deployment hardening, premium SLA,
security review support, and custom integrations. These should be offered as
explicit add-ons rather than folded into the base subscription.

## Commercial risk controls

- Keep merchant identity, card descriptor, invoice identity, refund policy,
  checkout, and legal pages mutually consistent.
- Do not market formal security certifications or complete enterprise UI
  coverage that does not exist.
- Correct draft legal materials before publication and obtain qualified advice
  for jurisdiction, tax, and enforceability questions.
- Do not add third-party analytics that undermine the local-first privacy
  positioning.
