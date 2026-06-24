# Drain3 ML Log Template Mining

Cutctx's Drain3 integration provides **ML-powered log template mining** for repetitive log streams. Instead of treating each log line independently (like the statistical LogCompressor), Drain3 discovers structural patterns — templates — and emits one representative line per template with a count of omitted similar lines. This delivers **10–50× token reduction** on repetitive logs versus the standard sampler's 2–5×.

## Overview

### The Problem with Repetitive Logs

The existing `LogCompressor` (statistical sampler) scores each line by level (ERROR=1.0, WARN=0.5, INFO=0.1), preserves stack traces and summaries, and discards low-importance lines. This works well for structured build outputs (pytest, cargo builds) but is fundamentally limited for **repetitive log streams**:

```
2026-06-24 09:01:03 INFO  Request 7381 from 10.0.0.5 processed in 14ms
2026-06-24 09:01:04 INFO  Request 7382 from 10.0.0.7 processed in 22ms
2026-06-24 09:01:04 INFO  Request 7383 from 10.0.0.5 processed in 9ms
… (800 more identical-pattern lines)
```

The statistical sampler keeps a random sample — the LLM still sees many lines conveying no additional semantic information.

### How Drain3 Solves It

[Drain3](https://github.com/logpai/Drain3) (MIT license) is an online streaming log template miner. It:

1. **Parses each line** by splitting on whitespace and identifying numeric/IP/path tokens as wildcards
2. **Maintains a prefix tree** of depth `sim_depth` (default 4) per line length
3. **Groups lines into clusters** where constant tokens match a **similarity threshold** (default 0.4)
4. **Returns one representative** per cluster annotated with omitted-count and template string

### Drain3 vs LogCompressor

| Aspect | LogCompressor (statistical) | Drain3LogCompressor (ML template) |
|--------|----------------------------|-----------------------------------|
| **Method** | Scores lines by severity, drops low-importance lines | Clusters lines by structural pattern, keeps one per template |
| **Repetitive logs** | Keeps a random sample → still repetitive | Groups identical patterns → single representative + count |
| **Compression** | 2–5× on most logs | 10–50× on repetitive streams |
| **Preserves** | Errors, warnings, stack traces, summaries | One representative per template + template string |
| **Language support** | Agnostic (regex-based severity detection) | Agnostic (whitespace-token structure) |
| **Dependencies** | Rust (built-in) | `drain3>=0.9.11` (opt-in) |

### Architecture

```
ContentRouter
  │
  ├─ drain3_enabled=True? ──── YES ──► Drain3LogCompressor
  │                                          │
  │                                     drain3 installed?
  │                                    ┌────┴────┐
  │                                   YES       NO
  │                                    │         │
  │                                    ▼         ▼
  │                              [Template  [Fallback to
  │                               mining]    LogCompressor]
  │                                    │
  │                                    ▼
  │                          One representative line per cluster
  │                          + "[N more similar lines omitted]"
  │
  └─ drain3_enabled=False ──── NO ───► LogCompressor (standard)
```

### Data Flow

```
raw_text
  │
  ├─ split on "\n"
  │
  ├─ for each line → TemplateMiner.add_log_message()
  │     returns LogCluster (cluster_id, template, size)
  │
  ├─ bucket lines by cluster_id
  │     {cluster_id: [line1, line2, ...]}
  │
  ├─ for each bucket:
  │     select representative = chronologically first line
  │     if bucket has >1 line:
  │       append annotation "[N more similar lines omitted — template: ...]"
  │
  ├─ sort buckets by first-seen line number (preserves log ordering)
  │
  └─ join → compressed_text
```

## Activation

### CLI Flag

```bash
cutctx proxy --drain3

# With custom cluster settings
cutctx proxy --drain3 --drain3-max-clusters 500 --drain3-sim-threshold 0.4
```

### Environment Variables

```bash
HEADROOM_DRAIN3=1 cutctx proxy
HEADROOM_DRAIN3_MAX_CLUSTERS=500 HEADROOM_DRAIN3_SIM_THRESHOLD=0.4 cutctx proxy
```

### Python API

```python
from headroom.transforms.drain3_compressor import (
    Drain3LogCompressor,
    Drain3CompressorConfig,
)

compressor = Drain3LogCompressor(
    Drain3CompressorConfig(max_clusters=500, sim_threshold=0.4)
)
result = compressor.compress(log_text)
print(result.compressed)
print(f"Clusters: {result.clusters_found}")  # e.g. 3
print(f"Ratio: {result.compression_ratio:.2%}")  # e.g. 3.3%
```

## Configuration

### ProxyConfig Fields

| Field | Default | Description |
|-------|---------|-------------|
| `drain3_enabled` | `False` | Enable Drain3 ML log template mining |
| `drain3_max_clusters` | `1000` | Maximum clusters before LRU eviction |
| `drain3_sim_threshold` | `0.4` | Similarity threshold (0.0–1.0), lower = merge more aggressively |

### CLI Options

| Flag | Env Var | Default | Description |
|------|---------|---------|-------------|
| `--drain3` | `HEADROOM_DRAIN3` | — | Enable Drain3 template mining |
| `--drain3-max-clusters` | `HEADROOM_DRAIN3_MAX_CLUSTERS` | `1000` | Max Drain3 clusters (min 10) |
| `--drain3-sim-threshold` | `HEADROOM_DRAIN3_SIM_THRESHOLD` | `0.4` | Similarity threshold 0.0–1.0 |

### Drain3CompressorConfig

```python
from headroom.transforms.drain3_compressor import Drain3CompressorConfig

config = Drain3CompressorConfig(
    max_clusters=1000,        # Max clusters before LRU eviction
    sim_threshold=0.4,        # 0.0–1.0 similarity threshold
    depth=4,                  # Drain3 prefix-tree depth
    max_children=100,         # Max branching of prefix tree
    fallback_on_error=True,   # Silently delegate on error
)
```

### Similarity Threshold Tuning

| Threshold | Behavior | Use Case |
|-----------|----------|----------|
| `0.2` | Very aggressive merging | Highly uniform logs (same format, few variables) |
| `0.4` | Default (Drain3 best-practice) | General purpose |
| `0.6` | Conservative merging | Logs with many variable-field combinations |
| `0.8` | Minimal merging | Near-deduplication, very diverse logs |

## Requirements

### Dependency

```bash
# Install with Drain3 support
pip install cutctx-ai[log-ml]

# Or add to an existing proxy install
pip install "cutctx-ai[proxy,log-ml]"

# Development
uv sync --extra dev --extra log-ml
```

The `log-ml` extra installs `drain3>=0.9.11` (which pulls in `PyYAML`, `jsonpickle`, and `cachetools`).

### Graceful Fallback

When Drain3 is **not installed**, `Drain3LogCompressor` is always constructable — its `compress()` method silently delegates to the standard `LogCompressor`. This means the ContentRouter can unconditionally use the Drain3 code path when the flag is set; the runtime fallback is transparent.

## Usage

### Basic Example

```python
from headroom.transforms.drain3_compressor import Drain3LogCompressor

log = """
2026-06-24 09:00:00 ERROR Database connection failed: timeout after 30s
2026-06-24 09:00:01 INFO  Request 1001 from 10.0.0.1 processed in 14ms
2026-06-24 09:00:02 INFO  Request 1002 from 10.0.0.2 processed in 22ms
2026-06-24 09:00:03 INFO  Request 1003 from 10.0.0.3 processed in 9ms
2026-06-24 09:00:04 WARN  Cache miss for key user_session_abc123
2026-06-24 09:00:05 WARN  Cache miss for key user_session_def456
2026-06-24 09:00:06 ERROR Database connection failed: timeout after 30s
"""

compressor = Drain3LogCompressor()
result = compressor.compress(log)

print(result.compressed)
# 2026-06-24 09:00:00 ERROR Database connection failed: timeout after 30s
#     [1 more similar lines omitted — template: ERROR Database connection failed: timeout after 30s]
# 2026-06-24 09:00:01 INFO  Request 1001 from 10.0.0.1 processed in 14ms
#     [2 more similar lines omitted — template: INFO  Request <*> from <*> processed in <*>ms]
# 2026-06-24 09:00:04 WARN  Cache miss for key user_session_abc123
#     [1 more similar lines omitted — template: WARN  Cache miss for key <*>]

print(f"Lines: {result.original_line_count} → {result.compressed_line_count}")
print(f"Clusters: {result.clusters_found}")
print(f"Ratio: {result.compression_ratio:.2%}")
print(f"Drain3 used: {result.drain3_used}")
```

### Repetitive Log Stream (Server Logs)

```python
# 50 lines, all same pattern with varying IPs/IDs
log = "\n".join(
    f"2026-06-24 09:00:{i:02d} INFO  Request {1000 + i} "
    f"from 10.0.0.{i % 10} processed in {10 + i}ms"
    for i in range(50)
)

result = Drain3LogCompressor().compress(log)
print(f"50 lines → {result.compressed_line_count} lines ({result.compression_ratio:.1%})")
print(result.compressed)
# Expected: ~3 lines (1 representative + 2 annotation lines)
# 2026-06-24 09:00:00 INFO  Request 1000 from 10.0.0.0 processed in 10ms
#     [49 more similar lines omitted — template: INFO  Request <*> from <*> processed in <*>ms]
```

### Mixed Log Content

```python
from headroom.transforms.drain3_compressor import Drain3LogCompressor

# Mix of errors, warnings, and info
log_text = """
[2026-06-24] ERROR Application crashed: OutOfMemoryError
[2026-06-24] INFO  Health check passed
[2026-06-24] INFO  Health check passed
[2026-06-24] WARN  Disk usage at 85%
[2026-06-24] ERROR Application crashed: OutOfMemoryError
[2026-06-24] ERROR Application crashed: OutOfMemoryError
[2026-06-24] INFO  Health check passed
"""

result = Drain3LogCompressor().compress(log_text)
print(result.compressed)
# [2026-06-24] ERROR Application crashed: OutOfMemoryError
#     [2 more similar lines omitted — template: ERROR Application crashed: OutOfMemoryError]
# [2026-06-24] INFO  Health check passed
#     [2 more similar lines omitted — template: INFO  Health check passed]
# [2026-06-24] WARN  Disk usage at 85%
```

### Using with ContentRouter

```python
from headroom.transforms.content_router import ContentRouter, ContentRouterConfig

config = ContentRouterConfig(
    use_drain3=True,
    drain3_max_clusters=500,
    drain3_sim_threshold=0.4,
)
router = ContentRouter(config)
result = router.compress(repetitive_log_text)
print(f"Strategy: {result.strategy_used}")  # CompressionStrategy.LOG
print(f"Ratio: {result.compression_ratio:.2%}")
```

### Thread Safety

The `TemplateMiner` is **not thread-safe** internally. `Drain3LogCompressor` holds a `threading.Lock` around all miner access. Each `ContentRouter` instance owns one compressor, and each worker process has its own router — no cross-process contention.

```python
import threading

compressor = Drain3LogCompressor()
results = []
errors = []

def worker():
    try:
        r = compressor.compress(log_text)
        results.append(r)
    except Exception as e:
        errors.append(e)

threads = [threading.Thread(target=worker) for _ in range(8)]
for t in threads:
    t.start()
for t in threads:
    t.join(timeout=10)

assert len(errors) == 0  # No deadlocks or races
```

## Verification

### Check Availability

```bash
python -c "
from headroom.transforms.drain3_compressor import drain3_available, Drain3LogCompressor
print('drain3_available:', drain3_available())  # True or False
c = Drain3LogCompressor()
print('Compressor constructed OK')
"
```

### Test Compression

```bash
python -c "
from headroom.transforms.drain3_compressor import Drain3LogCompressor

log = '\n'.join(
    f'2026-06-24 09:00:{i:02d} INFO  Request {1000+i} from 10.0.0.{i%10} processed in {10+i}ms'
    for i in range(30)
)
result = Drain3LogCompressor().compress(log)
print(f'Lines in : {result.original_line_count}')
print(f'Lines out: {result.compressed_line_count}')
print(f'Clusters : {result.clusters_found}')
print(f'Ratio    : {result.compression_ratio:.2%}')
print()
print(result.compressed[:400])
"
```

### Run Tests

```bash
pytest tests/test_drain3_compressor.py -v
```

### Verify CLI Flags

```bash
cutctx proxy --help | grep -A3 "drain3"
# Must show: --drain3, --drain3-max-clusters, --drain3-sim-threshold
```

## Troubleshooting

| Problem | Likely Cause | Solution |
|---------|-------------|----------|
| `drain3_available()` returns `False` | Drain3 not installed | `pip install cutctx-ai[log-ml]` |
| Compression ratio is ~1.0 (no compression) | Drain3 unavailable — using fallback | Check `result.drain3_used` — if `False`, install drain3 |
| Too many clusters created | `sim_threshold` too high | Lower `--drain3-sim-threshold` (try 0.3) |
| Too few clusters (over-merging) | `sim_threshold` too low | Raise `--drain3-sim-threshold` (try 0.5) |
| `drain3_max_clusters` hit | More templates than cluster limit | Increase `--drain3-max-clusters` or check log diversity |
| Blocked at startup | Lock held by concurrent compress | Check `drain3_max_clusters` — high values use more RAM |

### Design Notes

- **Fresh miner per call**: `Drain3LogCompressor` creates a new `TemplateMiner` for each `compress()` call (~0.1ms). This prevents cross-request template contamination (a pytest run's templates won't leak into the next webpack build).
- **First-seen line as representative**: The chronologically first line per cluster is kept — it's most likely intact and preserves log ordering.
- **Annotation format**: `[N more similar lines omitted — template: ...]` gives the LLM the template string so it can reason about what was removed.
- **Graceful degradation**: Every exception path falls back to `LogCompressor` — the proxy never returns an error to the user.

---

## See Also

- [Transforms Reference](transforms.md) — Other compression transforms
- [Text Compression](text-compression.md) — SearchCompressor, LogCompressor
- [Compression Overview](compression.md) — Universal compression
