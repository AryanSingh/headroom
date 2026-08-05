---
id: KPI-CATALOG-AI-EVALUATION
kind: kpi-catalog
chapter: CH-17
kpis:
  - id: KPI-AIEVAL-001
    name: Governed task-quality pass rate
    decision: Whether a candidate meets declared user-outcome quality across the current governed evaluation population.
    calculation: passing quality cases divided by all in-scope cases, including abstentions and failures, over the versioned dataset; report not-evaluable cases separately.
    source: versioned evaluation dataset, case results, rubric, and adjudication ledger
    frequency: every candidate run and release review
    owner: Evaluation owner
    target: at or above the approved task-class threshold with no unresolved critical regression
    warning: below threshold, missing task class, or human-adjudication disagreement above the approved limit
    distortions: [benchmark overfitting, stale tasks, excluding abstentions, evaluator bias]
    anti_gaming: [version dataset, include negative and safety cases, sample human review, publish denominators]
    interpretation: A 98 percent aggregate is not a pass if a protected task class or a critical safety case regresses.
  - id: KPI-AIEVAL-002
    name: Safe route-policy conformance
    decision: Whether the deployed candidate selects an authorized route and safety disposition for each evaluated task.
    calculation: cases with expected route and safety decision divided by all executed cases, including blocked and fallback cases, over the versioned dataset.
    source: route traces, policy decision log, evaluation results, and exception approvals
    frequency: every route-policy change and release review
    owner: AI platform owner
    target: 100 percent for safety and authority cases; approved threshold by non-sensitive task class
    warning: any unsafe allow, unapproved route, missing trace, or unadjudicated fallback
    distortions: [counting only completed responses, hiding blocked cases, sampling one route, ignoring policy exceptions]
    anti_gaming: [require trace correlation, retain blocked cases, reconcile policy version, review exceptions]
    interpretation: A route that is fast and accurate still fails when its authority or safety disposition differs from policy.
---

# AI quality and routing evaluation KPI catalog

Review quality and route conformance together with dataset coverage, cost, latency, and human disagreement. Neither KPI authorizes production promotion without the associated control evidence.
