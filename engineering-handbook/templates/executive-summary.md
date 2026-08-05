---
id: TMPL-EXECUTIVE-SUMMARY-001
kind: template
title: Executive Summary
field_instructions:
  decision_needed: State the decision, owner, and decision date.
  evidence: Summarize the strongest evidence and material uncertainty.
  recommendation: Give a bounded action, risk, and next review point.
completed_example:
  decision_needed: Approve Atlas 4.8 limited production release by 2026-08-03 18:00 UTC.
  evidence: Migration checksums matched and rollback completed in 11 minutes; log-access finding remains open.
  recommendation: Approve with the 21-day exception and restrict unrelated data changes.
---

# Executive Summary

## Field instructions

| Field | How to complete it |
| --- | --- |
| Decision | State decision owner, deadline, and options. |
| Context | Give the business or operational reason in a few sentences. |
| Evidence and uncertainty | State decisive evidence, gaps, and confidence limits. |
| Recommendation | Give a concrete action and any conditions or constraints. |
| Next checkpoint | Name owner, date, and evidence for follow-up. |

## Completed example: Product Atlas

**Decision:** Priya Nair, Release Manager, decides whether to approve Atlas 4.8.0 limited production release by 2026-08-03 18:00 UTC.  
**Context:** Atlas 4.8 adds tenant-region support needed for the APAC pilot.  
**Evidence and uncertainty:** Migration checksums matched, tenant-isolation tests passed, and rollback completed in 11 minutes. A Medium log-access finding remains open under a 21-day exception.  
**Recommendation:** Approve the limited release, exclude unrelated data-platform changes, and retain daily access-group review until the finding closes.  
**Next checkpoint:** Mateo Ruiz provides revised access export and redaction-test evidence to Priya by 2026-08-17.
