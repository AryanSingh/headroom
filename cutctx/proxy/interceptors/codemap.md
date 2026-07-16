# cutctx/proxy/interceptors/

## Responsibility
Intercepts tool outputs to replace bulky developer-tool results with compact representations.

## Design
A base interceptor contract has AST-grep, Difftastic, graph, and related strategies selected by tool/content. Each preserves essential semantics while producing bounded output.

## Flow
Tool calls/results are matched to an interceptor, transformed or summarized, and returned with metadata; unsupported results pass through unchanged.

## Integration
Used by proxy tool-surface and intelligence pipelines; integrates with local code-aware tools and graph context.
