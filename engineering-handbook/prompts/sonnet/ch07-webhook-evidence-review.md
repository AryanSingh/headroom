---
id: PROMPT-CH07-SONNET-01
kind: prompt
chapter: CH-07
model_family: sonnet
workload_type: focused webhook and tool-boundary evidence review
objective: Assess one callback/tool action for signature, tenant, replay, and approval evidence.
inputs: [callback fixture, signature verdict, event record, tool request, approval record]
boundaries: [Inspect supplied evidence only, do not expose secrets or invoke provider]
evidence: [Cite event/environment/tenant identifiers]
output_schema: {type: integration-boundary-review, fields: [status, observed_checks, gaps, regression_test, remediation]}
uncertainty: Mark absent original-body or approval evidence unresolved.
stop_conditions: [secret-bearing input, missing event ID, missing source revision]
escalation: Send blocking authority failure to integration owner.
---

# Sonnet callback evidence prompt

Review a single authority boundary and propose a deterministic regression test.
