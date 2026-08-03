---
id: CH-11
kind: chapter
title: Commercial Readiness Engineering Audit
purpose: Build and assess commercial product capabilities whose entitlement, metering, billing, privacy, support, and customer commitments are explicit, testable, and auditable.
audience: [Product engineers, platform engineers, finance engineers, security engineers, support leaders, engineering leaders]
scope: Packaging, entitlement, usage measurement, pricing configuration, billing handoffs, customer-facing commitments, support evidence, and commercial launch gates.
applicability: Subscription services, usage-priced APIs, enterprise platforms, marketplaces, trials, and internally billed shared services.
owners: [Commercial product owner, billing owner, service owner, security owner]
inputs: [product catalog, entitlement matrix, pricing decision, usage event schema, customer terms, support plan, launch evidence]
outputs: [commercial readiness decision, entitlement evidence register, billing reconciliation findings, launch gate]
dependencies: [NIST-SSDF-1.1, OWASP-ASVS-5.0.0, NIST-AI-RMF-1.0]
standards: [NIST-SSDF-1.1, OWASP-ASVS-5.0.0, NIST-AI-RMF-1.0]
---

# Commercial Readiness Engineering Audit

## Purpose, audience, scope, and applicability

Commercial readiness turns a feature into a supportable customer commitment. Audit whether a customer can buy, activate, use, change, be billed for, and receive support for the offered capability without hidden manual intervention or unauthorized access.

## Concepts and engineering principles

Keep the product catalog, entitlement decision, usage event, invoice line, and support case independently traceable through stable identifiers. Pricing is configuration with approval and effective dates, not an application constant. A commercial success signal must reconcile what the customer was allowed to use, what the service recorded, and what the billing system charged.

## Roles and accountability

The commercial product owner owns the offer and customer-facing promise. The billing owner owns pricing configuration, metering reconciliation, credits, and invoice evidence. The service owner owns enforcement. Security reviews privileged commercial actions and data access. Support owns escalation readiness; the release owner accepts residual launch risk.

## Prerequisites and required inputs

Collect the signed offer definition, package-to-entitlement matrix, tenant and identity model, pricing revisions, tax and currency assumptions, usage-event schema, billing integration contract, cancellation policy, support routing, privacy notices, and isolated test tenants.

## Standard operating procedure

1. Define each package, add-on, trial, quota, region, identity requirement, and effective date in a versioned catalog.
2. Prove entitlement is enforced at every service boundary, including background jobs, exports, APIs, and administrative paths.
3. Generate representative usage, upgrades, downgrades, cancellations, retries, credits, and failed-payment fixtures in isolated tenants.
4. Reconcile source usage events, aggregation results, invoice lines, and customer-visible usage with correlation IDs and a stated tolerance.
5. Test support and customer communications for quota exhaustion, payment failure, access removal, and disputed usage without exposing another tenant's data.
6. Review contract, privacy, availability, retention, and AI-use claims against implemented behavior and evidence.
7. Record exceptions with an owner, compensating control, customer impact, and expiry before launch.

## Worked example

[Product Atlas commercial readiness evidence](../examples/commercial-readiness/README.md) verifies a mid-cycle upgrade and overage credit without granting the old plan's export entitlement or creating a duplicate usage charge.

## Automation examples

```typescript
const decision = await authorizeFeature({ tenant: 'atlas-42', feature: 'export', catalogVersion: '2026.09.0' });
expect(decision).toEqual({ allowed: false, reason: 'plan-entitlement-missing' });
expect(await reconcileUsage('atlas-42', '2026-08')).toMatchObject({ delta: 0, currency: 'USD' });
```

## Audit prompts

Use [Opus](../prompts/opus/ch11-commercial-risk-assessment.md), [Sonnet](../prompts/sonnet/ch11-billing-evidence-review.md), and [Haiku](../prompts/haiku/ch11-offer-inventory.md) for cross-system launch risk, a bounded reconciliation review, and offer inventory normalization.

## Workflow checklist

Run [CL-COMM-01](../checklists/commercial-readiness.md) before launching or changing a package, entitlement, price, meter, billing connector, cancellation policy, or customer commitment.

## Evidence requirements and retention guidance

Retain catalog and price revision, entitlement verdict, sanitized usage event IDs, aggregation record, invoice reference, reconciliation result, customer communication template, approval, and exception expiry. Do not retain payment instrument data or customer content in routine audit evidence.

## Example findings with severity and remediation

**High — COMM-ATLAS-01.** A downgrade removed an API quota but a queued export job continued with premium access. Remediation: re-evaluate entitlement at execution, cancel or safely finish queued work by policy, notify the customer, and add an upgrade/downgrade regression fixture.

## KPIs and domain scorecard

The [commercial KPI catalog](../scorecards/commercial-kpis.md) measures entitlement-enforcement coverage and metering reconciliation completion. Revenue cannot compensate for an unauthorized feature grant or unexplained charge.

## Common failure patterns and diagnostic guidance

- A UI hides an option while an API or worker still permits it.
- Metering accepts duplicate retry events without a stable event key.
- A manual credit has no link to the incident, invoice, or approving owner.
- Customer terms promise retention or availability behavior that operations cannot evidence.

## Exit criteria

Exit when every offer has an accountable owner, effective version, enforced entitlement, reconciled metering path, tested lifecycle transitions, support route, customer-facing evidence, and an approved exception record where needed.

## Related runbooks, controls, examples, and templates

Use the commercial checklist, release-decision, evidence-register, audit-report, incident-review, and executive-summary templates. Escalate disputed charges or unauthorized access through the incident response process.
