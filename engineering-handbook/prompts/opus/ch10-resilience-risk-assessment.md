---
id: PROMPT-CH10-OPUS-01
kind: prompt
chapter: CH-10
model_family: opus
workload_type: cross-system resilience and recovery risk assessment
objective: Produce a prioritized reliability risk assessment spanning objectives, dependencies, saturation, degradation, observability, and recovery evidence.
inputs: [service map, objectives, traffic model, load results, dependency evidence, telemetry samples, recovery exercise records]
boundaries: [analyze supplied artifacts only, do not operate services, do not infer production behavior from an absent fixture]
evidence: [cite workload, objective revision, dependency, fixture, metric or trace, recovery record, and owner for every conclusion]
output_schema: {type: resilience-risk-assessment, fields: [outcome_model, evidence_gaps, failure_chains, ranked_risks, release_recommendation]}
uncertainty: Separate observed fixture behavior, supported inference, and unknown capacity or recovery behavior.
stop_conditions: [missing service map, absent objective definition, unavailable load result, no recovery evidence for durable service]
escalation: Escalate possible data loss, duplicate critical outcome, objective breach, or unverified restore to the SRE and data owners.
---

# Opus resilience risk assessment prompt

Trace each critical outcome through dependencies, saturation behavior, telemetry, and recovery. Rank failure chains by customer impact, data correctness, reversibility, and evidence strength. Treat an omitted workload class, untested dependency, or backup-only claim as a gap rather than proof of resilience.
