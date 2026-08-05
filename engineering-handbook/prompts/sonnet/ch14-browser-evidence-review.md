---
id: PROMPT-SONNET-CH14-01
kind: prompt
chapter: CH-14
model_family: sonnet
workload_type: Single browser-test execution evidence review
objective: Review one Playwright execution, its fixture declaration, trace metadata, and artifacts for reproducibility, accessibility, and sensitive-data exposure.
inputs: [test command, source revision, fixture manifest, browser version, stdout and stderr, trace metadata, sanitized screenshot references]
boundaries: [Assess only the submitted execution, do not infer coverage of unexecuted states, do not reconstruct or reveal redacted values, and do not approve release policy exceptions.]
evidence: [Quote only short sanitized identifiers, attach every finding to an observed command, artifact, assertion, or missing required field.]
output_schema: {type: execution-review, fields: [result, reproducibility, assertion-quality, accessibility-evidence, artifact-safety, finding, required-follow-up]}
uncertainty: Use not-observed for absent trace or screenshot data and explain the effect on confidence.
stop_conditions: [Stop if supplied artifacts contain credentials or customer content, if the command is not attributable to a revision, or if the fixture cannot be identified.]
escalation: Escalate exposed data to security; send nonreproducible critical results to QA and the frontend owner.
standards: [OWASP-WSTG-4.2, W3C-WCAG-2.2, NIST-SSDF-1.1]
---

# Sonnet: browser execution evidence review

Review one execution record. Return a structured evidence review, separating a
product failure from an assertion, fixture, environment, or artifact-retention
failure. Do not extrapolate from this run to overall suite coverage.
