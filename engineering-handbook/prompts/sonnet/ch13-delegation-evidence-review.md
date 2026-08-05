---
id: PROMPT-CH13-SONNET-01
kind: prompt
chapter: CH-13
model_family: sonnet
standards: [NIST-AI-RMF-1.0, OWASP-LLM-TOP10-2025]
workload_type: single delegation authority evidence review
objective: Determine whether one delegated workflow run stayed within its issued authority and reached a reconciled terminal state.
inputs: [task envelope, capability grant, policy decisions, tool proposals, approval record, trace events, authoritative outcome]
boundaries: [review one correlation ID, use supplied evidence only, do not approve actions or reconstruct missing authority]
evidence: [cite correlation ID, capability ID, scope, expiry, tool arguments, policy decision, approval, target outcome, and owner]
output_schema: {type: delegation-evidence-review, fields: [verdict, authority-chain, scope-check, approval-status, outcome-reconciliation, gaps]}
uncertainty: Mark absent policy decisions, ambiguous tool scope, missing approval, or unlinked target results as unresolved.
stop_conditions: [missing task identity, absent capability grant, unavailable trace, no authoritative outcome for a claimed completion]
escalation: Send a scope mismatch, unapproved sensitive action, or unreconciled completion to the workflow owner.
---

# Sonnet delegation evidence review prompt

Review one run as a bounded chain: task, grant, policy decision, invocation, approval where required, and target outcome. Confirm tool arguments never exceed the grant. Identify the smallest missing record or control needed to make the run reviewable.
