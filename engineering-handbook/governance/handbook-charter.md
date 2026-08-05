# Engineering Handbook Charter

## Purpose

This charter defines the decision rights, maintenance practice, and evidence expectations for a reusable engineering handbook. It supports product teams that need repeatable assurance without treating one product architecture as universal.

## Scope

The handbook covers product delivery, security, reliability, data change, AI evaluation, release decisions, and incident learning. Product owners adapt a workflow to their risk profile, contractual duties, and operating context. Legal, privacy, and regulatory obligations remain with the organization that operates the product.

## Operating principles

- Treat source records, test output, review decisions, and approvals as evidence; summarize them without replacing them.
- Assign accountability to roles. Name an individual only in the instance record that uses the role.
- Prefer reversible delivery steps and explicit decision gates for high-impact change.
- Record uncertainty, assumptions, and exceptions where reviewers can inspect them.
- Review controls after material incidents, architecture changes, or changes to the standards register.

## Decision rights

| Decision | Accountable role | Consulted roles | Record |
| --- | --- | --- | --- |
| Publish a handbook edition | Engineering Enablement Lead | Security, SRE, Product, Accessibility | edition decision log |
| Approve a product-tailored workflow | Engineering Manager | Security Lead, Product Manager | workflow adoption record |
| Accept a time-bounded exception | Named risk owner | Control owner, Security or Reliability lead | exception record |
| Approve release readiness | Release Manager | Service owner, QA lead, SRE | release decision |
| Retire a control | Control owner | Handbook steward, affected teams | control change record |

## Maintenance cycle

1. The handbook steward collects proposed changes with a rationale, affected assets, and evidence of use.
2. Domain owners review technical accuracy and identify related controls, templates, and examples.
3. The steward runs source validation and publication checks, then records unresolved findings.
4. The accountable publisher approves, defers, or rejects the edition decision.
5. Teams receive a concise change note that states applicability and any migration date.

## Product Atlas example

Product Atlas operates a B2B inventory-planning service. Its Engineering Enablement Lead published edition 2026.1 after the Security Lead reviewed its threat-model and incident-review templates. The release decision recorded the 30-day adoption window for the new AI evaluation report. The service teams retained local ownership of their release evidence and linked it from their internal work trackers.

## Review signals

Track edition adoption, overdue exceptions, validation findings by asset type, and time from a material incident to handbook update. Investigate low adoption before adding controls; the workflow may not fit the product context.
