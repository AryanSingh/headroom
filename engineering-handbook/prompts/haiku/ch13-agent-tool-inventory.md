---
id: PROMPT-CH13-HAIKU-01
kind: prompt
chapter: CH-13
model_family: haiku
standards: [NIST-AI-RMF-1.0, NIST-AI-600-1]
workload_type: agent and tool authority inventory normalization
objective: Normalize supplied agent, workflow, tool, capability, approval, owner, and evidence records into a compact inventory.
inputs: [agent registry, workflow definitions, tool registry, capability policies, approval rules, owner list, trace samples]
boundaries: [normalize supplied records only, do not infer permissions, mark a workflow compliant, or invent owners]
evidence: [preserve agent ID, workflow ID, tool ID, scope, expiry, approval rule, owner, and source reference]
output_schema: {type: agent-tool-inventory, fields: [agents, workflows, tools, authority-scopes, approval-rules, owners, evidence-gaps]}
uncertainty: Use unknown for absent scope, expiry, approval rule, owner, trace reference, or retention class.
stop_conditions: [missing agent registry, missing tool registry, records cannot be associated with a workflow]
escalation: Send any tool with ambient authority or no accountable owner to the agent platform owner.
---

# Haiku agent and tool inventory prompt

Produce one compact record per workflow-tool relationship. Preserve stated scope, expiry, approval rule, owner, and evidence reference. Do not translate an agent name or a successful run into authorization evidence.
