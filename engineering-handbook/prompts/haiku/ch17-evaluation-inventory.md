---
id: PROMPT-CH17-HAIKU-01
kind: prompt
chapter: CH-17
model_family: haiku
standards: [NIST-AI-RMF-1.0, OWASP-LLM-TOP10-2025]
workload_type: AI evaluation asset inventory normalization
objective: Normalize supplied evaluation cases, routes, model versions, rubrics, safety rules, owners, and evidence references into a compact release inventory.
inputs: [task inventory, dataset manifest, route policy, model registry, prompt registry, rubric, safety rules, owner list, report links]
boundaries: [normalize supplied records only, do not infer a pass, assign risk, or invent provenance]
evidence: [preserve case ID, task class, dataset version, route, model version, prompt version, safety rule, owner, and report reference]
output_schema: {type: ai-evaluation-inventory, fields: [task-classes, cases, routes, configurations, safety-rules, owners, evidence-gaps]}
uncertainty: Use unknown for absent provenance, expected route, rubric version, safety rule, owner, trace, or report reference.
stop_conditions: [missing dataset manifest, missing route policy, records cannot be associated with task classes]
escalation: Send missing safety rules, no accountable owner, or an unversioned candidate configuration to the AI platform owner.
---

# Haiku AI evaluation inventory prompt

Produce one compact record per task class and candidate configuration. Preserve supplied identifiers, expected route, safety rule, owner, and evidence reference. Do not translate a successful response into a release approval.
