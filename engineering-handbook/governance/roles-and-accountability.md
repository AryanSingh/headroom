# Roles and Accountability

## Role catalogue

| Role | Accountable for | Typical decisions | Evidence retained |
| --- | --- | --- | --- |
| Product owner | customer outcome and prioritization | scope, acceptance trade-offs | approved requirements, decision log |
| Engineering manager | delivery system and staffing | delivery plan, operational ownership | plan, capacity decision |
| Service owner | production behavior of a service | operational readiness, remediation | service inventory, runbook review |
| Security lead | security risk advice and escalation | risk treatment, security review | threat model, findings |
| Release manager | release coordination | go, hold, rollback | release decision |
| Incident commander | incident coordination | severity, containment priority | timeline, communications log |
| Data steward | data quality and lifecycle | migration and retention decisions | migration plan, reconciliation |
| AI system owner | model behavior and evaluation | evaluation acceptance, monitoring | evaluation report, dataset record |

## Assignment practice

Give one accountable role to each decision. Contributors may perform work and reviewers may challenge it, but they do not replace the accountable role. Record temporary delegation with its start, end, and decision scope.

## Escalation path

Escalate when a risk owner cannot accept residual risk within their authority, evidence conflicts, a safety or security issue crosses a declared threshold, or a release decision lacks a named owner. The receiving leader records a decision, a deadline, and the next communication point.

## Product Atlas example

For Atlas release 4.8, Priya held the Release Manager role and Mateo held the Service Owner role. Mateo supplied the load-test report and rollback rehearsal. Priya recorded a hold when the reconciliation job exceeded its recovery objective, then approved release after a repair and repeat test. The Data Steward reviewed the migration evidence but did not own the go decision.

## Role review checklist

- Is one accountable role named for each decision?
- Do contributors know their deliverable and due date?
- Does the record name an escalation receiver for unresolved risk?
- Can an auditor locate the evidence without relying on personal messages?
