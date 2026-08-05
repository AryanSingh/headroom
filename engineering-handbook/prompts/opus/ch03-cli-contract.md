---
id: PROMPT-CH03-OPUS-01
kind: prompt
chapter: CH-03
model_family: opus
workload_type: cross-command CLI compatibility analysis
objective: Identify compatibility, configuration, and automation risks across a CLI command family.
inputs: [help output, command inventory, configuration model, scripts, release notes]
boundaries: [Inspect supplied artifacts only, do not invoke commands or infer undocumented behavior]
evidence: [Cite command/flag source and distinguish observed output from documentation]
output_schema: {type: cli-contract-map, fields: [command_contracts, compatibility_risks, automation_risks, verification_order]}
uncertainty: Label undocumented or conflicting behavior as unknown.
stop_conditions: [missing command inventory, absent configuration model, required source unavailable]
escalation: Route breaking-change and credential concerns to the CLI owner.
---

# Opus CLI contract prompt

Analyze the supplied command family as a versioned API. Map inputs, outputs,
exit codes, configuration layers, mutations, and recovery paths. Prioritize
automation and compatibility risks with evidence references.
