---
id: PROMPT-CH13-OPUS-01
kind: prompt
chapter: CH-13
model_family: opus
standards: [NIST-AI-RMF-1.0, NIST-AI-600-1, OWASP-LLM-TOP10-2025]
workload_type: cross-workflow orchestration risk synthesis
objective: Produce a prioritized risk assessment across agent identity, delegation, authority, tools, state, approvals, recovery, and outcome reconciliation.
inputs: [agent inventory, workflow graphs, capability policies, traces, tool schemas, evaluations, incident records]
boundaries: [analyze supplied evidence only, do not invoke tools, grant authority, or infer missing trace events]
evidence: [cite workflow ID, correlation ID, policy version, capability ID, tool event, approval, outcome record, and owner for each conclusion]
output_schema: {type: orchestration-risk-synthesis, fields: [authority-graph, failure-chains, ranked-risks, evidence-gaps, remediation-priorities]}
uncertainty: Separate observed control behavior, supported inference, and unknown runtime or target-system outcomes.
stop_conditions: [missing workflow inventory, absent authority policy, unavailable trace sample, no owner for sensitive actions]
escalation: Escalate cross-tenant authority, unapproved side effects, unbounded retries, or irreconcilable outcomes to the agent platform and security owners.
---

# Opus orchestration risk synthesis prompt

Map each workflow from request to authoritative outcome. Identify where instructions can alter authority, where a retry can broaden scope, and where a claimed result lacks independent confirmation. Rank risks by blast radius, reversibility, evidence quality, and likelihood of silent misuse.
