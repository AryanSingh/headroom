# crates/cutctx-proxy/src/cache_stabilization/

## Responsibility
Normalizes cache-sensitive request regions and detects structural drift that would reduce upstream prompt-cache reuse.

## Design
Provider-specific passes deterministically sort/normalize tool definitions, add Anthropic cache-control boundaries, and derive OpenAI prompt cache keys. A bounded session LRU stores structural hashes; the drift detector compares hot-zone structure without altering request bytes.

## Flow
Derive provider/session identity -> canonicalize enabled cache metadata/tool arrays -> hash stable system/tools/early-message structure -> compare with prior session hash -> emit drift and cache-hit observability -> forward the resulting request.

## Integration
- Called from generic/provider forwarding before upstream dispatch.
- Uses SHA-256/MD5 canonicalization and reports through `observability/`.
