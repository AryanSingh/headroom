# Token-Savings Priorities

## Purpose
Cutctx's next major savings wins come less from generic prose compression and more from removing repeated scaffolding that gets sent every turn. This document captures the highest-ROI priorities, the best implementation seams, and the OSS ideas worth absorbing.

## Current priority order
1. `tool_schema_compaction`
2. `api_surface_slimming`
3. `reversible_code_minification`
4. `shell_output_slimming`
5. `token_optimizer_style_instrumentation`

## Best approach by priority

### 1. Tool schema compaction
This is the strongest immediate win when large tool definitions are resent across many turns and clients.

Current state:
- Shared compaction logic already exists in [cutctx/proxy/schema_compress.py](/Users/aryansingh/Documents/Claude/Projects/cutctx/cutctx/proxy/schema_compress.py)
- Tool-schema savings are now attributable to `tool_schema_compaction` rather than being buried inside generic compression
- Dashboard attribution can show tool-schema savings directly

Primary seams:
- [cutctx/proxy/handlers/openai/chat.py](/Users/aryansingh/Documents/Claude/Projects/cutctx/cutctx/proxy/handlers/openai/chat.py)
- [cutctx/proxy/handlers/openai/responses.py](/Users/aryansingh/Documents/Claude/Projects/cutctx/cutctx/proxy/handlers/openai/responses.py)
- [cutctx/proxy/handlers/anthropic.py](/Users/aryansingh/Documents/Claude/Projects/cutctx/cutctx/proxy/handlers/anthropic.py)
- [cutctx/proxy/outcome.py](/Users/aryansingh/Documents/Claude/Projects/cutctx/cutctx/proxy/outcome.py)
- [cutctx/savings/types.py](/Users/aryansingh/Documents/Claude/Projects/cutctx/cutctx/savings/types.py)

### 2. API / MCP surface slimming
This is the best next OSS-inspired priority after tool schemas. It maps well to LAP and OnlyCLI style ideas: expose the smallest useful surface rather than forwarding entire specs.

Current state:
- First-pass tool-surface slimming is now implemented on the OpenAI Chat, OpenAI Responses, and Anthropic request paths
- Savings can be attributed as `api_surface_slimming`
- Heuristics are intentionally conservative and preserve explicitly requested tools

Primary seams:
- [cutctx/proxy/tool_surface.py](/Users/aryansingh/Documents/Claude/Projects/cutctx/cutctx/proxy/tool_surface.py)
- [cutctx/proxy/handlers/openai/chat.py](/Users/aryansingh/Documents/Claude/Projects/cutctx/cutctx/proxy/handlers/openai/chat.py)
- [cutctx/proxy/handlers/openai/responses.py](/Users/aryansingh/Documents/Claude/Projects/cutctx/cutctx/proxy/handlers/openai/responses.py)
- [cutctx/proxy/handlers/anthropic.py](/Users/aryansingh/Documents/Claude/Projects/cutctx/cutctx/proxy/handlers/anthropic.py)

Current toggles:
- `CUTCTX_TOOL_SURFACE_SLIMMING=1`
- `CUTCTX_TOOL_SURFACE_MAX_TOOLS=24`
- `CUTCTX_TOOL_SURFACE_MIN_TOOLS=12`

### 3. Reversible code minification
Deblank-style whitespace and formatting reduction is attractive for large code payloads because it is low-risk and reversible.

Current state:
- Conservative `deblank` minification exists for code-like payloads
- It is only applied behind the tool-result fallback path for obviously code-like or shell-like text
- Ordinary prose is intentionally left untouched

Primary seams:
- file-content tool outputs
- code-heavy retrieval payloads
- transport-safe reversible transforms

Guardrails:
- Preserve stable hashing, retrieval, and diffability
- Keep the reversible mapping exact where reconstruction matters

### 4. Shell tool-output slimming
Lowfat and snip style ideas are still useful, especially for noisy logs, stack traces, and command output.

Current state:
- `snip` trimming now exists for long shell-style output
- It is paired with the code/shell fallback path rather than applied globally
- The current implementation favors safety over maximum aggressiveness

Primary seams:
- tool result interception
- CLI wrappers
- streaming output guards

Best use:
- truncate repetitive sections
- collapse unchanged lines
- summarize long tabular output while preserving retrieval paths

### 5. Token Optimizer style instrumentation
This is a more useful measurement layer than a direct code import target.

Best ideas to absorb:
- ghost-token auditing
- model-misrouting detection
- session scaffolding audits
- repeated-header and repeated-tool overhead reports

Primary seams:
- [cutctx/proxy/cost.py](/Users/aryansingh/Documents/Claude/Projects/cutctx/cutctx/proxy/cost.py)
- [cutctx/proxy/savings_tracker.py](/Users/aryansingh/Documents/Claude/Projects/cutctx/cutctx/proxy/savings_tracker.py)
- dashboard diagnostics surfaces

Current state:
- Request outcomes and savings history can now carry `scaffolding_tokens` and `ghost_tokens`
- Recent-request views surface scaffold and ghost overhead directly
- The current audit focuses on oversized tool-manifest scaffolding, which is the highest-confidence ghost-token source already measured in runtime

## Already absorbed

### Ponytail-style minimal build
Cutctx now has a first-party minimal-build guidance layer that nudges agents to:
- reuse existing code paths
- prefer native platform and stdlib primitives
- avoid speculative abstractions
- stop at the first sufficient solution

Key seams:
- [cutctx/proxy/minimal_build.py](/Users/aryansingh/Documents/Claude/Projects/cutctx/cutctx/proxy/minimal_build.py)
- [cutctx/proxy/handlers/openai/chat.py](/Users/aryansingh/Documents/Claude/Projects/cutctx/cutctx/proxy/handlers/openai/chat.py)
- [cutctx/proxy/handlers/openai/responses.py](/Users/aryansingh/Documents/Claude/Projects/cutctx/cutctx/proxy/handlers/openai/responses.py)
- [cutctx/proxy/handlers/anthropic.py](/Users/aryansingh/Documents/Claude/Projects/cutctx/cutctx/proxy/handlers/anthropic.py)

### Graphify hardening
Graphify should be treated as a reliability and transparency feature, not just an optional extra.

Current improvements:
- `requested` vs `available` vs `active` state is surfaced in stats
- The interceptor can attempt index recovery instead of silently degrading
- Build state and last error are exposed more clearly

Key seams:
- [cutctx/graph/graphify.py](/Users/aryansingh/Documents/Claude/Projects/cutctx/cutctx/graph/graphify.py)
- [cutctx/proxy/interceptors/graph_interceptor.py](/Users/aryansingh/Documents/Claude/Projects/cutctx/cutctx/proxy/interceptors/graph_interceptor.py)
- [cutctx/proxy/server.py](/Users/aryansingh/Documents/Claude/Projects/cutctx/cutctx/proxy/server.py)

### Prompt-cache remediation
Low cache savings are often a cache-stability problem, not a compression problem.

Current improvements:
- Write-only cache sessions are diagnosed explicitly
- The stats dashboard now surfaces more honest cache behavior
- Adaptive freeze behavior helps preserve cacheable prefixes

Key seams:
- [cutctx/cache/prefix_tracker.py](/Users/aryansingh/Documents/Claude/Projects/cutctx/cutctx/cache/prefix_tracker.py)
- [cutctx/proxy/cost.py](/Users/aryansingh/Documents/Claude/Projects/cutctx/cutctx/proxy/cost.py)
- [dashboard/src/pages/Overview.jsx](/Users/aryansingh/Documents/Claude/Projects/cutctx/dashboard/src/pages/Overview.jsx)

## Decision rule
When choosing between a new generic compressor and a feature that removes repeated per-turn scaffolding, prefer the scaffolding-removal feature first.
