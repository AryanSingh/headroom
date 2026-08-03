---
id: PROMPT-CH18-OPUS-01
kind: prompt
chapter: CH-18
model_family: opus
standards: [NIST-SSDF-1.1, OWASP-ASVS-5.0.0, OWASP-API-TOP10-2023]
workload_type: cross-consumer compatibility failure-chain synthesis
objective: Produce a prioritized compatibility risk assessment across contract semantics, generated SDKs, legacy consumers, authority boundaries, deprecation, rollback, and release evidence.
inputs: [prior and candidate specifications, behavior diff, support matrix, SDK versions, contract tests, authorization evidence, deprecation plan, rollout telemetry]
boundaries: [analyze supplied evidence only, do not call services, infer consumer behavior, or approve unsupported versions]
evidence: [cite contract field, version pair, consumer, fixture result, authority check, telemetry record, owner, and release decision for each conclusion]
output_schema: {type: compatibility-risk-synthesis, fields: [transition-map, consumer-risks, authority-risks, evidence-gaps, ranked-findings, required-gates, decision-recommendation]}
uncertainty: Separate observed compatible behavior, supported inference, and unknown consumer or production behavior.
stop_conditions: [missing supported-version policy, absent consumer matrix, removed required contract field, no authority evidence, no deprecation exit rule]
escalation: Escalate cross-tenant acceptance, incompatible supported consumer behavior, or unbounded retirement to API, SDK, security, and release owners.
---

# Opus compatibility risk synthesis prompt

Map each supported consumer through the old and candidate contract before ranking risks. Trace request and response semantics, error codes, authority checks, generated-client behavior, deprecation state, telemetry, rollback, and evidence gaps. Treat a missing support-matrix row as an unknown, not proof of compatibility.
