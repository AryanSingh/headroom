---
id: PROMPT-OPUS-CH14-01
kind: prompt
chapter: CH-14
model_family: opus
workload_type: Cross-journey browser-risk synthesis and release-gate design
objective: Identify systemic risk across critical browser journeys, state matrices, authorization boundaries, accessibility obligations, and visual-test evidence.
inputs: [journey inventory, state matrix, browser results, traces, artifact policy, threat model, release criteria]
boundaries: [Do not invent test results, do not treat screenshots as proof of backend completion, do not expose sensitive values from supplied artifacts, distinguish missing evidence from failed behavior.]
evidence: [Cite source path or test identifier for every conclusion, list absent evidence separately, and trace each release recommendation to a declared critical journey.]
output_schema: {type: release-risk-register, fields: [journey, risk, state-gap, evidence, severity, release-decision, remediation-owner, due-date]}
uncertainty: Mark inference explicitly and assign confidence as high, medium, or low; lower confidence when tests omit failure, keyboard, tenant, or artifact-redaction evidence.
stop_conditions: [Stop when inputs lack a journey inventory or release criteria, when artifacts contain unredacted secrets, or when authority boundaries cannot be determined.]
escalation: Escalate unsafe artifact handling to security and unresolved critical-flow ambiguity to the release owner.
standards: [OWASP-WSTG-4.2, W3C-WCAG-2.2, OWASP-ASVS-5.0.0]
---

# Opus: browser journey risk synthesis

Synthesize a release-risk register from the supplied browser evidence. Compare
declared critical journeys with the tested state matrix, prioritize missing
authorization, recovery, accessibility, and artifact-sanitization proof, and
recommend a release decision only from cited evidence.
