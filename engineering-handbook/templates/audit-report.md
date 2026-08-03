---
id: TMPL-AUDIT-REPORT-001
kind: template
title: Audit Report
field_instructions:
  audit_scope: Name the product, version, environment, and review boundaries.
  conclusion: State the supported conclusion and material limitations.
  findings: Summarize evidence-backed findings with owner and due date.
completed_example:
  product: Product Atlas Inventory API
  audit_scope: Release 4.8.0, production configuration and release evidence, reviewed 2026-08-03.
  conclusion: Ready with one Medium finding accepted through a 21-day exception.
  findings: Logging access group reduction owned by Service Owner Mateo Ruiz, due 2026-08-17.
---

# Audit Report

## Field instructions

| Field | How to complete it |
| --- | --- |
| Audit identification | Record report ID, reviewer, date, product, and reviewed version. |
| Scope and criteria | State the systems, environments, controls, and exclusions. |
| Evidence reviewed | List durable artifacts and their locations. |
| Findings | Give severity, impact, owner, due date, and supporting evidence. |
| Conclusion | State readiness or limitation without overstating certainty. |

## Completed example: Product Atlas

**Audit ID:** ATLAS-AUD-2026-08-03-01  
**Reviewer:** Leena Shah, Security Assurance Lead  
**Scope:** Inventory API release 4.8.0, production deployment configuration, migration evidence, and release record.  
**Criteria:** Atlas release workflow, adopted access-control practice, and evidence standard.  
**Evidence reviewed:** CI run 8851, access-policy export dated 2026-08-02, rollback rehearsal log, migration checksum report, and release decision RD-ATLAS-4.8.  
**Finding:** Medium, broad internal viewer access to tenant-name error logs. Mateo Ruiz owns access-group reduction by 2026-08-17; exception EX-ATLAS-019 expires 2026-08-24.  
**Conclusion:** The reviewed release has evidence for deployment, rollback, and migration reconciliation. The accepted finding limits assurance for log-data access until closure.
