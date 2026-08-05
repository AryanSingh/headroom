---
id: TMPL-AI-EVALUATION-REPORT-001
kind: template
title: AI Evaluation Report
field_instructions:
  use_case: Define user, decision, model behavior, and prohibited use.
  dataset: Describe source, sampling, labeling, privacy handling, and version.
  results: Report metrics, slices, error analysis, and release decision.
completed_example:
  use_case: Atlas drafts replenishment explanations for planner review and never submits orders.
  dataset: Version atlas-eval-2026-07 uses 600 de-identified planning cases with dual review.
  results: 93 percent factual-support rate overall; 84 percent on sparse-history cases, so release remains limited.
---

# AI Evaluation Report

## Field instructions

| Field | How to complete it |
| --- | --- |
| Intended use and boundary | State user, decision support role, and excluded action. |
| Model and configuration | Record model version, prompt version, tools, and guardrails. |
| Dataset and labels | Describe provenance, sampling, labeling, version, and sensitive-data handling. |
| Metrics and slices | Define pass criteria, results, confidence limits, and subgroup analysis. |
| Error analysis and decision | Classify failures, mitigations, monitoring, and release scope. |

## Completed example: Product Atlas

**Intended use:** Atlas drafts a replenishment explanation for a planner to review; it does not place orders or modify inventory.  
**Model and configuration:** Atlas Explain v2 uses a hosted language model, prompt `atlas-explain-2.3`, retrieval limited to the tenant forecast record, and citation rendering.  
**Dataset:** `atlas-eval-2026-07` contains 600 de-identified planning cases. Two planners labeled factual support and actionability; disagreements went to a third reviewer.  
**Results:** Factual-support rate was 93% overall and 84% for sparse-history cases. Unsupported numeric claims appeared in 9 of 600 responses.  
**Decision:** Limited release for planners with a visible review step. AI System Owner Jin Park adds sparse-history abstention and re-evaluates before expanding access.
