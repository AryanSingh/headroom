---
id: PROMPT-CH15-OPUS-01
kind: prompt
chapter: CH-15
model_family: opus
workload_type: cross-system chaos experiment risk synthesis
objective: Produce a ranked assessment of hypotheses, blast radius, abort controls, correctness boundaries, recovery evidence, and residual risk.
inputs: [service map, risk register, experiment plans, baselines, fault results, recovery records]
boundaries: [analyze supplied evidence only, do not execute faults, do not treat a process restart as business recovery]
evidence: [cite hypothesis, scope, baseline, injection, outcome ledger, abort record, recovery record, and owner]
output_schema: {type: chaos-risk-synthesis, fields: [assumptions, experiment-gaps, ranked-failure-chains, recovery-assessment, release-recommendation]}
uncertainty: Separate observed experiment behavior, supported inference, and untested failure modes.
stop_conditions: [missing hypothesis, absent blast-radius control, unavailable baseline, absent accepted-work reconciliation]
escalation: Escalate data loss, duplicate work, cross-tenant impact, or unbounded fault to the incident commander and service owner.
---

# Opus chaos risk synthesis prompt

Identify what the experiment actually proves, which business boundary remains untested, and whether recovery evidence reconciles accepted work. Rank risks by impact, reversibility, exposure, and evidence strength.
