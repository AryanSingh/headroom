---
id: CL-AI-EVAL-01
kind: checklist
title: AI quality and routing evaluation checklist
chapter: CH-17
controls:
  - id: ENG-AIEVAL-001
    requirement: Every AI release candidate must be evaluated against a versioned, representative task set with declared quality, safety, route, and escalation expectations.
    applicability: required for changes to model, prompt, retrieval, tool policy, evaluator, or route policy
    procedure: Freeze case IDs and provenance, execute the candidate configuration, retain per-case results, score each declared dimension, and compare with the approved baseline.
    expected_result: Candidate results are reproducible, no safety case is silently excluded, and material regressions are visible by task class.
    evidence: dataset manifest, model and policy versions, raw or privacy-preserving results, rubric, score report, baseline comparison, and adjudications
    automation: offline evaluation fixture and release evaluation pipeline
    owner: Evaluation owner
    frequency: every material AI configuration change and release
    failure_action: block promotion, record a finding, and rerun after corrective evidence exists
    standards: [NIST-AI-RMF-1.0, NIST-AI-600-1, NIST-SSDF-1.1]
  - id: ENG-AIEVAL-002
    requirement: Route selection and safety enforcement must be independently verified for each evaluated task before a route policy is promoted.
    applicability: required for multi-model routing, fallback, tool-enabled, or sensitive AI workflows
    procedure: Compare observed route, authority scope, cost/latency class, and safety disposition to the case expectation; require human adjudication for exceptions.
    expected_result: Unsafe or unauthorized requests are blocked before side effects, and eligible tasks use only their approved route and authority boundary.
    evidence: route-policy version, trace IDs, safety decision records, route comparison, exception approvals, and release decision
    automation: deterministic route-policy fixture and trace-policy assertions
    owner: AI platform owner
    frequency: every route-policy or authority change and release
    failure_action: disable the candidate route, contain affected workflows, and escalate to security and the release owner
    standards: [NIST-AI-RMF-1.0, NIST-AI-600-1, OWASP-LLM-TOP10-2025]
---

# AI quality and routing evaluation checklist

- [ ] Freeze representative case IDs, task contracts, provenance, expected route, quality outcome, safety disposition, and escalation rule.
- [ ] Record the candidate and baseline model, prompt, retrieval, tool, evaluator, and policy versions.
- [ ] Score outcome quality, safety, route correctness, latency, and cost without excluding blocked or failed cases.
- [ ] Review every material regression and ambiguous judgment with a named human owner.
- [ ] Block unsafe route selections and unsupported release claims; preserve evidence and the rollback trigger.
