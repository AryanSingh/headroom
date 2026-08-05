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

Depth should match consequence. A change with no meaningful consequence does not
need this procedure; run a lighter review and record that decision so the
boundary is explicit. The table below sets a starting depth; the audit lead
adjusts it in the brief and records the reason.

| Change type | Audit depth | Decision owner | Typical duration |
| --- | --- | --- | --- |
| Release of a critical customer journey or payment path | Full audit | Release authority | 3–5 business days |
| Material architecture change | Full audit | Accountable engineering owner | 5–10 business days |
| Elevated-risk migration | Targeted audit | Service owner | 2–5 business days |
| Recurring engineering health review | Health review | Engineering manager | 1–2 business days |

## Concepts and engineering principles

Separate facts, inferences, and decisions. A test report is a fact; a claim that
it represents production risk is an inference; approving a release is a
decision. Evidence is useful only when its source, collection time, command,
environment, and integrity are known. Sampling is acceptable when the sampling
method and coverage limit are explicit.

Rate the strength of each evidence item on the E0–E4 scale below and record the
level in the register. A higher level is not automatically sufficient; the item
must still answer the question it is attached to.

| Level | Meaning | Example |
| --- | --- | --- |
| E0 | No evidence collected | “The team believes the retry path is safe.” |
| E1 | Declarative evidence | A code-review approval or a list of test names without output |
| E2 | Reproducible artifact | Command, source revision, fixture, and captured output |
| E3 | Independent reproduction | A second reviewer re-runs the command on the recorded fixture |
| E4 | Continuous, deterministic verification | A CI contract suite that gates the exact release revision |

Severity vocabulary follows the risk-severity model in governance: Critical,
High, Medium, and Low, each with an impact-and-likelihood signal, an initial
handling target, and a decision owner. Use the governance table, not negotiated
labels, when classifying a finding.

## Roles and accountability

The audit lead defines the brief and adjudicates evidence quality. The accountable
engineering owner verifies system behavior and accepts remediation work. A domain
reviewer evaluates specialist risks without owning the decision. The release
authority accepts, delays, or rejects the release. A recorder maintains the
evidence and finding registers; this role may be combined with the audit lead
for small reviews.

| Role | Decision authority | Responsibility | Escalates to |
| --- | --- | --- | --- |
| Audit lead | Evidence quality and scope | Brief, evidence adjudication, reproduction | Decision owner on scope disputes |
| Accountable engineering owner | Remediation acceptance | Evidence supply, remediation, retest | Release authority for release impact |
| Domain reviewer | Specialist assessment only | Risk evaluation without a decision vote | Audit lead |
| Release authority | Release disposition | Accept, delay, or reject on evidence | Executive sponsor for contested holds |
| Recorder | Record integrity | Evidence and finding registers, timestamps | Audit lead |

## Prerequisites and required inputs

Before execution, obtain a change identifier, decision deadline, owner roster,
deployment environment, architecture or capability inventory, current test and
monitoring evidence, declared dependencies, and known exceptions. Do not begin
with a vague request such as “check quality.” Convert it into observable
questions: which user journey, API contract, data path, or failure mode matters?

| Input | Acceptance criterion |
| --- | --- |
| Change identifier | Links to a tracked change or release record |
| Decision deadline | Date and time the decision owner will decide |
| Owner roster | Named roles, not team names |
| Deployment environment | Environment, version, and access mode stated |
| Capability inventory | Versioned map or inventory list with a revision |
| Test and monitoring evidence | Reproducible commands or dashboard links with timestamps |
| Declared dependencies | Versioned manifest or lockfile |
| Known exceptions | Prior exceptions with owner, expiry, and compensating control |

The recorder logs intake in the evidence register before any audit command runs.
An audit that begins without a brief is itself a process finding.

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

Each step has a named owner, a target output, and a timeline that fits inside
the decision deadline. If a step cannot meet its timeline, the audit lead
reports the slip to the decision owner before the deadline, not after.

| Step | Output | Owner | Timeline | Pass threshold |
| --- | --- | --- | --- | --- |
| 1. Brief | Approved brief linked in the register | Audit lead | Before intake | Decision, scope, owners, and exit criteria explicit |
| 2. Inventory | Capability-to-verification mapping | Audit lead with service owners | Day 1 | Unknown paths listed as findings, not passes |
| 3. Risk ranking | Prioritized risk register | Audit lead with domain reviewer | Days 1–2 | Every Critical or High risk has a verification owner |
| 4. Evidence collection | Evidence-register entries | Accountable engineering owner | Days 2–4 | Each entry records command, revision, timestamp |
| 5. Reproduction | Reproduction packet | Audit lead | Before finding review | Smallest reliable reproduction recorded |
| 6. Finding review | Classified finding register | Decision owner | Days 4–5 | Severity, owner, due date, and release implication set |
| 7. Remediation verification | Retest evidence | Accountable engineering owner | Before closure | Fresh evidence, not review assertions |
| 8. Closure packet | Decision and residual risk | Audit lead | At the deadline | Exceptions approved and follow-up dated |

The severity table converts classification directly into release action. Use the
governance severity model for the rating itself.

| Severity | Release implication | Retest before release | Exception allowed |
| --- | --- | --- | --- |
| Critical | Block release; convene response leadership | Required | Only executive approval with daily review |
| High | Hold release; containment plan within one business day | Required | Expiry at most 30 days plus compensating control |
| Medium | Plan in the next cycle; may proceed on approval | Recommended | With expiry, owner, and retest trigger |
| Low | Track at normal cadence | Not required | Not required |

## Worked example

The linked [API release audit example](../examples/audit-release/README.md)
reviews Atlas Billing API release `2026.4.0`. It demonstrates an authorization
regression, its evidence packet, an Important finding, and the negative test
that proves remediation.

Step-by-step, the audit ran as follows. Expected evidence is what the brief
required; observed evidence is what collection produced.

| Step | Action | Expected evidence | Observed result | Disposition |
| --- | --- | --- | --- | --- |
| 1 | Write the brief | Approved brief `AB-2026.4.0` in the register | Approved on day 1 with tenant isolation as the top hypothesis | Proceed |
| 2 | Inventory capabilities | Invoice endpoints mapped to verification methods | `GET /v1/invoices/{id}` mapped with a cross-tenant test hypothesis | Proceed |
| 3 | Rank risks | Tenant isolation ranked by impact and exploitability | Ranked Critical: financial data, broad tenant population | Priority |
| 4 | Collect evidence | Contract suite at revision `7af1e22` | Negative case: beta session requests `inv_0142` and receives `200` | Open finding |
| 5 | Reproduce | Independent re-run on the same fixture | Second reviewer confirms the `200` and the alpha invoice body | Confirmed |
| 6 | Review | Severity, owner, due date, release implication | High; API owner; due before the release window | Hold release |
| 7 | Remediate and retest | Fresh evidence at the release revision | Tenant predicate added; negative regression passes; alpha positive case still passes | Clean |
| 8 | Close | Closure packet | Decision approved with retest evidence and follow-up date | Approve |

## Automation examples

Use read-only, deterministic commands first. For an API release, run the
contract suite, authorization matrix, migration validation query, dependency
inventory, and synthetic critical-path test from a clean fixture. Capture the
exact revision and command:

```shell
rtk pytest tests/contracts tests/security -q
rtk proxy python3 scripts/verify_release_evidence.py --release 2026.4.0
```

Expected output is a passing contract suite and a release-evidence report that
names the revision, fixture checksum, and each verified capability. Failure
interpretation: a failing or skipped negative-case test is a finding, not a
statistical blip; a missing fixture or credential requirement marks that item
blocked rather than passed. Treat an unavailable command, missing fixture, or
credential requirement as blocked evidence. Do not substitute a green dashboard
screenshot for a failed or unavailable reproducible check.

> **Application note — Cutctx (reference implementation).** A Cutctx proxy audit
> follows the same brief-to-closure sequence. It collects route-policy
> versions, model-routing decision records, engine reachability evidence, and
> redacted telemetry, and it records a finding when an enabled engine reports
> zero savings without a reachability proof. Evidence locations for Cutctx
> surfaces are listed in the Cutctx reference implementation appendix; none of
> the steps above change for a product-specific application.

## Audit prompts

Use the linked [Opus](../prompts/opus/ch01-audit-architecture.md),
[Sonnet](../prompts/sonnet/ch01-evidence-review.md), and
[Haiku](../prompts/haiku/ch01-evidence-normalization.md) prompts. Their work is
intentionally different: cross-system risk synthesis, focused reproduction
review, and mechanical evidence normalization. Prompt output is analysis, not
evidence; attach source links and raw artifacts to the register before any
prompt conclusion is cited in a decision.

## Workflow checklist

Run [CL-AUDIT-01](../checklists/audit-execution.md) at intake, finding review,
and closure. Each control defines its evidence, owner, frequency, and failure
action rather than relying on a generic checkbox.

| Phase | Controls to apply |
| --- | --- |
| Intake and evidence planning | `ENG-AUDIT-001` |
| Evidence collection and reproduction | `ENG-AUDIT-002`, `ENG-AUDIT-003` |
| Finding review, severity, and closure | `ENG-AUDIT-003`, `ENG-AUDIT-004` |
| Exception handling and disclosure | `ENG-AUDIT-004`, `ENG-AUDIT-005` |

## Evidence requirements and retention guidance

Retain the brief, inventory, command logs, reports, query output, finding
register, exception decisions, and retest evidence through the next material
release or the organization’s stated retention period, whichever is longer.
Redact customer data and secrets before attaching artifacts. Preserve hashes or
immutable CI URLs for edited reports.

| Artifact | Retention period | Location | Exclusion rules |
| --- | --- | --- | --- |
| Audit brief | Decision-record lifetime | Evidence register (immutable link) | Remove internal-only scope notes after the decision |
| Command logs and reports | Through the next material release or stated retention, whichever is longer | Immutable CI URL or evidence store | Redact customer data, tokens, and secrets |
| Finding register | Decision-record lifetime | Restricted finding tracker | Remove free-text containing unredacted personal data |
| Exception decisions | Decision-record lifetime | Governance record | Archive expired exceptions with their rationale |
| Retest evidence | Through the next material release | Evidence register | Superseded by a newer retest on the same revision |

## Example findings with severity and remediation

**Important — AUTHZ-ATLAS-02.** A tenant-scoped invoice endpoint returned a
valid invoice to a session from another tenant. Evidence: a deterministic
contract test at revision `7af1e22`. Remediation: enforce tenant scope in the
repository query, add a regression test for an unauthorized tenant, and rerun
the authorization matrix. Release disposition: hold until retest is clean.

The severity rating was driven by the affected-user population (all tenants),
financial data sensitivity, and the absence of a compensating control; the
factor that drove the rating is recorded in the finding, per the governance
severity model.

**Medium — EVID-ATLAS-03.** The migration validation query was run against a
stale fixture two revisions behind the release candidate. Evidence: fixture
checksum and query timestamp. Remediation: re-run the query on the release
revision, mark the old entry superseded, and add a fixture-version assertion to
the validation script. Release disposition: proceed after the fresh run.

**Approved exception — EXC-ATLAS-2026-09.** A dependency update was delayed by
14 days. Compensating control: the prior pinned version with a current
vulnerability scan on record. Owner: service owner. Expiry: 2026-09-30. Retest
trigger: the next release candidate re-runs the dependency inventory.

## KPIs and domain scorecard

The [audit KPI catalog](../scorecards/audit-operations-kpis.md) measures audit
coverage, retest latency, and finding escape rate. `KPI-AUDIT-001` gates
approval on verified high-risk capability coverage; `KPI-AUDIT-002` measures
remediation feedback speed; `KPI-AUDIT-003` measures how many findings escape
to production. A high completion percentage is not success when high-risk
capabilities remain unknown; the scorecard therefore gates on uncovered critical
paths.

## Common failure patterns and diagnostic guidance

- Scope expands after evidence collection. Freeze the original decision and
  open a separate audit brief for newly discovered work.
- A report cites a test name but not output or revision. Re-run it and record
  the reproducible command.
- Severity is debated as a label. Revisit customer impact, exposure, and
  available containment instead of negotiating labels.
- A release exception has no expiry. It is incomplete; name an owner, expiry,
  compensating control, and retest trigger.

| Symptom | Likely cause | Check | Fix |
| --- | --- | --- | --- |
| Scope grows after collection | Decision boundary was never frozen | Compare finding scope to the brief scope | Freeze the original decision; open a new brief |
| Report cites a test name only | Evidence captured without revision or output | Look for revision, command, and output fields | Re-run and record the reproducible command |
| Severity label debated | Impact or exposure analysis missing | Ask which severity factor drove the rating | Revisit impact, exposure, and containment |
| Exception has no expiry | Incomplete exception record | Check owner, expiry, compensating control | Name owner, expiry, control, and retest trigger |
| Green dashboard replaces a check | Screenshot treated as evidence | Verify a reproducible command exists | Run the command; mark blocked if unavailable |

## Exit criteria

The audit exits only when the decision owner has a complete closure packet,
all blocking findings are remediated or explicitly accepted through the
exception process, evidence is reproducible or its limitation is declared, and
the follow-up owner/date is recorded.

| Criterion | Evidence |
| --- | --- |
| Complete closure packet | Decision, residual risk, exceptions, and evidence locations |
| Blocking findings remediated or accepted | Retest evidence or an approved exception record |
| Evidence reproducible or limitation declared | Command, revision, and output, or a limitation note |
| Follow-up owner and date recorded | Register entry with owner and date |

## Related runbooks, controls, examples, and templates

Use the audit report, evidence register, finding record, and release-decision
templates. Related assets will connect release, rollback, and incident runbooks
as those operational volumes are authored. The severity and evidence standards
in governance are the authoritative reference for the tables in this chapter.
