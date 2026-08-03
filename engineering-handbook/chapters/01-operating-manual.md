---
id: CH-01
kind: chapter
title: Operating Manual for Engineering Audits
purpose: Run evidence-led engineering audits that lead to a reproducible decision.
audience: [Engineering managers, staff engineers, quality leads, security leads]
scope: Audit intake, execution, finding review, retest, and closure for a bounded product change.
applicability: Use for releases, material architecture changes, elevated-risk migrations, and recurring engineering health reviews.
owners: [Audit lead, accountable engineering owner]
inputs: [Approved audit brief, system inventory, risk hypotheses, evidence locations]
outputs: [Evidence register, finding register, decision record, retest record]
dependencies: [NIST-SSDF-1.1, OWASP-SAMM-2.1]
standards: [NIST-SSDF-1.1, OWASP-SAMM-2.1]
---

# Operating Manual for Engineering Audits

## Purpose, audience, scope, and applicability

An audit is a time-bounded decision process, not a search for defects. It makes
the release, investment, or remediation decision traceable to observed evidence.
The audit lead protects scope; the engineering owner supplies evidence and owns
remediation. Use this procedure when a decision has meaningful operational,
security, customer, or financial consequence.

## Concepts and engineering principles

Separate facts, inferences, and decisions. A test report is a fact; a claim that
it represents production risk is an inference; approving a release is a
decision. Evidence is useful only when its source, collection time, command,
environment, and integrity are known. Sampling is acceptable when the sampling
method and coverage limit are explicit.

## Roles and accountability

The audit lead defines the brief and adjudicates evidence quality. The accountable
engineering owner verifies system behavior and accepts remediation work. A domain
reviewer evaluates specialist risks without owning the decision. The release
authority accepts, delays, or rejects the release. A recorder maintains the
evidence and finding registers; this role may be combined with the audit lead
for small reviews.

## Prerequisites and required inputs

Before execution, obtain a change identifier, decision deadline, owner roster,
deployment environment, architecture or capability inventory, current test and
monitoring evidence, declared dependencies, and known exceptions. Do not begin
with a vague request such as “check quality.” Convert it into observable
questions: which user journey, API contract, data path, or failure mode matters?

## Standard operating procedure

1. Write an audit brief with decision, scope boundaries, risk hypotheses,
   required evidence, owners, and exit criteria.
2. Inventory capabilities and map each to a verification method. Mark unknown
   capability paths as a finding, not as an assumed pass.
3. Rank risks by customer impact, exploitability, reversibility, and detection
   latency. Start with items that could block a decision.
4. Collect immutable or reproducible evidence. Store commands, source revision,
   fixture version, timestamps, and relevant output.
5. Reproduce each candidate finding independently when practical. Record the
   smallest reliable reproduction, affected scope, and a safe remediation.
6. Hold a finding review. Classify severity, owner, due date, exception status,
   and release implication. Resolve disagreement in the decision record.
7. Verify remediation with fresh evidence; never close an issue merely because a
   code review says it was changed.
8. Publish a closure packet: decision, residual risk, approved exceptions,
   evidence locations, retest results, and follow-up date.

## Worked example

The linked [API release audit example](../examples/audit-release/README.md)
reviews Atlas Billing API release `2026.4.0`. It demonstrates an authorization
regression, its evidence packet, an Important finding, and the negative test
that proves remediation.

## Automation examples

Use read-only, deterministic commands first. For an API release, run the
contract suite, authorization matrix, migration validation query, dependency
inventory, and synthetic critical-path test from a clean fixture. Capture the
exact revision and command:

```shell
rtk pytest tests/contracts tests/security -q
rtk proxy python3 scripts/verify_release_evidence.py --release 2026.4.0
```

Treat an unavailable command, missing fixture, or credential requirement as
blocked evidence. Do not substitute a green dashboard screenshot for a failed
or unavailable reproducible check.

## Audit prompts

Use the linked [Opus](../prompts/opus/ch01-audit-architecture.md),
[Sonnet](../prompts/sonnet/ch01-evidence-review.md), and
[Haiku](../prompts/haiku/ch01-evidence-normalization.md) prompts. Their work is
intentionally different: cross-system risk synthesis, focused reproduction
review, and mechanical evidence normalization.

## Workflow checklist

Run [CL-AUDIT-01](../checklists/audit-execution.md) at intake, finding review,
and closure. Each control defines its evidence, owner, frequency, and failure
action rather than relying on a generic checkbox.

## Evidence requirements and retention guidance

Retain the brief, inventory, command logs, reports, query output, finding
register, exception decisions, and retest evidence through the next material
release or the organization’s stated retention period, whichever is longer.
Redact customer data and secrets before attaching artifacts. Preserve hashes or
immutable CI URLs for edited reports.

## Example findings with severity and remediation

**Important — AUTHZ-ATLAS-02.** A tenant-scoped invoice endpoint returned a
valid invoice to a session from another tenant. Evidence: a deterministic
contract test at revision `7af1e22`. Remediation: enforce tenant scope in the
repository query, add a regression test for an unauthorized tenant, and rerun
the authorization matrix. Release disposition: hold until retest is clean.

## KPIs and domain scorecard

The [audit KPI catalog](../scorecards/audit-operations-kpis.md) measures audit
coverage, evidence freshness, finding escape rate, retest latency, and exception
age. A high completion percentage is not success when high-risk capabilities
remain unknown; the scorecard therefore gates on uncovered critical paths.

## Common failure patterns and diagnostic guidance

- Scope expands after evidence collection. Freeze the original decision and
  open a separate audit brief for newly discovered work.
- A report cites a test name but not output or revision. Re-run it and record
  the reproducible command.
- Severity is debated as a label. Revisit customer impact, exposure, and
  available containment instead of negotiating labels.
- A release exception has no expiry. It is incomplete; name an owner, expiry,
  compensating control, and retest trigger.

## Exit criteria

The audit exits only when the decision owner has a complete closure packet,
all blocking findings are remediated or explicitly accepted through the
exception process, evidence is reproducible or its limitation is declared, and
the follow-up owner/date is recorded.

## Related runbooks, controls, examples, and templates

Use the audit report, evidence register, finding record, and release-decision
templates. Related assets will connect release, rollback, and incident runbooks
as those operational volumes are authored.
