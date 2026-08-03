---
id: CH-17
kind: chapter
title: AI Quality and Routing Evaluation
purpose: Establish reproducible, evidence-led evaluation of AI quality, safety, route selection, and fallback behavior before a model or routing policy is released.
audience: [AI platform engineers, application engineers, QA engineers, security engineers, product owners, release managers]
scope: Evaluation datasets, task contracts, route decisions, scoring, safety gates, regression analysis, human review, and release evidence.
applicability: Model-backed features, agent workflows, classifiers, extraction pipelines, retrieval systems, and multi-model routing policies.
owners: [AI platform owner, evaluation owner, security owner, product owner]
inputs: [task inventory, evaluation dataset, route policy, model configuration, rubric, safety policy, baseline results]
outputs: [evaluation report, release decision, regression findings, route-policy change record]
dependencies: [NIST-AI-RMF-1.0, NIST-AI-600-1, OWASP-LLM-TOP10-2025, NIST-SSDF-1.1]
standards: [NIST-AI-RMF-1.0, NIST-AI-600-1, OWASP-LLM-TOP10-2025, NIST-SSDF-1.1]
---

# AI Quality and Routing Evaluation

## Purpose, audience, scope, and applicability

Evaluate an AI system as a decision path, not merely a model response. A release claim needs a versioned task set, an explicit route policy, reproducible scoring, safety checks, and a human decision for material regressions. Apply this procedure whenever model, prompt, retrieval, tool policy, evaluator, or fallback logic changes.

## Concepts and engineering principles

Separate capability quality from operational suitability. A concise answer may score well while using an unauthorized route, leaking sensitive context, exceeding a cost limit, or failing to refuse a harmful instruction. Measure task outcome, route correctness, safety behavior, latency, and cost together; never turn one aggregate score into an unconditional release approval.

## Roles and accountability

The AI platform owner owns route-policy enforcement and reproducibility. The evaluation owner curates the dataset and scoring protocol. The product owner defines task acceptance and materiality. Security owns adversarial and data-handling criteria. The release owner accepts, blocks, or time-bounds residual risk with traceable evidence.

## Prerequisites and required inputs

Collect a task inventory, versioned evaluation cases, expected outcomes, scoring rubric, route policy, model and prompt versions, safety policy, prior baseline, and decision thresholds. Synthetic data must be labeled; production-derived cases require minimization, access control, retention rules, and documented approval.

## Standard operating procedure

1. Define the user outcome, prohibited outcomes, quality rubric, and the route eligible for each task class.
2. Freeze a representative dataset with case IDs, expected classifications, safe-response expectations, and versioned provenance.
3. Execute every case against the exact route-policy, model, prompt, retrieval, and tool configuration proposed for release.
4. Score quality separately from route selection, safety, latency, and cost; preserve raw records and evaluator version.
5. Compare the candidate with an approved baseline by task class and inspect every regression above the materiality threshold.
6. Require human review for ambiguous scores, protected-domain outcomes, safety blocks, and route-policy exceptions.
7. Record the release decision, accepted residual risk, rollback trigger, owner, and next evaluation due date.

## Worked example

[Product Atlas offline AI evaluation](../examples/ai-evaluation/README.md) evaluates billing-support classification. It verifies that a routine invoice-status request uses the low-cost route, an account-closure request uses the high-assurance route, and an instruction-exfiltration attempt is blocked before any route executes.

## Automation examples

```bash
python3 evaluate_fixture.py
# AI_EVALUATION_FIXTURE_PASS quality=1.00 route=1.00 safety=1.00 release=approved
```

```bash
python3 evaluate_fixture.py --report evaluation-report.json
python3 -c "import json; print(json.load(open('evaluation-report.json'))['release_decision'])"
# approved
```

## Audit prompts

Use [Opus](../prompts/opus/ch17-evaluation-risk-synthesis.md), [Sonnet](../prompts/sonnet/ch17-regression-evidence-review.md), and [Haiku](../prompts/haiku/ch17-evaluation-inventory.md) for risk synthesis, focused regression review, and inventory normalization.

## Workflow checklist

Run [CL-AI-EVAL-01](../checklists/ai-quality-routing-evaluation.md) before a model, prompt, retrieval corpus, tool authority, evaluator, or route policy is promoted.

## Evidence requirements and retention guidance

Retain dataset version and provenance classification, policy and model versions, case-level outputs or privacy-preserving references, scoring rubric, evaluator version, route traces, safety decisions, baseline comparison, human adjudications, and release decision. Do not retain secrets, unrestricted customer content, or hidden reasoning traces when concise outcome evidence is sufficient.

## Example findings with severity and remediation

**High — AI-EVAL-ATLAS-01.** A prompt-injection case produced a helpful-looking answer on an unapproved low-assurance route. Remediate by blocking instruction-conflict patterns before routing, adding the case to the regression suite, and requiring a security review before route-policy promotion.

## KPIs and domain scorecard

The [AI evaluation KPI catalog](../scorecards/ai-evaluation-kpis.md) measures task-quality pass rate and safe route-policy conformance. Review both with coverage and human-disagreement trends; a high score on a narrow or stale dataset is not evidence of release readiness.

## Common failure patterns and diagnostic guidance

- A benchmark excludes abstentions, safety blocks, or failed tool calls from the denominator.
- The evaluator shares the candidate model's blind spots without calibration or sampled human review.
- A route-policy change is evaluated only by aggregate quality and not cost, latency, authority, or safety.
- Production transcripts are retained as an unbounded benchmark without minimization or provenance controls.

## Exit criteria

Exit when every in-scope case has reproducible outcome and route evidence, safety failures block promotion, material regressions are adjudicated, data handling is approved, and the release decision names an accountable owner and rollback trigger.

## Related runbooks, controls, examples, and templates

Use the AI-evaluation-report, verification-plan, threat-model, finding, and release-decision templates with the evaluation checklist. Escalate unsafe behavior through the incident response runbook.
