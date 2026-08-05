---
id: RB-INC-001
kind: runbook
title: Service Incident Response
triggers: [Credible customer-impacting availability, integrity, performance, or security event; breached service objective; operator escalation]
severity: [Critical, High, Medium, Low]
roles: [Incident Commander, Technical Lead, Communications Lead, Scribe, On-call SRE, Service Owner]
prerequisites: [Incident channel, incident record, current telemetry, service ownership roster, escalation contacts]
decisions: [Declare severity, contain, mitigate, escalate, recover, close response]
communication: [Internal incident channel, support liaison, status owner, executive delegate for critical events]
containment_or_rollback: [Stop unsafe change, reduce traffic, isolate component, disable feature, invoke relevant rollback or security procedure]
evidence: [Timestamped timeline, telemetry links, command/deployment records, customer reports, decisions, communications]
recovery: [Restore safe service, validate critical journeys, monitor stability, hand off corrective work]
exit_criteria: [Customer impact is controlled, service is stable, communications are current, follow-up owner exists]
follow_up: [Blameless review, corrective actions, evidence retention, severity reassessment]
standards: [NIST-IR-800-61R3, OTEL-SEMCONV-1.43.0]
---

# Service Incident Response

## Purpose

Coordinate a time-bounded response to a production service event. This runbook prioritizes customer safety, evidence, and clear authority over premature root-cause conclusions. Security-specific evidence handling follows the security-incident runbook.

## First ten minutes

1. Create the incident record and channel. Assign an incident commander and scribe; state the next update time.
2. Record the observed symptom, affected service, first-known time, customer scope, evidence links, and current uncertainty.
3. Assign a severity using the risk model. Reassess whenever scope or evidence changes.
4. Apply low-risk containment: halt a rollout, reduce traffic, disable the affected feature, or isolate a failing worker. Record every action and result.
5. Assign technical investigation and communications separately. The incident commander owns priorities and external commitments.

## Product Atlas example

Atlas recommendation updates are delayed for 48 minutes across 18 tenants. The commander rates the event High, pauses the import batch, and assigns an SRE to queue recovery while support posts a stale-data notice. Queue depth falls, fresh recommendations appear for a test tenant, and the team monitors two processing windows before downgrading impact and scheduling a review.

## Operating loop

At each update, answer: what changed, who is affected, what evidence supports it, what containment is active, what decision is next, and when will the next update occur. Maintain a timestamped fact timeline. Mark hypotheses as hypotheses. Do not paste credentials, customer content, or exploit detail into a broad channel.

## Decision guide

| Condition | Action |
| --- | --- |
| Scope unknown or growing | Raise severity, broaden investigation, keep containment reversible |
| Security compromise suspected | Invoke security incident response and restrict evidence access |
| Release-caused regression | Invoke rollback while retaining incident coordination |
| Data correctness uncertain | Stop destructive or compounding work; invoke migration or data recovery |
| Stable recovery verified | Start observation window and plan handoff |

## Recovery and exit

Recovery means the critical customer journey works, telemetry is fresh, and no containment action is silently failing. Exit active response after the commander documents current impact, recovery evidence, remaining risk, owner, and next review time. The follow-up review records contributing conditions and measurable corrective actions without assigning blame.
