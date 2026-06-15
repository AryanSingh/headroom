# CutCtx Compression Algorithms

## SmartCrusher
Universal JSON compressor that works on arrays of dicts, nested objects, and mixed types.

**Techniques:**
- Key deduplication across array elements
- Value type inference and normalization
- Schema-aware column extraction
- Opaque blob detection (base64, images, audio)

**Example:**
```json
// Before: 1,200 tokens
[{"id": 1, "name": "Alice", "email": "alice@example.com", "role": "admin"},
 {"id": 2, "name": "Bob", "email": "bob@example.com", "role": "user"}]

// After: 180 tokens (85% savings)
{_cols: [id, name, email, role], _rows: [[1, "Alice", "alice@example.com", "admin"], [2, "Bob", "bob@example.com", "user"]]}
```

## CodeCompressor
AST-aware compression for source code in Python, JavaScript, Go, Rust, Java, and C++.

**Techniques:**
- Import statement summarization
- Comment removal (optional)
- Function signature extraction
- Dead code elimination

## DiffCompressor
Optimized for git diffs and patches.

**Techniques:**
- File header deduplication
- Hunk header compression
- Context line reduction
- Binary diff optimization

## LogCompressor
Specialized for log files and stack traces.

**Techniques:**
- Timestamp normalization
- Repeated pattern detection
- Stack trace compression
- Level-based filtering

## SearchCompressor
Optimized for search results and documentation.

**Techniques:**
- Result deduplication
- Snippet compression
- Metadata stripping
- Relevance scoring

## CacheAligner
Stabilizes message prefixes so provider KV caches actually hit.

**Not a compressor** — reduces cost by enabling cache hits on Anthropic/OpenAI.

## CCR (Content-Addressed Reversible Compression)
Stores originals locally for retrieval on demand.

**How it works:**
1. Content is hashed (BLAKE3 → 16 hex chars)
2. Original stored in local SQLite/Redis
3. Compressed version sent to LLM
4. LLM calls `headroom_retrieve(hash)` when it needs full content
5. Original content returned from local store
