# cutctx/cache/

## Responsibility
Implements provider-aware prompt caching, semantic reuse, compression caching, and cache feedback.

## Design
Provider cache adapters, exact/semantic stores, prefix tracking, dynamic detection, and a backend registry compose independent policies over shared cache primitives. Child backends provide memory or SQLite persistence.

## Flow
Requests derive stable keys/prefixes, consult exact or semantic stores, validate TTL/provider rules, and either reuse results or persist new responses/compressions with feedback.

## Integration
Used by proxy handlers and transforms; integrates with Anthropic/OpenAI/Google cache semantics and `cache/backends` persistence.
