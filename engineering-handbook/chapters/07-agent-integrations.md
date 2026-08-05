---
id: CH-07
kind: chapter
title: Agent and Integration Engineering Audit
purpose: Build and assess integrations and agent tool interfaces with explicit authority, bounded execution, traceable data flow, and recovery.
audience: [Integration engineers, agent-tool builders, platform engineers, security engineers, QA]
scope: OAuth and service identity, webhooks, tool contracts, callback validation, retries, secrets, human approval, and auditability.
applicability: SaaS integrations, MCP tools, plugins, automations, and AI-agent action surfaces.
owners: [Integration owner, security owner, product owner]
inputs: [integration inventory, scopes, tool schemas, webhook contracts, data-flow map]
outputs: [authority map, callback evidence, integration findings, release gate]
dependencies: [OWASP-ASVS-5.0.0, OWASP-API-TOP10-2023, NIST-SSDF-1.1]
standards: [OWASP-ASVS-5.0.0, OWASP-API-TOP10-2023, NIST-SSDF-1.1]
---

# Agent and Integration Engineering Audit

## Purpose, audience, scope, and applicability

An integration grants another system a pathway into product data or actions. An agent tool makes that pathway available to probabilistic planning. Audit authority, data flow, replay behavior, and approval boundaries—not merely whether the happy-path handshake works.

## Concepts and engineering principles

Use least-privilege scopes, short-lived credentials, verified callback signatures, and explicit tool schemas. Separate suggestion from execution for irreversible or high-impact actions. Treat tool output and external content as untrusted input; an agent must not convert instructions in retrieved content into authority it was never granted.

## Roles and accountability

The integration owner owns contracts and consumer communication. Security owns scope review, secret handling, and callback verification. Product owns approval policy and user disclosure. The service owner owns retry and failure recovery; the incident lead coordinates credential revocation when a connector is abused.

## Prerequisites and required inputs

Gather providers, owners, client registrations, scopes, secrets location, callback URLs, webhook signing schemes, tool input/output schemas, data classification, retention, rate limits, retry policies, approval rules, and offboarding procedures. Create isolated provider or local fake fixtures.

## Standard operating procedure

1. Inventory every inbound and outbound integration, tool, scope, action, data class, owner, and disable switch.
2. Verify OAuth state, redirect URI exactness, token audience, scope minimization, rotation, revocation, and tenant binding.
3. Send valid, unsigned, stale, malformed, duplicated, and out-of-order webhooks.
4. Test tool schemas for required fields, output redaction, authority boundaries, confirmation requirements, and safe behavior on ambiguous requests.
5. Prove retries and dead-letter paths do not duplicate downstream action.
6. Exercise provider outage, expired token, revoked consent, and rate-limit paths.
7. Retain an audit record that links actor, tool/integration, authority, input class, approval, result, and correlation ID without persisting secrets.

## Worked example

[Product Atlas agent integration evidence](../examples/agent-integration/README.md) shows an expense-export tool that may prepare a CSV preview but needs explicit finance approval before delivery. Its webhook fixture rejects an altered body and a replayed event ID.

## Automation examples

```typescript
const rejected = await request.post('/webhooks/atlas-expense', { headers: { 'x-atlas-signature': 'sha256=not-valid' }, data: { event_id: 'evt-8', kind: 'expense.approved' } });
expect(rejected.status()).toBe(401);
expect(await audit.hasEvent('expense.approved', 'evt-8')).toBe(false);
```

## Audit prompts

Use [Opus](../prompts/opus/ch07-integration-authority-map.md), [Sonnet](../prompts/sonnet/ch07-webhook-evidence-review.md), and [Haiku](../prompts/haiku/ch07-integration-inventory.md) for authority mapping, callback evidence review, and compact inventory normalization.

## Workflow checklist

Run [CL-INT-01](../checklists/agent-integrations.md) before enabling a provider, changing a scope, publishing a tool, or changing a callback endpoint.

## Evidence requirements and retention guidance

Retain approved scope evidence, sanitized callback requests, signature verdict, event ID, provider/account fixture, token metadata excluding secret material, tool schema version, approval record, correlation ID, and source revision.

## Example findings with severity and remediation

**Critical — INT-ATLAS-01.** An expense webhook accepted a valid signature from the production tenant after a sandbox event ID collision. Remediation: bind signature verification and event deduplication to provider environment and tenant, purge collision-prone entries, and add isolated environment fixtures.

## KPIs and domain scorecard

The [integration KPI catalog](../scorecards/integration-kpis.md) tracks scope review coverage, signature-verification coverage, duplicate-action prevention, and approval-policy adherence. Any unapproved high-impact action is a release blocker regardless of the monthly percentage.

## Common failure patterns and diagnostic guidance

- A broad OAuth scope is retained after an endpoint needs only read access.
- Signature verification checks a parsed body, not the original signed bytes.
- A tool executes an external instruction without a user-owned confirmation.
- Retries queue indefinitely after consent revocation without a clear operator path.

## Exit criteria

Exit when every integration has an owner and disable route, authorization and callback evidence are current, privileged agent actions require the approved confirmation policy, retries are idempotent, and secrets are revocable.

## Related runbooks, controls, examples, and templates

Use the integration checklist, incident-review, threat-model, and release-decision templates. Coordinate with the incident response runbook for token revocation, provider disablement, and external notification.
