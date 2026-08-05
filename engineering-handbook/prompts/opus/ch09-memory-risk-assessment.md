---
id: PROMPT-CH09-OPUS-01
kind: prompt
chapter: CH-09
model_family: opus
workload_type: cross-layer memory governance and security risk assessment
objective: Produce a prioritized risk assessment for memory ingestion, retrieval, retention, deletion, and AI evaluation.
inputs: [memory inventory, data classifications, access policies, layer topology, deletion evidence, evaluation results]
boundaries: [inspect supplied artifacts only, do not retrieve memory, do not assume consent or retention evidence]
evidence: [cite memory type, layer, policy rule, fixture result, and evaluation record for every claim]
output_schema: {type: memory-risk-assessment, fields: [data_flow, control_gaps, deletion_risks, retrieval_risks, ranked_actions]}
uncertainty: Separate observed evidence, inference about derivatives, and unknown retention or authorization behavior.
stop_conditions: [missing memory inventory, absent layer topology, unavailable access or deletion evidence]
escalation: Escalate cross-tenant retrieval, deletion failure, or regulated-data exposure to security and privacy owners.
---

# Opus memory governance risk assessment prompt

Analyze memory as a cross-layer governed system. Trace source to derivative, authorization to ranking, and deletion request to all retrieval surfaces. Rank risks by exposure, reversibility, and evidence strength; do not infer a safe layer from primary-store success.
