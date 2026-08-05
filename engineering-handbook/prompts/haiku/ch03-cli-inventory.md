---
id: PROMPT-CH03-HAIKU-01
kind: prompt
chapter: CH-03
model_family: haiku
workload_type: mechanical CLI command and flag inventory
objective: Normalize supplied CLI help text into command and option records.
inputs: [help output, version output, command aliases]
boundaries: [Do not infer semantics or reachability, preserve literals, do not execute commands]
evidence: [Keep source text reference for each record]
output_schema: {type: cli-inventory, fields: [command, option, argument, documented_exit_code, source_reference, gap]}
uncertainty: Record omitted or ambiguous values as gaps.
stop_conditions: [help output is truncated, source version is absent, output includes secrets]
escalation: Return unsupported syntax or conflicting docs to the CLI recorder.
---

# Haiku CLI inventory prompt

Normalize help output into inventory rows. Preserve names exactly, capture
documented values, and flag missing exit-code or automation information.
