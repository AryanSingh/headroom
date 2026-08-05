---
id: TMPL-RELEASE-DECISION-001
kind: template
title: Release Decision
field_instructions:
  decision: Record go, hold, rollback, or limited release with rationale.
  evidence: List the release evidence reviewed and known gaps.
  authority: Name the accountable release decision role.
completed_example:
  decision: Go for Atlas 4.8.0 after successful rollback rehearsal and reconciliation.
  evidence: CI 8851, deployment plan, checksum report, and exception EX-ATLAS-019.
  authority: Priya Nair, Release Manager.
---

# Release Decision

## Field instructions

| Field | How to complete it |
| --- | --- |
| Release identity | State product, version, environment, and planned window. |
| Decision | Select a decision and explain the evidence-based rationale. |
| Readiness evidence | List tests, approvals, monitoring, rollback, and migration evidence. |
| Open risk | State accepted risks, owner, expiry, and release constraints. |
| Authority and communications | Name decision owner and audiences notified. |

## Completed example: Product Atlas

**Release:** Atlas Inventory API 4.8.0 to production, 2026-08-03 20:00–21:00 UTC.  
**Decision:** Go. CI run 8851 passed, the staging rollback rehearsal completed in 11 minutes, and the migration checksum matched active inventory rows.  
**Open risk:** EX-ATLAS-019 covers broad error-log viewer access through 2026-08-24. The release excludes the unrelated reporting-service migration.  
**Authority:** Priya Nair, Release Manager.  
**Communication:** Priya notified on-call SRE, support, and the product owner in the Atlas release channel.
