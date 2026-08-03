# Exception Management

## Purpose

An exception records a deliberate, time-bounded departure from an adopted control or workflow. It makes risk visible to the owner; it does not erase the underlying control or finding.

## Exception record

Capture the control or practice, affected product scope, rationale, risk assessment, compensating measures, accountable risk owner, reviewer, start date, expiry date, and closure evidence. Set a review date before expiry.

## Decision flow

1. The requester describes the delivery constraint and attaches available evidence.
2. The control owner assesses the affected control and proposed compensating measures.
3. The named risk owner accepts, declines, or requests changes within their authority.
4. The team tracks remediation to closure and records verification evidence.
5. The exception owner reviews expiry and either closes the record or seeks a new decision with updated evidence.

## Product Atlas example

Atlas could not complete a full disaster-recovery exercise before a regional launch because its test tenant lacked production-scale data. The Reliability Lead accepted a 21-day exception after the team ran a restore drill at smaller scale, scheduled the full exercise, and placed a release hold on unrelated data-platform changes. The exception closed after the full exercise met the recorded recovery objective.

## Guardrails

Do not use an exception to conceal an incident, bypass access controls for convenience, or create an open-ended acceptance. Escalate an exception that affects safety, regulated data, or a high-severity exposure to the appropriate risk authority.
