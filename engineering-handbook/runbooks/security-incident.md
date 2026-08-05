---
id: RB-SEC-001
kind: runbook
title: Security Incident Response
triggers: [Suspected unauthorized access, credential exposure, tenant-boundary failure, malicious activity, integrity compromise, confirmed vulnerability exploitation]
severity: [Critical, High, Medium]
roles: [Security Incident Commander, Security Lead, Incident Commander, Forensics Lead, Legal/Privacy Liaison, Communications Lead, Service Owner]
prerequisites: [Restricted incident workspace, escalation contacts, logging access, evidence storage, authority for credential and traffic controls]
decisions: [Classify event, preserve evidence, contain access, rotate credentials, notify stakeholders, recover, close]
communication: [Restricted security channel, need-to-know leadership, legal/privacy liaison, approved customer communication path]
containment_or_rollback: [Revoke credentials, restrict access, disable integration, isolate affected workload, block malicious traffic, roll back unsafe change]
evidence: [Immutable log references, access records, artifact hashes, affected-scope analysis, custody record, decision timeline]
recovery: [Restore trusted identities and service state, validate isolation, monitor for recurrence]
exit_criteria: [Containment verified, required notifications decided, recovery evidence retained, residual risk owned]
follow_up: [Forensic review, vulnerability remediation, credential hygiene review, control effectiveness test]
standards: [NIST-IR-800-61R3, OWASP-ASVS-5.0.0, OWASP-API-TOP10-2023]
---

# Security Incident Response

## Purpose and evidence discipline

Use this runbook when confidentiality, integrity, authentication, authorization, or tenant isolation may be compromised. Limit access to the response workspace. Preserve original evidence references before changing systems; do not collect unnecessary customer data or disclose unverified technical details.

## Product Atlas example

Atlas detects repeated API requests where a signed webhook is replayed across tenants. The security commander disables the webhook consumer, revokes the integration credential, retains request identifiers and signature-verification logs in the restricted case folder, and validates that replayed requests are rejected after a nonce-policy change. Legal and privacy receive the confirmed scope, not speculative estimates.

## Procedure

1. Open a restricted case, appoint the security incident commander, and record reporter, first-known time, systems, and confidence level.
2. Preserve volatile evidence through approved snapshots or immutable log references. Record collector, time, source, scope, and access restrictions.
3. Establish affected identities, tenants, services, data classes, and active attack path. Treat unknown scope as a reason to contain, not as proof of no impact.
4. Contain the smallest effective boundary: revoke or rotate credentials, disable the integration, restrict policy, isolate workload, or block traffic. Record who authorized it.
5. Verify containment from independent evidence. For an identity event, test revoked access; for tenant isolation, use controlled cross-tenant probes; for malware or host compromise, follow the platform forensic procedure.
6. Decide notifications with legal, privacy, and communications owners based on confirmed facts, contractual commitments, and applicable obligations. Do not promise scope or timing before approval.
7. Eradicate the cause with reviewed, tested changes. Rebuild trust in keys, sessions, artifacts, and configuration rather than assuming a single visible symptom is complete.
8. Recover in stages with heightened monitoring. Retain a timeline of decisions and evidence locations.

## Do not

- Do not delete logs, rotate away the only credential evidence, or wipe a system before the forensics lead authorizes it.
- Do not use a public channel for customer records, secrets, exploit steps, or unconfirmed attribution.
- Do not close because traffic has returned; close only when containment, recovery, notification decisions, and residual risk ownership are documented.

## Exit and follow-up

Exit when containment is independently verified, communications decisions are recorded, trusted service operation is demonstrated, and the case has an accountable follow-up owner. Test the corrective control against the original attack path and review evidence access after the case closes.
