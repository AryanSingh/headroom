---
id: CH-15
kind: chapter
title: Chaos Engineering Audit
purpose: Demonstrate that critical outcomes remain safe, observable, and recoverable when realistic failures are deliberately introduced.
audience: [SREs, platform engineers, service owners, security engineers, release managers]
scope: Hypothesis-driven experiments, blast-radius controls, steady-state measures, abort criteria, recovery evidence, and corrective actions.
applicability: Customer-facing services, queues, data stores, identity dependencies, control planes, and AI-assisted workflows.
owners: [Service owner, SRE owner, incident commander]
inputs: [service map, risk register, steady-state indicators, experiment plan, rollback runbook, isolated fixtures]
outputs: [experiment record, findings, remediation backlog, release decision]
dependencies: [NIST-SSDF-1.1, NIST-IR-800-61R3, OTEL-SEMCONV-1.43.0]
standards: [NIST-SSDF-1.1, NIST-IR-800-61R3, OTEL-SEMCONV-1.43.0]
---

# Chaos Engineering Audit

## Purpose, audience, scope, and applicability

Chaos engineering is controlled learning from failure, not unbounded disruption. Audit whether critical outcomes have a measurable steady state, a reversible fault plan, a named stop authority, and evidence that recovery preserves correctness.

The audit covers every fault injection, recovery exercise, and chaos-derived release claim: customer-facing services, queues, data stores, identity dependencies, control planes, and AI-assisted workflows. It applies to production, production-like, and isolated-fixture experiments alike, because a fixture that hides real queue age, tenant skew, or cold-cache behavior produces evidence that flatters the wrong system. The deliverable is not a list of injected failures; it is a set of tested hypotheses about the outcomes customers depend on, each with baseline and observed evidence, a bounded blast radius, and a finding or confirmed claim attached.

## Concepts and engineering principles

Start with a falsifiable hypothesis: under a specified fault, a specified outcome remains within its declared boundary. Bound blast radius by tenant, time, rate, environment, and irreversible actions. A recovered process is not proof if accepted work was duplicated, silently lost, or attributed to the wrong tenant.

Three principles govern every experiment. First, **the hypothesis names the outcome, not the component**: measure whether accepted work is queued once and recovered once, whether a customer can still complete a critical action, and whether latency stays within its boundary, rather than whether a process restarts. Second, **the baseline is captured under comparable conditions**: same topology, data shape, cache state, and traffic pattern, so the observed delta is attributable to the fault and not to a quieter day. Third, **recovery is proven at the business ledger**: idempotency keys, queue depth, tenant scope, and invoice or order outcomes are reconciled after the fault, because a process that restarts while duplicating accepted work has not recovered.

## Roles and accountability

The service owner owns the business boundary. The SRE owner designs injection and observability. The incident commander may abort immediately. Security approves experiments that affect authorization, secrets, or tenant isolation. The release owner accepts only remediated or time-bounded residual risk.

| Role | Owns | Approves | Accountable for |
| --- | --- | --- | --- |
| Service owner | Business boundary, outcome correctness, remediation | Hypothesis, result reconciliation | That accepted work is neither lost nor duplicated |
| SRE owner | Fault design, injection, observability, recovery rehearsal | Experiment plan, blast-radius scope | That the fault is bounded and reversible |
| Incident commander | Abort authority | Immediate abort when safety is at risk | That no experiment outruns its stop authority |
| Security owner | Authorization, secret, tenant-isolation impact | Security-affected experiments | That no fault crosses tenant or authorization boundaries |
| Release owner | Chaos-derived release claims | Release decisions from experiment evidence | That only remediated or time-bounded risk ships |

## Prerequisites and required inputs

Obtain a dependency map, production-like but isolated fixtures, approved hypothesis, steady-state query, rollback action, abort thresholds, communications channel, and evidence location. Confirm that fault injection cannot contact production or issue irreversible external actions.

Before the audit, confirm the dependency map is current, the steady-state query is defined and its baseline captured, and the abort thresholds are named with the authority who can pull the kill switch. The fixture must represent realistic queue age, tenant distribution, and cache state rather than an empty synthetic world. The communications channel must be agreed before injection, and the evidence location must be able to retain traces and logs for the full review window, because recovery evidence collected after logs expire is not evidence at all.

## Standard operating procedure

1. **Choose one critical outcome and declare its boundary.** State the success, correctness, latency, and recovery boundary for a single outcome. Owner: service owner. Threshold: one outcome per experiment; a boundary that cannot be measured is a blocking gap.
2. **Define the fault and blast radius.** Specify the fault, the environment, the tenant or traffic scope, the duration, the rate, and the irreversible actions excluded. Owner: SRE owner. Threshold: the blast radius is bounded on every axis and reversible.
3. **Name the abort authority and thresholds.** Record who may abort, what threshold triggers an abort, and the rollback or containment action. Owner: incident commander. Threshold: an abort is executable by the named authority without waiting for approval.
4. **Capture the baseline.** Record the steady-state query, the observation window, and the baseline result under comparable conditions. Owner: SRE owner. Timeline: baseline must be captured within the agreed window before injection (for example, the same hour of the same day type, not a holiday).
5. **Inject one reversible fault.** Introduce a single fault within the declared scope. Owner: SRE owner. Threshold: one fault at a time; no experiment combines independent faults until each is understood.
6. **Observe across signals.** Collect client outcome, queue state, traces, logs, and business-ledger evidence together with the correlation IDs that tie them. Owner: SRE owner.
7. **Abort on threshold breach.** If any stop threshold is breached, abort, contain, and recover, then preserve all evidence before retrying or expanding scope. Owner: incident commander. Timeline: abort decision recorded within the declared response window.
8. **Reconcile the business result.** Verify that accepted work is queued once, recovered once, and attributed to the correct tenant, using idempotency and ledger queries. Owner: service owner.
9. **Compare with the hypothesis and record findings.** Every unsupported claim becomes a finding with a severity, owner, and due date; every supported claim is recorded as confirmed evidence. Owner: service owner.
10. **Re-run after remediation.** Repeat the fixture after remediation and attach the passing result and the finding closure to the release evidence. Owner: release owner.

### Abort and escalation decision table

| Observation during experiment | Likely meaning | Decision | Owner |
| --- | --- | --- | --- |
| Stop threshold breached | Fault larger than modeled, or boundary wrong | Abort immediately, contain, preserve evidence | Incident commander |
| Cross-tenant or authorization signal | Scope control failed | Abort, isolate, invoke incident process | Security owner |
| Accepted work duplicated or lost | Recovery path broken | Abort, reconcile ledger, block release claim | Service owner |
| Baseline and observed not comparable | Environment or data skew | Abort, recapture baseline, rerun | SRE owner |
| All signals within boundary | Hypothesis supported | Record confirmed evidence, close experiment | Service owner |

## Worked example

[Product Atlas queue-partition experiment](../examples/chaos/README.md) injects a bounded worker outage. It proves that an accepted invoice is queued once, exposed as delayed, and recovered without a duplicate charge.

Walk through the expected evidence sequence. The hypothesis: "when the invoice worker partition is stopped for three minutes, accepted invoices remain queued exactly once, are exposed as delayed, and recover without duplicate charges." The baseline captures queue depth, invoice-outcome counts, and the delayed-invoice dashboard query for the same weekday window. The fault stops a bounded worker partition; the blast radius is limited to one tenant cohort and no production traffic is redirected. During the outage, the queue depth grows, the delayed-invoice view shows the affected invoices with the declared status, and no invoice is charged twice. The abort threshold is armed: if any invoice produced a duplicate outcome or the queue exceeded the declared bound, the incident commander would stop the experiment. After recovery, the reconciliation query groups `invoice_outcomes` by idempotency key and returns no key with a count above one, proving the invoice was queued once and recovered once. The experiment record attaches the baseline query, injection record, abort-threshold state, dashboard evidence, reconciliation result, and a confirmed-hypothesis note.

## Automation examples

```bash
python3 chaos_fixture.py
# CHAOS_FIXTURE_PASS queued-once recovered-once abort-threshold-armed
```

```sql
SELECT idempotency_key, COUNT(*)
FROM invoice_outcomes
WHERE experiment_id = 'atlas-queue-partition-01'
GROUP BY idempotency_key HAVING COUNT(*) > 1;
```

Automation should arm the abort threshold before injection, fail the experiment if the fault plan is out of scope, capture the baseline automatically, and block a chaos-derived release claim until the ledger reconciliation and finding closure are recorded. The fixture should be the same versioned fixture the service uses for its release gate, so experiment evidence and release evidence measure the same behavior.

## Audit prompts

Use [Opus](../prompts/opus/ch15-chaos-risk-synthesis.md), [Sonnet](../prompts/sonnet/ch15-experiment-evidence-review.md), and [Haiku](../prompts/haiku/ch15-experiment-inventory.md) for risk synthesis, experiment evidence review, and compact experiment inventory.

Use the Opus prompt when the audit spans the risk register, experiment plan, and release claims and you need a consolidated risk statement. Use the Sonnet prompt to review one experiment's evidence package, checking that the baseline is comparable, the abort path is evidenced, and the ledger reconciles. Use the Haiku prompt to build the compact experiment inventory before planning. Treat model output as a hypothesis to verify against experiment records before it becomes a finding.

## Workflow checklist

Use [CL-CHAOS-01](../checklists/chaos-engineering.md) before any fault injection, recovery exercise, or chaos-derived release claim.

The checklist controls `ENG-CHAOS-001` through `ENG-CHAOS-005` cover hypothesis and blast-radius safety, outcome reconciliation, recovery evidence, finding ownership, and experiment scheduling. `ENG-CHAOS-005` (scheduling and conflict management) prevents the expensive failure mode where an experiment runs during an incident or another experiment and its evidence can no longer be attributed; check the experiment register before every injection.

## Evidence requirements and retention guidance

Retain the approved hypothesis, scope, fixture version, baseline, injection record, abort decision, trace and metric queries, business-ledger reconciliation, recovery record, finding, and owner decision. Exclude payloads, credentials, and customer content.

| Evidence | What to record | Retention | Owner |
| --- | --- | --- | --- |
| Experiment plan | Hypothesis, scope, fault, thresholds, authority, rollback | Experiment register life | SRE owner |
| Baseline and observation | Steady-state queries, baseline result, observed result, window | Experiment register life | SRE owner |
| Injection record | Fault, scope, timestamps, fixture version | Experiment register life | SRE owner |
| Abort evidence | Threshold breached, decision, containment, recovery action | Incident linkage plus audit window | Incident commander |
| Ledger reconciliation | Idempotency query, queue state, tenant scope result | Experiment register life | Service owner |
| Findings and decisions | Severity, owner, due date, remediation retest, release decision | Finding life plus one year | Service owner |

Payloads, credentials, and customer content never enter the experiment evidence set. Where a trace is needed for investigation, retain it in the incident evidence store with an explicit retention and access rule, and confirm the evidence location can hold the full review window before injection.

## Example findings with severity and remediation

**High — CHAOS-ATLAS-01.** A worker restart replayed an acknowledged invoice without an idempotency record. Remediate by writing durable deduplication state before acknowledgement and repeating the restart fixture as a release gate.

**High — CHAOS-ATLAS-02.** An experiment targeting a queue dependency ran during an unrelated incident window, so its error-rate signal could not be attributed to the fault and the experiment had to be discarded. Remediation: consult the experiment register and incident state before injection, and require a conflict-free window for any experiment whose evidence will feed a release claim.

**Medium — CHAOS-ATLAS-03.** The recovery trace was collected after the sampling policy had discarded the failing span, so the recovery path was asserted but not evidenced. Remediation: confirm trace retention covers the experiment window before injection, and capture recovery evidence as part of the experiment, not after it.

## KPIs and domain scorecard

The [chaos KPI catalog](../scorecards/chaos-kpis.md) measures hypothesis coverage and verified recovery. Do not count a planned experiment as coverage until its business result and abort behavior are evidenced. Review `KPI-CHAOS-001` and `KPI-CHAOS-002` monthly and at release review, and add `KPI-CHAOS-003` (finding closure) to the monthly review, because an experiment that reveals a defect and produces no fixed retest is a cost without a lesson.

## Common failure patterns and diagnostic guidance

- An experiment measures process uptime instead of customer outcome and duplicate work.
- A broad fault lacks a kill switch or named abort authority.
- A synthetic fixture hides tenant skew, cold-cache behavior, or queue age.
- Recovery evidence is collected after logs have expired or sampling discarded the failing trace.

| Symptom | Likely cause | Check | Fix |
| --- | --- | --- | --- |
| Experiment passes, incident later | Measured uptime, not outcome | Inspect hypothesis for a business outcome boundary | Name the outcome and its correctness boundary |
| Fault cannot be stopped | No kill switch or named abort authority | Review plan for threshold and authority | Arm abort threshold; name authority before injection |
| Fixture evidence flatters system | Empty or unrepresentative synthetic data | Compare fixture queue age, tenant mix, cache state | Use versioned production-like fixtures |
| Recovery claimed, no trace | Evidence collected after retention expiry | Verify retention covers experiment window | Confirm evidence location before injection |
| Finding never remediated | No owner or due date | Review finding register | Assign owner and due date at experiment close |

## Exit criteria

Exit when the fault hypothesis has baseline and observed evidence, blast radius remained bounded, abort and recovery paths were demonstrably usable, accepted work reconciles correctly, and findings have an owner and due date.

| Criterion | Evidence | Passes when |
| --- | --- | --- |
| Hypothesis evidenced | Baseline and observed result with comparable conditions | Observed outcome compared against declared boundary |
| Blast radius bounded | Scope, injection, and containment records | Fault never exceeded declared scope |
| Abort path usable | Armed threshold and recorded abort decision | Stop authority executable without approval wait |
| Recovery proven | Ledger reconciliation and recovery record | Accepted work neither lost nor duplicated |
| Findings owned | Finding register with severity, owner, due date | Every unsupported claim has remediation ownership |
| Release claim valid | Remediated retest and release decision | Only remediated or time-bounded risk ships |

## Related runbooks, controls, examples, and templates

Use the incident-review, verification-plan, and release-decision templates with the chaos checklist and production incident runbook.

> **Application note — Cutctx.** For a token-compression proxy product, the chaos audit applies to the compression and routing pipeline: the hypothesis should name a measured outcome such as "under a routing-engine outage, requests fall back to the approved default preset without token-count regressions," with the steady-state query pinned to the engine, model, and preset versions in force. The trap in `docs/handoff-2026-07-28.md` — an engine enabled, silent, and saving nothing while claiming "lossless" behavior — is a business-ledger failure: the reconciliation must compare claimed compression against measured per-request token counts, and the experiment register must record which preset version was in force so the fault result is attributable.
