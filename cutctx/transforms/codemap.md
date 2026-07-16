# cutctx/transforms/

## Responsibility
Implements the composable context-transformation engine for code, prose, logs, search, diffs, HTML, audio, structured tables, and tool output.

## Design
A transform base contract and `TransformPipeline` implement ordered Strategy composition with budgets, circuit breakers, observability, cache alignment, anchor/tag protection, and adaptive sizing. Content routing selects specialized compressors; smart crusher and selective/verbatim transforms provide fallbacks.

## Flow
Input is normalized and classified, protected spans/anchors are identified, policy and budget select transforms, stages compact content with failure isolation, and output metadata/summaries report units, savings, and fidelity decisions.

## Integration
Called by SDK compression, proxy intelligence, integrations, and evals; depends on tokenizers, relevance, caches, optional ML compressors, and provider-specific policies.
