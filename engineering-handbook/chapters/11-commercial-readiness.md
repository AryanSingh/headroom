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

The audit is a launch gate, not a finance sign-off. Product engineers prove the offer is enforceable, platform engineers prove it is measurable, finance engineers prove it is billable, security proves privileged commercial actions and customer data are protected, and support leaders prove escalation and communication work before any customer depends on them. The gate applies to the first launch of an offer and to every later change that alters what customers are promised, charged, or allowed to do: new packages, add-ons, trials, quotas, regions, price revisions, meter definitions, billing connectors, cancellation policies, and support plans. A change that looks internal, such as a billing-integration refactor or a metering-pipeline migration, still requires the audit because the evidence trail, not the code, is what makes the commercial commitment safe.

## Concepts and engineering principles

Keep the product catalog, entitlement decision, usage event, invoice line, and support case independently traceable through stable identifiers. Pricing is configuration with approval and effective dates, not an application constant. A commercial success signal must reconcile what the customer was allowed to use, what the service recorded, and what the billing system charged.

Three pipeline invariants shape every audit step. First, **entitlement is enforced at execution time**, not at display time: the UI may show a capability while a background job, export worker, or administrative API still permits it, so every executable boundary must evaluate the same effective entitlement decision. Second, **usage is metered from idempotent events**: each accepted event carries a stable key, retries produce no duplicate charge, and aggregation preserves the event-to-invoice lineage. Third, **every commercial change is effective-dated and approved**: the catalog records when a price, package, or quota becomes active, who approved it, and which customers it applies to, so a mid-cycle upgrade produces one coherent invoice rather than a blend of catalog snapshots.

## Roles and accountability

The commercial product owner owns the offer and customer-facing promise. The billing owner owns pricing configuration, metering reconciliation, credits, and invoice evidence. The service owner owns enforcement. Security reviews privileged commercial actions and data access. Support owns escalation readiness; the release owner accepts residual launch risk.

| Role | Owns | Approves | Accountable for |
| --- | --- | --- | --- |
| Commercial product owner | Offer definition, package-to-entitlement matrix, customer-facing claims | Launch decision, exception records, claim register | That the promise is true, enforceable, and communicated |
| Billing owner | Pricing configuration, meter definitions, invoice evidence, credits | Price revisions, adjustment approvals, reconciliation tolerance | That charges reconcile to approved source events |
| Service owner | Enforcement at execution boundaries, usage-event schema | Enforcement-fixture results, quota behavior | That revoked access cannot complete work |
| Security owner | Privileged-action review, tenant isolation, privacy evidence | Sensitive commercial actions | That no customer data crosses offer boundaries |
| Support lead | Escalation routes, communication templates, dispute handling | Support readiness statement | That customers can act on quota, payment, and removal events |
| Release owner | Launch gate, residual risk acceptance | Final commercial readiness decision | That exceptions have owners, controls, and expiry |

## Prerequisites and required inputs

Collect the signed offer definition, package-to-entitlement matrix, tenant and identity model, pricing revisions, tax and currency assumptions, usage-event schema, billing integration contract, cancellation policy, support routing, privacy notices, and isolated test tenants.

Before the audit starts, confirm the inputs are current and versioned. A stale catalog revision or a pricing spreadsheet that is not the system of record invalidates every downstream result. The usage-event schema must include the stable event key, tenant and account identifiers, the catalog version in force, timestamps, and the unit being metered. The billing integration contract must name the invoice line format, the currency and rounding rule, the failure and retry behavior, and the reconciliation endpoint. For offers with AI features, collect the AI-use claim and the evidence that supports it (for example, model behavior tests, evaluation results, or human-review records) so the commercial promise does not exceed implemented behavior.

## Standard operating procedure

1. **Define the offer in a versioned catalog.** Record each package, add-on, trial, quota, region, identity requirement, price, and effective date, with an owner and an approval reference. Timeline: complete before any customer-visible change is scheduled. Owner: commercial product owner.
2. **Classify launch risk.** Rate the change by revenue impact, customer-visible behavior change, enforcement complexity, and billing-integration risk. High-risk changes (new meter, new pricing model, entitlement-model refactor) require the full evidence package below; low-risk changes (label updates, region additions with identical terms) can use a reduced gate. Record the classification and its rationale.
3. **Prove enforcement at every boundary.** Test UI, API, worker, export, background job, and administrative paths for grant, deny, upgrade, downgrade, cancellation, trial expiry, and quota exhaustion transitions. Owner: service owner. Threshold: zero post-revocation executions and zero cross-plan grants in the fixture run.
4. **Generate representative lifecycle fixtures.** Create isolated tenants that exercise upgrades, downgrades, cancellations, retries, credits, failed payments, and quota changes against the exact catalog revision being released.
5. **Reconcile the commercial pipeline.** Match source usage events to aggregation results, invoice lines, and customer-visible usage using correlation IDs, with the reconciliation tolerance stated and approved before the run. Owner: billing owner. Threshold: zero unexplained events and zero unapproved adjustments.
6. **Test support and customer communications.** Exercise quota-exhaustion, payment-failure, access-removal, and disputed-usage messaging without exposing another tenant's data. Confirm routing, language, and remediation instructions are correct for each audience.
7. **Review commitments against behavior.** Map every contract, privacy, availability, retention, and AI-use claim to implemented, evidenced behavior in the claim register. Any claim without evidence is a finding, not a wish.
8. **Record exceptions with owners and expiry.** Every residual risk gets a named owner, a compensating control, the customer impact, and a review date. An exception without an expiry is an open commitment that must be tracked.
9. **Issue the readiness decision.** The release owner signs the launch gate only when enforcement, reconciliation, communications, and claim evidence are complete and every exception is bounded. Record the decision, the evidence package reference, and the residual-risk statement.

### Launch decision table

| Risk class | Trigger | Required evidence | Approvals | Timeline from freeze to gate |
| --- | --- | --- | --- | --- |
| Low | Label, region-with-identical-terms, internal tooling change | Catalog revision, smoke enforcement fixture | Commercial product owner | 1–3 business days |
| Standard | New package, price revision, quota change, support-plan change | Full catalog, enforcement fixtures, reconciliation, communications, claim review | Commercial product owner, billing owner, support lead | 1–2 weeks |
| High | New meter, new pricing model, entitlement refactor, billing-platform migration | Standard evidence plus billing-integration tests, financial sign-off, privacy review, exception plan | All owners plus security owner and finance | 2–6 weeks, staged with a pilot customer cohort |

## Worked example

[Product Atlas commercial readiness evidence](../examples/commercial-readiness/README.md) verifies a mid-cycle upgrade and overage credit without granting the old plan's export entitlement or creating a duplicate usage charge.

Walk through the expected evidence sequence. The customer upgrades from the Standard plan to the Pro plan on day 12 of a monthly cycle. First, the catalog revision records the Pro price, the effective date, and the approved upgrade rule; the entitlement system issues a new decision for tenant `atlas-42` that grants Pro quotas while the old plan's export entitlement remains absent until the export add-on is purchased. Second, the metering pipeline receives the upgrade event with a stable event key, aggregates usage before and after the effective date under the correct catalog snapshots, and the invoice builder produces a prorated charge for the upgrade plus a separate overage credit for usage that exceeded the Standard quota before the upgrade. Third, the reconciliation job joins the source events, the aggregation record, the invoice lines, and the credit register and reports a zero delta against the approved tolerance. Fourth, the support fixture confirms that the customer's usage view shows the same numbers as the invoice and that the export button remains disabled with a purchase prompt. Each step leaves an evidence record: catalog revision, entitlement verdict, event IDs, aggregation and invoice references, reconciliation result, and communication template. If any step diverges, the finding is attached to the step, not deferred to post-launch.

## Automation examples

```typescript
const decision = await authorizeFeature({ tenant: 'atlas-42', feature: 'export', catalogVersion: '2026.09.0' });
expect(decision).toEqual({ allowed: false, reason: 'plan-entitlement-missing' });
expect(await reconcileUsage('atlas-42', '2026-08')).toMatchObject({ delta: 0, currency: 'USD' });
```

Automation should cover the boundaries humans miss: background export workers, administrative impersonation paths, retry delivery, and mid-cycle catalog changes. For every lifecycle transition, run a fixture that starts from a declared catalog revision and asserts the entitlement decision, the metering outcome, and the invoice line together, so a change that breaks one pipeline stage fails the whole transition.

## Audit prompts

Use [Opus](../prompts/opus/ch11-commercial-risk-assessment.md), [Sonnet](../prompts/sonnet/ch11-billing-evidence-review.md), and [Haiku](../prompts/haiku/ch11-offer-inventory.md) for cross-system launch risk, a bounded reconciliation review, and offer inventory normalization.

Run the Opus prompt when the audit spans catalog, metering, billing, and support systems and you need a consolidated risk statement. Run the Sonnet prompt on a single evidence package, such as one customer's reconciliation result, to check whether the evidence supports the claimed outcome. Run the Haiku prompt to normalize an offer inventory from inconsistent sources before the audit begins. Treat model output as a hypothesis: every risk it raises must be traceable to a fixture result or evidence record before it becomes a finding.

## Workflow checklist

Run [CL-COMM-01](../checklists/commercial-readiness.md) before launching or changing a package, entitlement, price, meter, billing connector, cancellation policy, or customer commitment.

The checklist controls `ENG-COMM-001` through `ENG-COMM-005` are ordered so the offer definition is verified before enforcement, enforcement before billing, billing before communications, and communications before the launch gate. `ENG-COMM-003` (claim register) and `ENG-COMM-004` (entitlement-to-billing match) are the two controls most often skipped on "small" changes; run them even for label-only releases because a claim or a price can change without a feature change.

## Evidence requirements and retention guidance

Retain catalog and price revision, entitlement verdict, sanitized usage event IDs, aggregation record, invoice reference, reconciliation result, customer communication template, approval, and exception expiry. Do not retain payment instrument data or customer content in routine audit evidence.

| Evidence | What to record | Retention | Owner |
| --- | --- | --- | --- |
| Catalog and price revisions | Effective date, approval, affected offers, diff against prior revision | Life of offer plus two years | Commercial product owner |
| Entitlement verdicts | Tenant, feature, catalog version, decision, reason, timestamp | Billing audit horizon (at least two years) | Service owner |
| Usage and aggregation records | Event keys, unit counts, catalog snapshot, aggregation run ID | Statutory billing retention; reference-only | Billing owner |
| Invoice and credit references | Invoice number, line IDs, credit register entry, reconciliation delta | Statutory billing retention | Billing owner |
| Customer communications | Template version, recipient rule, send evidence, incident linkage | Two years or per contract | Support lead |
| Exceptions | Owner, compensating control, customer impact, expiry, review record | Until expiry plus one year | Release owner |

Payment instrument data, full card numbers, customer content, and unrestricted production logs never enter the audit evidence set; retain references and hashes instead. If a dispute requires an exception to that rule, it goes through the incident response process, not the routine evidence store.

## Example findings with severity and remediation

**High — COMM-ATLAS-01.** A downgrade removed an API quota but a queued export job continued with premium access. Remediation: re-evaluate entitlement at execution, cancel or safely finish queued work by policy, notify the customer, and add an upgrade/downgrade regression fixture.

**High — COMM-ATLAS-02.** A mid-cycle price change was applied to all accounts because the catalog revision lacked an effective-date filter, so existing customers were invoiced at the new price. Remediation: make effective dates mandatory in the catalog schema, snapshot the catalog per invoice cycle, and add a fixture that invoices the same account under two consecutive revisions.

**Medium — COMM-ATLAS-03.** The support template for quota exhaustion described a limit that the catalog had not shipped, so a customer was told they could purchase a quota that did not exist. Remediation: generate communication templates from the catalog rather than hand-written copy, and gate template publication on the claim register review.

## KPIs and domain scorecard

The [commercial KPI catalog](../scorecards/commercial-kpis.md) measures entitlement-enforcement coverage and metering reconciliation completion. Revenue cannot compensate for an unauthorized feature grant or unexplained charge. Review `KPI-COMM-001` and `KPI-COMM-002` at every launch gate and monthly close, and `KPI-COMM-003` (entitlement-to-billing match) whenever pricing or packaging changes, because an invoice that contradicts the entitlement grant fails even when revenue is unchanged.

## Common failure patterns and diagnostic guidance

- A UI hides an option while an API or worker still permits it.
- Metering accepts duplicate retry events without a stable event key.
- A manual credit has no link to the incident, invoice, or approving owner.
- Customer terms promise retention or availability behavior that operations cannot evidence.

| Symptom | Likely cause | Check | Fix |
| --- | --- | --- | --- |
| UI shows capability, background job runs with it | Entitlement evaluated at display time, not execution time | Review worker and export code paths for a second authorization call | Evaluate entitlement at execution; cancel queued work by policy; add boundary fixtures |
| Double charge after a retry | Retry lacks an idempotency key | Inspect event schema and delivery semantics for stable key | Persist first-write result keyed by event ID; deduplicate before aggregation |
| Credit appears with no approver | Manual credit path bypasses approval | Trace credit register entries to incident and invoice records | Require approval link; block unapproved adjustments |
| Terms promise behavior evidence cannot show | Claim written without an implementation owner | Diff claims against claim register and test evidence | Add claim-to-evidence mapping; block launch on unproven claims |
| Mid-cycle change hits all customers | Missing effective-date scoping | Check catalog revision filters and invoice snapshot logic | Mandate effective dates; snapshot catalog per cycle; add regression fixture |

## Exit criteria

Exit when every offer has an accountable owner, effective version, enforced entitlement, reconciled metering path, tested lifecycle transitions, support route, customer-facing evidence, and an approved exception record where needed.

| Criterion | Evidence | Passes when |
| --- | --- | --- |
| Offer defined | Catalog revision with effective date and approval | Every offer, add-on, trial, and quota is versioned and owned |
| Entitlement enforced | Boundary fixture results | Zero grants after revocation; zero cross-plan access |
| Metering reconciled | Reconciliation report | Delta within approved tolerance; all adjustments approved |
| Lifecycle tested | Transition fixture record | Upgrade, downgrade, cancel, retry, credit, and payment-failure paths pass |
| Support ready | Escalation and communication evidence | Correct routing and safe, accurate messaging |
| Claims evidenced | Claim register | Every customer-facing claim maps to implemented behavior |
| Exceptions bounded | Exception records | Each has owner, compensating control, impact, and expiry |

## Related runbooks, controls, examples, and templates

Use the commercial checklist, release-decision, evidence-register, audit-report, incident-review, and executive-summary templates. Escalate disputed charges or unauthorized access through the incident response process.

> **Application note — Cutctx.** For a token-compression proxy product, the commercial pipeline meters model and token usage rather than feature quotas, so the entitlement decision must carry the routing preset in force and the meter must record the model, token count, and preset version per request. The claim register then evidences statements such as "lossless compression" against the measured per-engine behavior in `docs/handoff-2026-07-28.md`; a claim that an engine compresses losslessly while the shipped default routes elsewhere fails the same way as an unshipped support quota. Effective-dated catalog revisions apply to pricing-model and preset-version changes alike.
