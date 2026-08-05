---
id: PROMPT-CH07-OPUS-01
kind: prompt
chapter: CH-07
standards: [OWASP-ASVS-5.0.0, OWASP-API-TOP10-2023]
model_family: opus
workload_type: cross-system integration authority mapping
objective: Map provider scopes, data flows, tool actions, approvals, replay paths, and disable controls.
inputs: [integration inventory, scopes, callback contracts, tool schemas, approval policy]
boundaries: [Use supplied artifacts only, do not execute tools or infer provider behavior]
evidence: [Cite sources and separate observed authority from configured scope]
output_schema: {type: integration-authority-map, fields: [authority_paths, high_impact_actions, evidence_gaps, verification_order]}
uncertainty: Label missing scope or approval evidence unknown.
stop_conditions: [missing owner, scope, or tool schema]
escalation: Route privileged ambiguity to integration and security owners.
---

# Opus integration authority-map prompt

Map who can cause each action, which evidence proves the boundary, and where approval is required.
