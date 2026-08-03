---
id: PROMPT-CH07-HAIKU-01
kind: prompt
chapter: CH-07
model_family: haiku
workload_type: mechanical integration and tool inventory normalization
objective: Normalize provider, scope, callback, tool, owner, and disable-switch records.
inputs: [provider list, scope list, callback list, tool schemas, owner records]
boundaries: [Do not infer reachability or authority correctness]
evidence: [Preserve source identifiers]
output_schema: {type: integration-inventory, fields: [kind, identifier, owner, scope, disable_switch, gap]}
uncertainty: Record absent values as gaps.
stop_conditions: [secret-bearing records or missing identifiers]
escalation: Send ambiguous entries to integration recorder.
---

# Haiku integration inventory prompt

Normalize only supplied records into inventory rows.
