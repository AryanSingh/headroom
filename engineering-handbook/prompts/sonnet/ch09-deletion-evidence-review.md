---
id: PROMPT-CH09-SONNET-01
kind: prompt
chapter: CH-09
model_family: sonnet
standards: [NIST-SSDF-1.1, NIST-AI-RMF-1.0]
workload_type: focused memory deletion-chain evidence review
objective: Determine whether one deletion request has verifiable completion across the declared memory layers.
inputs: [deletion request, layer topology, job records, retrieval checks, cache and index acknowledgements]
boundaries: [review one subject and request only, do not inspect raw sensitive content, do not infer unlisted layers]
evidence: [cite request ID, layer, acknowledgement, retrieval result, and timing for every conclusion]
output_schema: {type: deletion-chain-review, fields: [verdict, layer_statuses, unresolved_layers, exposure_assessment, closure_conditions]}
uncertainty: Mark missing acknowledgements, unknown backups, and untested retrieval paths as unresolved.
stop_conditions: [missing deletion request ID, unavailable topology, no post-delete retrieval check]
escalation: Escalate any retrievable deleted subject or missed service objective to privacy and incident owners.
---

# Sonnet deletion evidence review prompt

Review the supplied deletion chain. Confirm primary, index, cache, export, and retrieval evidence against the declared topology. Do not close the request on a primary-store acknowledgement alone; specify the minimal proof required for every unresolved layer.
