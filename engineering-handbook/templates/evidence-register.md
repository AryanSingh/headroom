---
id: TMPL-EVIDENCE-REGISTER-001
kind: template
title: Evidence Register
field_instructions:
  evidence_item: Identify one durable artifact and the claim it supports.
  location: Provide a stable repository, ticket, or protected-record reference.
  retention: State classification and retention decision.
completed_example:
  evidence_item: Atlas 4.8 migration checksum report.
  location: Release vault /atlas/4.8/migration-checksum-2026-08-02.pdf.
  retention: Internal, 18 months, restricted to release and data teams.
---

# Evidence Register

## Field instructions

| Field | How to complete it |
| --- | --- |
| Claim supported | State the decision or assertion the artifact supports. |
| Source and collector | Identify the producing system and person or role that registered it. |
| Timestamp and scope | State when collection occurred and what it covered. |
| Location and access | Give a stable location and access classification. |
| Retention and integrity | State retention period and any hash, signature, or immutable record. |

## Completed example: Product Atlas

| Evidence ID | Claim supported | Source and collector | Timestamp and scope | Location and access | Retention and integrity |
| --- | --- | --- | --- | --- | --- |
| EV-ATLAS-481 | Migration preserved active inventory rows | Atlas reconciliation job; collected by Data Steward Noor Patel | 2026-08-02 18:10 UTC; release 4.8.0 production migration | Release vault `/atlas/4.8/migration-checksum-2026-08-02.pdf`; Internal, release and data teams | 18 months; SHA-256 recorded in release decision |
