---
id: PROMPT-CH08-OPUS-01
kind: prompt
chapter: CH-08
model_family: opus
workload_type: multi-policy routing and orchestration risk synthesis
objective: Produce a prioritized route-policy risk map for a changed workload, provider, or fallback graph.
inputs: [workload inventory, policy revisions, provider capabilities, failure traces, evaluation results]
boundaries: [inspect supplied artifacts only, do not execute routes, do not infer undisclosed provider guarantees]
evidence: [cite policy predicate, workload class, trace reason code, and fixture result for every claim]
output_schema: {type: routing-risk-map, fields: [decision_graph, boundary_risks, failure_modes, ranked_findings, verification_order]}
uncertainty: Separate observed policy behavior, reasoned impact, and untested failure conditions.
stop_conditions: [missing policy revision, absent workload-to-provider mapping, unavailable failure evidence]
escalation: Escalate cross-boundary routing or duplicated privileged action risk to routing, security, and SRE owners.
---

# Opus routing risk map prompt

Analyze the supplied routing change as a decision system. Trace workload classification through policy predicates, candidate selection, fallback, queueing, retry, and telemetry. Prioritize boundary loss, hidden defaults, duplicate actions, and unverifiable decisions. Return the declared structure without inventing capacity or provider behavior.
