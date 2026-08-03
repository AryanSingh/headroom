---
id: TMPL-VERIFICATION-PLAN-001
kind: template
title: Verification Plan
field_instructions:
  claims: List delivery claims that need evidence.
  methods: Map each claim to test, review, or observation and pass signal.
  risks: State gaps, owner, and fallback action.
completed_example:
  claims: Atlas 4.8 preserves inventory records and rolls back within 15 minutes.
  methods: Reconciliation query, API smoke suite, and timed rollback rehearsal.
  risks: Production load differs from staging; SRE monitors queue lag and pauses rollout if lag exceeds five minutes.
---

# Verification Plan

## Field instructions

| Field | How to complete it |
| --- | --- |
| Claims | Write observable claims about behavior, safety, performance, or operability. |
| Method and pass signal | Map each claim to a repeatable check and measurable result. |
| Environment and data | State environment, fixtures, access, and data constraints. |
| Evidence | Name report, log, screenshot, query output, or approval record. |
| Risk and fallback | Identify uncertainty, owner, and decision if evidence is incomplete. |

## Completed example: Product Atlas

**Claims:** Atlas 4.8 preserves active inventory records, rejects cross-tenant access, and completes rollback within 15 minutes.  
**Methods and pass signals:** Run reconciliation query with matching counts and checksums; run tenant-isolation API suite with zero unauthorized responses; time a staging rollback at 15 minutes or less.  
**Environment and data:** Staging replica with 12 million synthetic inventory rows and three tenant fixtures; Data Steward grants read-only reconciliation access.  
**Evidence:** CI run 8851, checksum report EV-ATLAS-481, tenant-isolation test report, and rollback rehearsal log.  
**Risk and fallback:** Production traffic may exceed staging load. SRE Elena monitors queue lag and pauses the rollout if it exceeds five minutes.
