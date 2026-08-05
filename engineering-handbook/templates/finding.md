---
id: TMPL-FINDING-001
kind: template
title: Finding Record
field_instructions:
  condition: Describe observed evidence rather than speculation.
  impact: State credible harm and affected scope.
  remediation: Name owner, target date, and verification evidence.
completed_example:
  condition: Atlas error-log viewer group included 42 support users without a support case need.
  impact: Tenant names could be viewed outside the incident response purpose.
  remediation: Service Owner Mateo reduces the group by 2026-08-17 and attaches an access export.
---

# Finding Record

## Field instructions

| Field | How to complete it |
| --- | --- |
| Observation | Record what the reviewer observed and how. |
| Severity and rationale | State rating and factors that drove it. |
| Impact | Describe the credible effect, not a hypothetical extreme. |
| Recommendation | Describe a practical corrective action or compensating measure. |
| Ownership and verification | Name accountable role, date, and closure evidence. |

## Completed example: Product Atlas

**Finding ID:** FND-ATLAS-2026-014  
**Observation:** The 2026-08-02 access export showed 42 members in `atlas-error-log-viewers`; 31 had no active support case role.  
**Severity:** Medium. Tenant names appear in some error messages and the group expands internal exposure.  
**Impact:** Unauthorized internal viewing could weaken Atlas's customer-data handling commitments.  
**Recommendation:** Restrict the group to on-call support roles and redact tenant names from new error messages.  
**Owner and verification:** Service Owner Mateo Ruiz, target 2026-08-17. Closure evidence: revised access export and passing redaction test run.
