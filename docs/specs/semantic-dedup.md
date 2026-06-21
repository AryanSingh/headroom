# Semantic Deduplication for Cutctx

## Problem Statement

In long agent sessions, the same content (files, API responses, tool outputs) is read multiple times across different turns. The compression pipeline currently compresses each occurrence independently, but cannot detect and eliminate redundancy *across* turns.

**Example scenario:**
- Turn 3: User asks to read `auth_middleware.py` → 500 tokens
- Turn 12: User asks a follow-up question → reads `auth_middleware.py` again → 500 tokens (compressed independently to 100)
- Turn 28: User asks another question → reads `auth_middleware.py` again → 500 tokens (compressed independently to 100)

Current result: `auth_middleware.py` stored/transmitted 3 times (300 compressed tokens + overhead).

Desired result: Store once (100 tokens), reference 2 times (2 × 10 tokens ≈ 20 tokens). **Total: ~120 tokens saved, 95%+ reduction on repetitive content.**

## User Stories

1. **As a long-running agent,** I want duplicate content across turns to be deduplicated automatically, **so that** repeated file reads or API queries don't inflate context.

2. **As an eval engineer,** I want semantic deduplication stats to be available, **so that** I can measure token savings on real agent workflows and identify dedup opportunities.

3. **As a prompt engineer using Cutctx,** I want the deduplication to integrate transparently with the CCR (Compress-Cache-Retrieve) system, **so that** if the LLM needs the full content later, it can call `cutctx_retrieve(ref)`.

4. **As a developer debugging a session,** I want short content and system messages to be skipped from dedup, **so that** the overhead of hashing and pointer management doesn't outweigh savings.

## Technical Design

### Overview

Semantic deduplication works at the message level and paragraph level (for longer content). It maintains a rolling hash index of content seen so far in the session. When identical content appears again, it is replaced with a `[cutctx:ref:HASH]` pointer — a marker that the existing CCR system already knows how to retrieve.

### Rolling Hash Approach

**Input:** A list of messages (from the compression pipeline).

**Process:**
1. For each message with `role` in `["user", "assistant", "tool"]` (skip `role=system`):
   - Extract the `content` field
   - If the message contains large tool output (e.g., API results), chunk it at paragraph boundaries
   - Hash each chunk using SHA-256 truncated to 16 hex chars
   - Check the session dedup index:
     - **First occurrence:** Store hash → content mapping, register with CCR if available
     - **Subsequent occurrences:** Replace content with `[cutctx:ref:HASH]`

2. Return deduplicated messages + stats (tokens saved, dedup count, refs created).

### Chunk Granularity

- **Paragraph-level dedup:** For content >200 tokens, split at blank lines (or for code, at semantic boundaries)
- **Message-level dedup:** Entire message content under 200 tokens (skip chunking overhead)
- **Skip short content:** Content under 200 tokens is not worth deduplicating (hash + pointer overhead > savings)

### Pointer Format

`[cutctx:ref:HASH]` where:
- `cutctx:ref:` is a stable marker (matches CCR retrieval protocol)
- `HASH` is the 16-char SHA-256 hex digest of the original content
- The LLM can call `cutctx_retrieve(hash=HASH)` to get the full content back

### Integration with Compression Pipeline

**Entry point:** `SessionDeduplicator.process(messages)` should be called:
- **Early in the pipeline** (after parsing but before content-specific compression)
- **Or at the proxy level** (when collecting messages for CCR tracking)

The deduplicator optionally uses the existing `CompressionStore` to register hash→content mappings (for automatic CCR integration). If CCR is unavailable, it maintains an in-memory dict.

### API Design

```python
from cutctx.dedup import SessionDeduplicator, DeduplicationResult

# Create a session-scoped deduplicator
dedup = SessionDeduplicator()

# Process messages across multiple turns
turn_1_messages = [{"role": "user", "content": "read file.py"}, ...]
result_1 = dedup.process(turn_1_messages)
print(result_1.tokens_saved)  # 0 on first turn (nothing to dedup yet)

turn_2_messages = [{"role": "tool", "content": file_py_content}, ...]  # Same as turn 1
result_2 = dedup.process(turn_2_messages)
print(result_2.tokens_saved)  # High! Content replaced with pointer

# View stats
print(dedup.stats)  # {"dedup_count": 1, "tokens_saved": X, "refs_created": 1, ...}

# Reset for a new session
dedup.reset()
```

### CCR Integration

The deduplicator hooks into the compression store:

```python
dedup = SessionDeduplicator(ccr_store=get_compression_store())

# When content is first seen:
dedup._store_to_ccr(hash_key, original_content)
# This registers the hash→content mapping for later retrieval

# When content is seen again:
# Content is replaced with [cutctx:ref:HASH], and the
# LLM can retrieve via existing cutctx_retrieve() mechanism
```

## Success Metrics

1. **Compression ratio improvement:** 50%+ relative token reduction on sessions with >2 identical content occurrences
2. **Latency budget:** <2ms overhead per message (hashing + dict lookup)
3. **Dedup coverage:** 80%+ of duplicate content detected (measured on test agent workflows)
4. **CCR integration:** 100% of dedup refs correctly retrievable via CCR

## Edge Cases and Handling

### Short Content (<200 tokens)
- **Behavior:** Skip dedup entirely
- **Rationale:** Pointer overhead + hash computation ≈ content size savings
- **Example:** A 50-token tool output repeated 3 times saves 100 tokens deduped but costs 30 tokens for pointers

### Hash Collisions
- **Risk:** SHA-256[:16] has ~280 trillion collision resistance
- **Handling:** Log warning if same hash maps to different content; store both, let CCR sort it out
- **Probability:** Negligible for sessions <1000 messages

### CCR TTL Interaction
- **Scenario:** Content is deduped in turn 5, referenced in turn 15; CCR expires in between
- **Behavior:** The pointer becomes invalid but doesn't break the session (graceful degradation)
- **Mitigation:** Reset session dedup state when CCR cache is flushed

### System Messages
- **Behavior:** Always skip dedup (role=system)
- **Rationale:** System messages are usually unique instructions; deduplicating them could create edge cases with LLM understanding

### Tool Output Structure Variations
- **Challenge:** Same logical data may be formatted differently (JSON vs YAML, different field order)
- **Current scope:** Only detect exact content matches (future: semantic similarity scoring)

## Implementation Checklist

- [ ] `ContentHash` dataclass with hash, token_count, first_seen_turn, content_preview
- [ ] `SessionDeduplicator` class with rolling hash index
- [ ] `_hash_content()` method (SHA-256[:16])
- [ ] `_chunk_message()` method (paragraph-level chunking, min 200 tokens)
- [ ] `_is_system_message()` filter
- [ ] `_should_skip_dedup()` logic (short content, role checks)
- [ ] `process()` method (main entry point)
- [ ] `reset()` method (clear session state)
- [ ] `stats` property (return dedup metrics)
- [ ] CCR store integration (optional)
- [ ] Unit tests covering basic dedup, skip logic, multi-turn, reset, stats
- [ ] Integration test with compression pipeline (if needed)

