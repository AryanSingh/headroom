# 007. Behavior

**Status:** done

## Proxy Modes

### Passthrough

Cutctx forwards requests without modification.

**Behavior:**
- All requests pass through unchanged
- Response headers may be modified for telemetry
- No compression applied
- Useful for testing or debugging

**Configuration:** `cutctx proxy --no-optimize`

**Request Flow:**
```
Client → Proxy → Provider API → Response
```

---

### Token Mode

Cutctx applies deterministic transforms to requests.

**Behavior:**
- SmartCrusher compresses JSON tool outputs
- CacheAligner stabilizes prefixes
- RollingWindow caps context tokens
- CCR caching enabled
- Token budget enforced

**Configuration:** `CUTCTX_MODE=token` or `cutctx proxy --mode token`

**Request Flow:**
```
Client → Proxy → [SmartCrusher] → [CacheAligner]
         → [RollingWindow] → [CCR Cache]
         → Provider API → Response
```

---

### Cache Mode

Cutctx preserves prior turns where possible to maximize provider prefix-cache hit rate.

**Behavior:**
- Freezes provider-confirmed cached prefixes
- Compresses the mutable tail of the request
- Trades some token savings for better cache stability

**Configuration:** `CUTCTX_MODE=cache` or `cutctx proxy --mode cache`

---

## Session Modes

Session modes control how Cutctx handles context windows.

| Mode | Description | Use Case |
|------|-------------|----------|
| `token` | Prioritize token removal | Default proxy mode |
| `cache` | Preserve prior turns for provider prefix-cache stability | Long Claude/Codex sessions |
| passthrough | Disable optimization with `--no-optimize` | Debugging |

---

## Request Lifecycle

```
1. Request received at proxy endpoint
   │
   ▼
2. Session lookup/creation
   │  - Extract session ID from headers
   │  - Create new session if not found
   │
   ▼
3. Mode determination
   │  - Check CUTCTX_MODE
   │  - Check runtime headers
   │  - Determine active plugins
   │
   ▼
4. Compression pipeline execution
   │  a. Token counting
   │  b. Semantic cache check
   │  c. Content type detection
   │  d. Transform selection
   │  e. Summary compression (if eligible)
   │  f. Token budget enforcement
   │
   ▼
5. Forward to provider API
   │  - Route to correct provider
   │  - Apply API key from config
   │  - Handle timeouts
   │
   ▼
6. Response capture
   │  - Log request/response metadata
   │  - Calculate savings
   │
   ▼
7. Savings calculation
   │  - tokens_before - tokens_after
   │  - percentage = savings / tokens_before
   │
   ▼
8. Telemetry emission
   │  - Prometheus metrics
   │  - Optional tracing
   │
   ▼
9. Response returned to client
      - X-Cutctx-Savings header
      - X-Cutctx-Original-Tokens header
      - X-Cutctx-Compressed-Tokens header
```

---

## Error Handling

| Error Type | HTTP Code | Behavior |
|------------|----------|----------|
| Provider timeout | 504 | Retry up to 3 times with exponential backoff |
| Invalid request | 400 | Return error details in body |
| Compression failure | 500 | Fall back to passthrough mode |
| Provider error | Provider code | Return provider error to client |
| Internal error | 500 | Return 500, log details |
| Rate limited | 429 | Return retry-after header |

**Retry Configuration:**
```python
@dataclass
class RetryConfig:
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
```

---

## Response Headers

Cutctx adds headers to all compressed responses:

```
X-Cutctx-Savings: 0.35
X-Cutctx-Original-Tokens: 8192
X-Cutctx-Compressed-Tokens: 5325
X-Cutctx-Compression-Type: semantic,summary
X-Cutctx-Request-Id: abc123
X-Cutctx-Cache-Hit: false
```

**Header Descriptions:**
- `X-Cutctx-Savings` — Token savings percentage (0.35 = 35%)
- `X-Cutctx-Original-Tokens` — Token count before compression
- `X-Cutctx-Compressed-Tokens` — Token count after compression
- `X-Cutctx-Compression-Type` — Types of compression applied
- `X-Cutctx-Request-Id` — Unique request identifier
- `X-Cutctx-Cache-Hit` — Whether result was from cache

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0-draft | 2026-04-16 | Initial behavior document |
