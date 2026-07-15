# Product Manager Audit: Cutctx Core Efficiency Product

**Date:** 2026-07-15
**Scope:** Token savings, compression, model routing, onboarding to proof, retention, and competitive gaps.

## Product assessment

Cutctx is already differentiated at the feature level. Its strongest combination is local-first compression, provider-neutral proxying, reversible CCR retrieval, source-attributed savings, cache optimization, agent wrappers, and safety-conscious model routing. Few products combine all of these in one control plane.

The next market challenge is not feature count. It is making safety and ROI independently believable. A user should be able to install Cutctx, run one real workload, and receive a trustworthy receipt showing what changed, what was saved, what quality checks passed, which model was selected, and how to reproduce the result.

## Existing features

- Content-specific compression for JSON/tool output, code, logs, diffs, search, prose, schemas, and images.
- Reversible CCR storage and retrieval.
- Accuracy guards for identifiers and references.
- Cache alignment and cache-aware savings attribution.
- Model routing with Mini/Luna/strong tiers, confidence, abstention, trace metadata, and calibrated-scorer support.
- OpenAI-, Anthropic-, and agent-compatible proxy/wrapper surfaces.
- Savings dashboard, metrics, history, and source breakdown.
- Unified setup flow and broad integration surface.

## Missing or incomplete product capabilities

### Partially resolved P0 — Decision-grade quality proof

`cutctx evals downstream` now runs zero-provider task consumers and publishes paired baseline-vs-compressed accuracy for JSON aggregation, operational log lookup, diff interpretation, and tool-result extraction. This is credible local task-outcome evidence and already found two real query-preservation defects. Provider-backed preservation is now recorded for SQuAD v2, HotpotQA, and CodeSearchNet, plus a Claude/Codex subscription-CLI route pilot. BFCL remains excluded until tool calls are schema-validated; HumanEval and long-context evaluation still require executable/statistically powered runs before research-grade or cross-vendor claims.

### Resolved P0 — Provider-complete routing safety

The router previously missed several OpenAI tool-call message shapes and could classify an active tool-loop continuation as low complexity. The recent-context detector now covers provider-native call and result shapes recursively, with TDD regressions and a 59-case benchmark gate. Increasing routing coverage should still remain evidence-gated.

### Resolved P1 — One portable evidence bundle

`cutctx evidence` now generates versioned JSON or Markdown joining downstream task outcomes, compression verification, routing safety, release posture, Context Assurance, first-request/seven-day savings attribution, SHA-256 artifact bindings, and limitations. It produces honest unavailable states instead of manufacturing proof.

### Resolved P1 — Activation receipt and seven-day report

The evidence command selects the earliest persisted request in the reporting window for the activation receipt and aggregates a seven-day period by default. It uses canonical additive savings-source attribution and includes the routing, quality, release, and assurance proof artifacts alongside ROI.

### P2 — Privacy-reviewed activation analytics

Measure install → healthy proxy → first request → first verified savings receipt → seven-day retained use. Keep telemetry opt-in or local-first and document exactly what leaves the machine.

## Competitive gaps

| Dimension | Cutctx position | Gap to close |
| --- | --- | --- |
| Compression | Broader agent/runtime integration and reversibility than standalone compressors | Match research competitors with downstream-task, reproducible public evidence |
| Model routing | Strong conservative policy, traces, abstention, and orchestration | Expand held-out evaluation and provider-shape coverage before increasing savings |
| AI gateway | Strong context-specific optimization and local-first story | Simplify evaluation and make reliability/ROI proof portable |
| Native provider compaction | Cross-provider and attributable | Prove incremental value over provider-native cache/compaction on the same workloads |
| Hosted simplicity | Strong local/privacy advantage | Reduce first-value friction and offer a clear supported deployment path |

## User journey friction

### Discover

The feature surface is broad enough that a buyer may not know whether Cutctx is primarily a compressor, proxy, router, memory layer, or governance plane. Lead with the outcome: verified context efficiency for AI agents.

### Evaluate

Current proof is distributed across README tables, benchmark artifacts, CLI stats, and audit documents. A buyer must assemble the trust story manually.

### Activate

Setup is improved, but the first-value loop should end with a real compressed request and a quality/savings receipt, not only a healthy proxy.

### Operate

Operators need clear visibility into abstentions, guard failures, CCR retrievals, provider-cache interaction, and model-routing quality—not only gross token reduction.

### Renew

Retention depends on recurring, trustworthy ROI. A seven-day/monthly proof report should show net savings after overhead, quality incidents, routing outcomes, and top optimization opportunities.

## Onboarding issues

- Too many equally prominent modes before the user has experienced value.
- Capability discovery is stronger than guided workload selection.
- First successful setup is not yet the same as first verified ROI.
- Public proof does not yet guide users to reproduce the most relevant workload category.

## Retention issues

- Savings alone can become background noise; users need confidence and actionability.
- No single recurring report explains net value, risk avoided, and next optimization.
- Weak downstream-task evidence may block team expansion after an individual developer trial.
- Broad enterprise surfaces increase maintenance burden unless usage and buyer value are measured.

## Recommended product strategy

Adopt a **trust-first efficiency loop**:

1. Safely compress and route.
2. Verify what must remain correct.
3. Attribute every saving without double counting.
4. Emit a portable evidence receipt.
5. Learn from abstentions and retrievals.
6. Increase savings only where shadow evidence proves quality.

This positions Cutctx beyond a prompt compressor or generic gateway: an evidence-backed context efficiency control plane.

## Success metrics

- Zero unsafe Mini downgrades in provider-complete routing suites and shadow evidence.
- Baseline-vs-compressed downstream task delta within an explicit quality budget per workload.
- Install-to-first-verified-receipt time under five minutes for supported local agents.
- Percentage of active users viewing or exporting a seven-day evidence report.
- Net token and dollar savings after compression/routing overhead, separated by source.
- CCR retrieval and guard-failure rates low enough to demonstrate trustworthy compression.
- Expansion from single developer to team workspace after verified ROI.

## Immediate priority

Provider-native tool-context detection, the 59-case corpus, deterministic downstream task execution, query-aware log preservation, portable activation/evidence receipt, and initial provider/subscription route evidence are complete. The next major investment is external validation: schema-aware BFCL, executable HumanEval, a statistically powered long-context run, independently labeled routing data, and privacy-reviewed opt-in activation analytics. Avoid more aggressive downgrades until those external gates are in place.
