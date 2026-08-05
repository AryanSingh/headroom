---
id: APP-GLOSSARY-001
kind: reference
title: Engineering Audit Glossary
purpose: Establish shared operational vocabulary used by the handbook.
audience: [engineering teams, auditors, product and operations partners]
standards: [NIST-SSDF-1.1, OWASP-ASVS-5.0.0, NIST-AI-RMF-1.0]
---

# Engineering Audit Glossary

## Evidence and governance

**Acceptance criterion** — An observable condition that is true before an activity, release, or control is considered complete.

**Control** — A stable requirement with a reproducible procedure, owner, evidence, cadence, and failure action. A control is not a policy slogan.

**Evidence** — A durable artifact that supports a stated conclusion: test output, signed decision, configuration export, query result, incident timeline, or reviewed recording. Evidence includes collection time and source.

**Exception** — A time-bounded, named decision to operate outside a control. It includes risk, compensating measures, accountable owner, expiry, and closure criteria; it is not a silent waiver.

**Finding** — A gap between required behavior and reviewed evidence, with severity, impact, owner, due date, and remediation path.

**Risk acceptance** — An accountable decision to accept a residual risk for a defined interval. It does not prove the risk is resolved.

## Delivery and operations

**Canary** — A deliberately limited production exposure used to assess a release against predeclared signals before wider rollout.

**Change failure rate** — Failed production changes divided by all production changes over a defined period. Pair it with deployment frequency to prevent incentives to avoid change.

**Error budget** — The permitted unreliability implied by an SLO. Spending it guides release risk; it does not replace customer-impact review.

**Idempotency** — Repeating a request or job has the same intended effect as performing it once. The idempotency key, scope, retention period, and duplicate result are part of the contract.

**Recovery point objective (RPO)** — Maximum acceptable data loss measured in time. RPO is tested through restore evidence, not asserted from a backup schedule.

**Recovery time objective (RTO)** — Maximum acceptable time to restore a service outcome. Measure from a declared incident start to restored user capability.

**Service-level indicator (SLI)** — The measured quantity used to assess a service outcome, such as successful tenant-scoped API responses.

**Service-level objective (SLO)** — The target range for an SLI within a period. State the population, exclusions, measurement path, and owner.

## Security and data

**Authorization boundary** — The point where the system decides whether a principal may perform a specific action on a specific resource in a tenant and environment.

**Least privilege** — Granting only the access necessary for a stated role and time window, with review and revocation evidence.

**Tenant isolation** — Preventing a tenant’s data, tools, credentials, or execution context from being read or affected by another tenant.

**Data classification** — A documented label describing handling expectations for data, such as public, internal, confidential, or restricted. Labels guide actual access and retention behavior.

**Retention** — The approved period data or evidence remains available. Retention includes deletion or archival verification, legal hold handling, and ownership.

## AI and automation

**Agent** — A system that selects or sequences actions toward a goal. It may use tools, memory, models, and delegated roles; each authority boundary remains explicit.

**Evaluation set** — Versioned input cases and expected assessment criteria used to measure a system. It includes provenance, labels, slices, and known limitations.

**Human-in-the-loop** — A named person performs a meaningful review or approval before an irreversible or high-impact action. Merely displaying output is not sufficient.

**Model routing** — Selecting a model, provider, configuration, or fallback according to a stated policy and observed request attributes.

**Prompt injection** — Untrusted content attempts to change an AI system’s instructions, authority, or tool use. Treat external content as data, not as a trusted directive.

**Replay** — Re-executing a recorded input or workflow to reproduce a behavior. Replays protect sensitive data and prevent unintended external effects.

## Testing and measurement

**Deterministic fixture** — A local, repeatable test setup whose result does not require paid APIs, mutable external state, or nondeterministic timing.

**False positive** — A test or alert reports a problem when the specified problem is absent. Track it alongside detection rate to avoid untrusted automation.

**Leading indicator** — A measure intended to warn before an outcome, such as growing queue age. Validate it against later impact rather than treating it as proof.

**Trace correlation** — Linking logs, metrics, and spans to a shared request or workflow identifier so a reviewer can reconstruct an outcome without guessing.
