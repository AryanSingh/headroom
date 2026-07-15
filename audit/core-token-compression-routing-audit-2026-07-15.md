# Core Audit: Token Savings, Compression, and Model Routing

**Date:** 2026-07-15
**Scope:** Core compression, savings attribution, model routing, benchmark evidence, and product trust surfaces.
**Working-tree note:** Existing user changes in OpenAI tool-schema compaction and related tests were inspected but not modified.

## Executive summary

Cutctx has an unusually broad and differentiated core: content-specific compression, reversible CCR retrieval, cache alignment, source-level savings attribution, cross-provider proxying, and conservative three-tier model routing. Focused regression coverage is strong: 328 relevant tests passed in this audit, and the current 56-case routing benchmark reported 100% tier accuracy with zero unsafe Mini downgrades.

The most important verified defect is a model-routing safety gap. The complexity classifier recognizes `role: tool`, Anthropic `tool_use`/`tool_result`, and `function_call_output` only when nested in `content`. It misses real OpenAI tool-call shapes including top-level Responses API `function_call` items, Chat Completions `tool_calls`, and `function_call` content blocks. Reproductions for all three shapes returned `LOW`, allowing an active tool-loop continuation to route to Mini despite the documented fail-conservative contract.

The largest market gap is proof quality. Cutctx's fixture comparison now includes deterministic bootstrap intervals, but its reported comparison quality remains lexical token retention rather than downstream answer/task correctness. Microsoft LLMLingua positions itself with peer-reviewed downstream-task results and up to 20x compression claims. Cutctx's stronger product story—local-first, reversible, agent-native, cross-provider—needs equally strong public evidence based on real task outcomes, not only compression ratio and F1/ROUGE overlap.

## Findings

### Resolved High — OpenAI tool-call context could be misrouted to Mini

- **Confidence:** High; reproduced directly.
- **Evidence:** `cutctx/proxy/model_router.py:169-182` checks `role == "tool"` or a narrow set of nested content-block types. It does not inspect top-level item `type`, `tool_calls`, or nested `function_call`.
- **Reproduction:** Each of the following recent-history shapes followed by `Show status.` returned `TaskComplexity.LOW`:
  - Responses API top-level `{ "type": "function_call", ... }`
  - Chat Completions assistant `{ "tool_calls": [...] }`
  - Content block `{ "type": "function_call", ... }`
- **Impact:** Active tool/repository continuations may be assigned to `gpt-5.4-mini`, weakening tool-use reliability and violating the router's conservative safety contract.
- **Resolution:** `cutctx/proxy/model_router.py` now uses a recursive provider-neutral detector for tool roles, Chat `tool_calls`, legacy `function_call`, provider call items, and `*_call_output` results. Four regression variants were written and observed failing before implementation, then passed after the minimal fix. Three provider-shape cases were added to the versioned benchmark corpus.
- **Post-fix evidence:** 178 focused routing/savings tests passed; the expanded 59-case routing benchmark retained 100% tier accuracy and zero unsafe Mini downgrades.

### High — Compression leadership is not yet supported by downstream-task comparison evidence

- **Confidence:** High.
- **Evidence:** `benchmarks/run_comparison.py:270-273` computes token-level F1 and ROUGE-L against the original text. Its output explicitly labels this a lexical-retention proxy, not downstream task quality. The fixture harness contains uncertainty intervals, but the underlying outcome is still indirect.
- **Impact:** Buyers cannot determine whether a higher reduction preserves answer correctness, tool-call validity, code behavior, or retrieval accuracy. This weakens otherwise strong savings claims and makes competitive comparisons easy to challenge.
- **Remediation:** Add task-execution evaluators for structured extraction/tool calls, QA, code repair, and long-context retrieval. Report paired baseline-vs-compressed task accuracy, savings, latency, and confidence intervals with raw versioned artifacts.

### Medium — The routing benchmark is too small and too coupled to the heuristic

- **Confidence:** High.
- **Evidence:** `benchmarks/model_routing_quality.py:31-111` plus the v2 fixture contain 56 deterministic cases. The same repository authors define both the regex heuristic and its labels. The current audit run achieved 100% on every tier and category.
- **Impact:** The gate is a useful regression suite but weak evidence of generalization. It did not contain the three provider-native tool-call shapes that exposed the verified safety defect.
- **Remediation:** Add provider-shape fixtures, paraphrase/adversarial variants, blinded human labels, and a larger held-out corpus. Keep zero unsafe Mini downgrades as the hard gate.

### Medium — Product proof mixes excellent implementation breadth with uneven evidence strength

- **Confidence:** High.
- **Evidence:** `README.md:128-164` combines real-workload savings, benchmark accuracy, and zero-LLM compression tables, but these claims use different evaluation methodologies and are not surfaced as one signed/versioned proof bundle.
- **Impact:** Technical evaluators must reconstruct what is measured, what is inferred, and which claims are reproducible locally. This creates trust friction at evaluation and procurement time.
- **Remediation:** Generate a single `cutctx evidence` bundle containing environment, versions, fixture hashes, task outcomes, routing safety, savings attribution, latency, and limitations. Render the same artifact in CLI, dashboard, and docs.

### Low — Core strength is difficult to explain as one focused product promise

- **Confidence:** Medium.
- **Evidence:** The product includes compression, routing, cache optimization, memory, governance, learning, images, multiple wrappers, and orchestration. The breadth is real, but first-time evaluation still requires understanding several modes.
- **Impact:** Users may perceive complexity before experiencing first savings.
- **Remediation:** Lead with one activation loop: setup → first compressed request → verified quality/savings receipt → seven-day report. Treat advanced capabilities as progressive disclosure.

## Verified strengths

- Content-specific transforms instead of a single generic summarizer.
- Reversible CCR retrieval and strict accuracy guardrails.
- Centralized request-outcome and savings-source attribution.
- Conservative routing defaults, confidence/abstention metadata, calibrated-scorer support, and zero-unsafe-downgrade CI intent.
- Strong focused coverage: 80 routing tests, 149 compression tests, and 99 savings/outcome tests passed during this audit.
- Routing benchmark baseline: 56/56 tier assignments correct with zero unsafe Mini downgrades before adding the newly identified provider-shape cases.

## Recommended phased improvement

1. **Completed — routing safety:** provider-native call/result shapes now fail strong during active tool loops.
2. **Next — decision-grade proof:** add downstream task evaluators and publish paired, versioned evidence bundles.
3. **Next — product activation:** expose a simple first-request savings-and-quality receipt and a seven-day proof report.
4. **Later — tune aggressiveness:** use shadow evidence to increase Mini/Luna coverage without weakening the zero-unsafe-downgrade gate.

## Verification log

- `pytest -q tests/test_model_router.py tests/test_openai_codex_routing.py tests/test_anthropic_model_routing.py` → 80 passed.
- `pytest -q tests/test_compress_api.py tests/test_pipeline_integration.py tests/test_compression_decision.py tests/test_schema_compress.py tests/test_openai_responses_context_compaction.py` → 149 passed.
- `pytest -q tests/test_request_outcome.py tests/test_savings_orchestration.py tests/test_savings_breakdown_usd_parity.py tests/test_handler_outcome_tag_invariant.py` → 99 passed.
- `benchmarks/model_routing_quality.py --ci` → 56 cases, 100% tier accuracy, zero unsafe Mini downgrades.
- Direct classifier reproduction → three OpenAI tool-call shapes incorrectly returned `LOW`.
- TDD RED → four provider-native regression variants failed with `LOW` instead of `HIGH`.
- TDD GREEN → the four variants plus stale-context coverage passed; full `tests/test_model_router.py` passed 63 tests.
- Integrated focused suite → 178 passed on Python 3.12 with the compiled Rust extension.
- Expanded routing benchmark → 59 cases, 100% tier accuracy, zero unsafe Mini downgrades.

## External comparison context

- Microsoft LLMLingua documents model-based prompt compression, peer-reviewed task evaluations, and up to 20x compression claims: https://github.com/microsoft/LLMLingua
- LiteLLM documents routing, retries, cooldowns, fallbacks, and load balancing: https://docs.litellm.ai/docs/routing
- Portkey positions its AI gateway around routing, reliability, observability, and governance: https://portkey.ai/docs/product/ai-gateway

These sources inform positioning only. No cross-vendor performance winner is claimed without a controlled same-machine, same-task benchmark.
