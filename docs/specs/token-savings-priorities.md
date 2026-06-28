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
This is the strongest immediate win because large tool definitions are resent across many turns and many clients.

Current state:
- Shared compaction logic already exists in [cutctx/proxy/schema_compress.py](/Users/aryansingh/Documents/Claude/Projects/headroom/cutctx/proxy/schema_compress.py)
- Tool-schema savings are now attributable as `tool_schema_compaction` rather than being fully buried inside generic compression
- Dashboard attribution can show tool-schema savings directly

Primary seams:
- [cutctx/proxy/handlers/openai/chat.py](/Users/aryansingh/Documents/Claude/Projects/headroom/cutctx/proxy/handlers/openai/chat.py)
- [cutctx/proxy/handlers/openai/responses.py](/Users/aryansingh/Documents/Claude/Projects/headroom/cutctx/proxy/handlers/openai/responses.py)
- [cutctx/proxy/handlers/anthropic.py](/Users/aryansingh/Documents/Claude/Projects/headroom/cutctx/proxy/handlers/anthropic.py)
- [cutctx/proxy/outcome.py](/Users/aryansingh/Documents/Claude/Projects/headroom/cutctx/proxy/outcome.py)
- [cutctx/savings/types.py](/Users/aryansingh/Documents/Claude/Projects/headroom/cutctx/savings/types.py)

Success condition:
- repeated tool-calling sessions show a visible `tool_schema_compaction` savings row
- recent requests no longer hide schema wins inside a generic bucket

### 2. API and MCP surface slimming
This is the best next OSS-inspired priority after tool schemas. It maps well to LAP and OnlyCLI style ideas: expose the smallest useful surface rather than forwarding entire specs.

Current state:
- first-pass tool-surface slimming is now implemented on OpenAI Chat, OpenAI Responses, and Anthropic request paths
- the slimming pass is opt-in and only activates on oversized tool lists
- savings can be attributed as `api_surface_slimming`

Primary seams:
- MCP exposure and tool forwarding layers
- OpenAPI-to-agent translation
- CLI-to-agent translation
- tool registration middleware

Candidate tactics:
- send only the subset of endpoints a client can actually call
- trim argument docs and examples once a tool is already known
- progressively reveal schema details only after first use

Current toggles:
- `CUTCTX_TOOL_SURFACE_SLIMMING=1`
- `CUTCTX_TOOL_SURFACE_MAX_TOOLS=24`
- `CUTCTX_TOOL_SURFACE_MIN_TOOLS=12`

### 3. Reversible code minification
Deblank-style whitespace and formatting reduction is attractive for large code payloads because it is low-risk and reversible.

Primary seams:
- file-content tool outputs
- code-heavy retrieval payloads
- transport-safe reversible transforms

Guardrails:
- preserve stable hashing for retrieval and diffability
- keep a reversible mapping when exact reconstruction matters

### 4. Shell and tool-output slimming
lowfat and snip style ideas are still useful, especially for noisy logs, stack traces, and command output.

Primary seams:
- tool result interception
- CLI wrappers
- streaming output guards

Best use:
- truncate repetitive sections
- collapse unchanged lines
- summarize long tabular output while preserving retrieval paths

### 5. Token Optimizer style instrumentation
This is more useful as a measurement layer than as a code import target.

Best ideas to absorb:
- ghost-token auditing
- model-misrouting detection
- session scaffolding audits
- repeated-header and repeated-tool overhead reports

Primary seams:
- [cutctx/proxy/cost.py](/Users/aryansingh/Documents/Claude/Projects/headroom/cutctx/proxy/cost.py)
- [cutctx/proxy/savings_tracker.py](/Users/aryansingh/Documents/Claude/Projects/headroom/cutctx/proxy/savings_tracker.py)
- dashboard diagnostics surfaces

## Already absorbed

### Ponytail-style minimal build
Cutctx now has a first-party minimal-build guidance layer that nudges agents to:
- reuse existing code paths
- prefer native platform and stdlib primitives
- avoid speculative abstractions
- stop at the first sufficient solution

Key seams:
- [cutctx/proxy/minimal_build.py](/Users/aryansingh/Documents/Claude/Projects/headroom/cutctx/proxy/minimal_build.py)
- [cutctx/proxy/server.py](/Users/aryansingh/Documents/Claude/Projects/headroom/cutctx/proxy/server.py)

### Graphify hardening
Graphify should be treated as a reliability and transparency feature, not just an optional extra.

Current improvements:
- requested vs available vs active state surfaced in stats
- interceptor can attempt index recovery instead of silently degrading
- build state and last error are exposed more clearly

Key seams:
- [cutctx/graph/graphify.py](/Users/aryansingh/Documents/Claude/Projects/headroom/cutctx/graph/graphify.py)
- [cutctx/proxy/interceptors/graph_interceptor.py](/Users/aryansingh/Documents/Claude/Projects/headroom/cutctx/proxy/interceptors/graph_interceptor.py)
- [cutctx/proxy/server.py](/Users/aryansingh/Documents/Claude/Projects/headroom/cutctx/proxy/server.py)

### Prompt-cache remediation
Low cache savings are often a cache-stability problem, not a compression problem.

Current improvements:
- write-only cache sessions are diagnosed explicitly
- stats and dashboard now surface more honest cache behavior
- adaptive freeze behavior helps preserve cacheable prefixes

Key seams:
- [cutctx/cache/prefix_tracker.py](/Users/aryansingh/Documents/Claude/Projects/headroom/cutctx/cache/prefix_tracker.py)
- [cutctx/proxy/cost.py](/Users/aryansingh/Documents/Claude/Projects/headroom/cutctx/proxy/cost.py)
- [dashboard/src/pages/Overview.jsx](/Users/aryansingh/Documents/Claude/Projects/headroom/dashboard/src/pages/Overview.jsx)

## Decision rule
When choosing between a new generic compressor and a feature that removes repeated per-turn scaffolding, prefer the scaffolding-removal feature first.
