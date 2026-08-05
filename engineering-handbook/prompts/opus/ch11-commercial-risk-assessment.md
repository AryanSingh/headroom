---
id: PROMPT-CH11-OPUS-01
kind: prompt
chapter: CH-11
model_family: opus
workload_type: cross-system commercial launch risk assessment
objective: Produce a prioritized assessment of offer, entitlement, metering, billing, support, privacy, and customer-commitment risks for a proposed launch.
inputs: [offer catalog, entitlement matrix, usage schema, billing flow, support plan, customer commitments, fixture evidence]
boundaries: [analyze supplied artifacts only, do not approve pricing or customer terms, do not infer enforcement from a UI screenshot]
evidence: [cite catalog revision, entitlement boundary, usage event, invoice or adjustment reference, fixture, owner, and commitment source for each conclusion]
output_schema: {type: commercial-risk-assessment, fields: [offer-model, evidence-gaps, failure-chains, ranked-risks, launch-recommendation]}
uncertainty: Separate verified enforcement, supported inference, and unknown billing or customer-impact behavior.
stop_conditions: [missing offer definition, absent entitlement matrix, unavailable usage evidence, no support route]
escalation: Escalate possible unauthorized access, duplicate charge, misleading commitment, or unapproved adjustment to the commercial product and billing owners.
---

# Opus commercial launch risk assessment prompt

Trace each offered customer outcome from catalog through entitlement, service execution, usage, invoice, support, and customer commitment. Rank risks by customer impact, financial correctness, reversibility, and evidence strength. Treat an absent execution-boundary fixture as a launch gap.
