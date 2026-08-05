---
id: PROMPT-CH17-OPUS-01
kind: prompt
chapter: CH-17
model_family: opus
standards: [NIST-AI-RMF-1.0, NIST-AI-600-1, OWASP-LLM-TOP10-2025]
workload_type: cross-system AI evaluation risk synthesis
objective: Produce a prioritized release-risk assessment across dataset coverage, quality, safety, routing, authority, evaluator validity, and rollback readiness.
inputs: [task inventory, dataset manifest, baseline and candidate reports, route policies, model configurations, safety cases, adjudications, incident records]
boundaries: [analyze supplied evidence only, do not call models, alter policy, or invent benchmark outcomes]
evidence: [cite case ID, dataset version, task class, model and policy versions, trace ID, rubric result, adjudication, and owner]
output_schema: {type: ai-evaluation-risk-synthesis, fields: [coverage-map, failure-chains, ranked-risks, release-blockers, evidence-gaps, remediation-plan]}
uncertainty: Separate observed results, supported inferences, evaluator limitations, and unknown production behavior.
stop_conditions: [missing dataset provenance, absent baseline, no route-policy version, unavailable safety results, no accountable release owner]
escalation: Escalate unsafe allows, cross-scope authority, critical task regressions, or unreviewed evaluator disagreement to security and the release owner.
---

# Opus AI evaluation risk synthesis prompt

Map every task class to its intended outcome, eligible route, authority boundary, safety expectation, and evidence source. Identify unsupported release claims, blind spots in the benchmark, correlated evaluator failure modes, and failure chains that could turn a route regression into a customer or security incident. Rank remediation by impact, reversibility, and evidence quality.
