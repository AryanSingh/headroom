---
id: PROMPT-HAIKU-CH14-01
kind: prompt
chapter: CH-14
model_family: haiku
workload_type: Browser-test inventory normalization
objective: Normalize browser-test metadata into a compact inventory of journey, state, locator type, fixture, artifact class, and owner.
inputs: [test file list, test titles, fixture list, journey inventory, artifact-retention labels]
boundaries: [Do not evaluate risk severity, do not infer behavior from a test title alone, do not include secret values, and preserve unknown fields as unknown.]
evidence: [Return the input file or test identifier for each row and flag missing mapping fields.]
output_schema: {type: normalized-test-inventory, fields: [test-id, journey, state, fixture, locator-class, artifact-class, owner, mapping-status]}
uncertainty: Set mapping-status to unknown or incomplete rather than guessing a missing journey, owner, or state.
stop_conditions: [Stop after all supplied test records are normalized or when input cannot be parsed into identifiable records.]
escalation: Send incomplete critical-journey mappings to QA ownership for classification.
standards: [OWASP-WSTG-4.2, W3C-WCAG-2.2]
---

# Haiku: UI test inventory normalization

Convert supplied browser-test metadata into the declared inventory schema.
Preserve source identifiers, mark missing mappings, and avoid risk analysis or
release recommendations.
