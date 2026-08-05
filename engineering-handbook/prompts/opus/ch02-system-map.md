---
id: PROMPT-CH02-OPUS-01
kind: prompt
chapter: CH-02
model_family: opus
workload_type: cross-system capability and trust-path mapping
objective: Produce a candidate end-to-end capability graph and evidence-gap order for an unfamiliar product.
inputs: [product brief, repository map, deployment manifests, API/UI inventory, provider list, ownership data]
boundaries: [Use only supplied material, separate configured from observed behavior, do not assert runtime reachability without evidence]
evidence: [Cite each node and edge to a source artifact or identify it as an inference]
output_schema: {type: capability-graph-review, fields: [capabilities, trust_paths, dependency_paths, unknowns, verification_order]}
uncertainty: Mark each assertion observed, configured, inferred, or unknown.
stop_conditions: [missing product outcomes, no revision or deployment context, conflicting system boundaries]
escalation: Return contested ownership or high-impact unknowns to the discovery lead.
---

# Opus capability-map prompt

Map supplied user and operator outcomes through entry points, authorization,
state, dependencies, and recovery. Highlight cross-system paths that are likely
to hide risk. Build a verification order from impact and evidence gaps, not from
directory order. Return only the declared capability-graph-review schema.
