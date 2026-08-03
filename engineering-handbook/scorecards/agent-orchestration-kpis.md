---
id: KPI-CATALOG-AGENT-ORCH
kind: kpi-catalog
chapter: CH-13
kpis:
  - id: KPI-AGENT-001
    name: Bounded authority execution coverage
    decision: Whether tool-invoking workflow runs have a complete, matching authority chain.
    calculation: completed tool-invoking runs with a task identity, scoped grant, policy decision, invocation record, and authoritative outcome divided by all completed tool-invoking runs.
    source: orchestrator traces, capability broker logs, policy decisions, and authoritative service audit events
    frequency: daily and before release
    owner: Agent platform owner
    target: 100 percent
    warning: below 100 percent or any invocation without a matching scope and expiry
    distortions: [counting planner-only runs, accepting generated success text, excluding denied requests]
    anti_gaming: [sample trace-to-service reconciliation, include denied and retried runs, compare capability scope to tool arguments]
    interpretation: Coverage is meaningful only when the completed action is independently linked to the authority that permitted it.
  - id: KPI-AGENT-002
    name: Sensitive action approval and reconciliation coverage
    decision: Whether high-impact agent actions are approved and confirmed by their authoritative target.
    calculation: sensitive actions with recorded approval and successful outcome reconciliation divided by all sensitive action attempts.
    source: approval queue, workflow traces, tool audit logs, and target-system outcome records
    frequency: each action and weekly
    owner: Workflow owner
    target: 100 percent
    warning: any unapproved invocation, unresolved outcome, or approval after execution
    distortions: [classifying risky writes as low impact, measuring only approved actions, treating HTTP acceptance as completion]
    anti_gaming: [independent action classification review, include denied attempts, require business-state reconciliation]
    interpretation: An approval is not complete evidence until the target system outcome is matched to the approved request.
---

# Agent orchestration KPI catalog

Review authority coverage and sensitive-action reconciliation together. A reliable agent program can show both why it was allowed to act and what the authoritative system actually did.
