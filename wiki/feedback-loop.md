# Feedback Loop (Data Flywheel)

Cutctx learns from compression patterns across sessions to optimize future compressions. When content is retrieved via CCR (Compress-Cache-Retrieve), this triggers a feedback signal that adjusts compression aggressiveness for that content type in future requests—creating a self-improving compressor per workspace.

## Overview

### Problem

Standard compression uses static ratios (e.g., "compress everything to 50%"). But optimal compression varies by context and content type:
- Code snippets can tolerate aggressive compression (symbols are recoverable)
- Error messages need to preserve key details
- JSON arrays can be deeply compressed with CCR fallback

Without feedback, the proxy applies the same ratio to everything and occasionally over-compresses, forcing costly retrievals.

### Feedback Loop Solves This

The feedback loop tracks two signals per content type:
1. **Compression events** — how aggressively each content type was compressed
2. **Retrieval events** — how often content of that type was retrieved (indicating over-compression)

These feed into a **per-workspace `CompressionProfile`** that learns:
- If a content type has >50% retrieval rate → compress less aggressively
- If a content type has <20% retrieval rate → current compression is good
- Recommended compression ratios update after each session

The result: the more you use Cutctx in a codebase, the better it gets at compressing that codebase.

### How It Differs from Static Compression

| Aspect | Feedback Loop | Static Compression |
|--------|---------------|-------------------|
| **Learns from** | Actual retrieval patterns | Fixed configuration |
| **Optimization** | Per-workspace, per-content-type | Global defaults |
| **Adaptation** | Improves over time | Same across all projects |
| **Scope** | Workspace-local (not shared) | Same everywhere |

---

## Mechanism

### The Flow

```
Session 1: Initial compression
├─ Load workspace profile (empty on first run)
├─ Apply default ratios (e.g., 0.5 for all content types)
├─ Compress messages
├─ LLM calls cutctx_retrieve for json_array content
└─ CCR handler signals retrieval → profile.update_from_ccr_retrieval("json_array")

Profile Update:
├─ Increment json_array.total_retrievals
├─ Compute retrieval_rate: retrievals / total_compressions
├─ Apply heuristic: if retrieval_rate > 0.5, increase recommended_ratio by 0.2
├─ Clamp to [0.0, 0.95] (security cap)
└─ Save profile to ~/.cutctx/profiles/{workspace_hash}.json

Session 2: Improved compression
├─ Load workspace profile (now has json_array stats)
├─ ContentRouter reads profile.recommended_ratio for each content type
├─ Applies adjusted bias_multiplier (e.g., json_array now uses 0.7 instead of 0.5)
├─ Fewer json_array retrievals expected
└─ Profile updates again with new retrieval rate
```

### Workspace Identity

Profiles are **per-workspace**, identified by:
1. Git remote origin URL (if a git repo)
2. Directory path (if not a git repo)

Hashed to 16 hex characters and stored at `~/.cutctx/profiles/{hash}.json`. Each workspace has exactly one profile; profiles are not shared between users or machines.

### CompressionProfile Structure

The profile tracks per-content-type statistics (defined in `cutctx/profiles.py`):

```python
ContentTypeStats:
  content_type: str                    # e.g., "json_array", "source_code"
  sessions_seen: int                   # How many sessions touched this type
  total_compressions: int              # Total compression events
  total_retrievals: int                # How many were retrieved via CCR
  avg_compression_ratio: float         # Running average of compression ratio
  retrieval_rate: float                # retrievals / total_compressions
  recommended_ratio: float             # Target for future sessions [0.0, 0.95]
  last_session_timestamp: float        # When last seen
```

### Recommendation Heuristic

The `_update_recommendation()` method adjusts `recommended_ratio` based on retrieval rate:

- **≥50% retrieval rate** (over-compressed): Increase ratio by 0.2 → compress less
- **20–50% retrieval rate** (somewhat over-compressed): Increase ratio by 0.1
- **<20% retrieval rate** (good compression): Use actual avg_compression_ratio

Final ratio is clamped to `[0.0, 0.95]` (0.95 cap prevents disabling compression entirely).

### Integration with ContentRouter

When ContentRouter initializes, it reads the workspace profile and applies learned `recommended_ratio` values as `bias_multiplier` overrides for each content type. This adjusts compression aggressiveness without changing the algorithm.

Example flow:
1. Profile says json_array has retrieval_rate=0.6 → recommended_ratio=0.7
2. ContentRouter sets bias_multiplier=0.7 for json_array transformers
3. json_array content now uses more gentle compression ratios
4. Over time, retrieval_rate for json_array drops

---

## CLI Usage

### Show Profile

```bash
cutctx profile show
```

Displays a human-readable summary of the current workspace's learned compression patterns:

```
Compression Profile — Workspace Feedback Loop
──────────────────────────────────────────────
  Workspace:            a1b2c3d4e5f6g7h8
  Content types:        5
  Total compressions:   247
  Total retrievals:     31
  Overall retrieval rate: 12.6%

Per-Content-Type Stats:
  Content Type             Sessions Compressions Retrieval Recommended
  source_code                   8           52      3.8%       0.48
  json_array                    6           89     15.7%       0.65
  build_output                  7           76      8.1%       0.52
  git_diff                       5           18      0.0%       0.42
  plain_text                     4           12      8.3%       0.50
```

### Output as JSON

```bash
cutctx profile show --json
```

Returns the full profile data structure:

```json
{
  "workspace_hash": "a1b2c3d4e5f6g7h8",
  "total_content_types": 5,
  "total_compressions": 247,
  "total_retrievals": 31,
  "overall_retrieval_rate": 0.126,
  "stats_by_type": {
    "source_code": {
      "sessions_seen": 8,
      "total_compressions": 52,
      "retrieval_rate": 0.038,
      "avg_compression_ratio": 0.48,
      "recommended_ratio": 0.48
    },
    "json_array": {
      "sessions_seen": 6,
      "total_compressions": 89,
      "retrieval_rate": 0.157,
      "avg_compression_ratio": 0.58,
      "recommended_ratio": 0.65
    },
    ...
  }
}
```

---

## How to See It in Action

### Record a Session with High Retrieval

1. Run the proxy with CCR enabled:
   ```bash
   cutctx proxy --ccr
   ```

2. Make requests that trigger retrievals (e.g., work with large JSON structures or compressed code):
   ```bash
   curl http://localhost:8000/v1/messages -H "Content-Type: application/json" \
     -d '{"messages": [{"role": "user", "content": "...large json..."}]}'
   ```

3. If the LLM calls `cutctx_retrieve`, that's a retrieval signal.

### Check Profile Evolution

Run several sessions, then check the profile:

```bash
cutctx profile show
```

After session 1, you might see:
```
json_array: compressions=5, retrievals=2 (40% rate) → recommended_ratio=0.6
```

After session 3 (with adjusted compression):
```
json_array: compressions=15, retrievals=1 (6.7% rate) → recommended_ratio=0.48
```

The retrieval rate drops because the profile learned to compress json_array less aggressively.

---

## Privacy & Scope

- **Per-workspace, not shared**: Profiles live in `~/.cutctx/profiles/` on each machine and are not synced or uploaded to any server.
- **Deterministic workspace identity**: Same git remote + path always hashes to the same ID, so switching between machines with the same workspace re-uses the same profile.
- **No content stored**: The profile stores only statistics (compression ratios, retrieval counts), never the original or compressed content.
- **Opt-in**: Profiles are built automatically when CCR is enabled; they don't affect compression without explicit use of the feedback mechanism.

---

## Limitations & Future Work

1. **Cold-start bias**: New workspaces start with default ratios; it takes several sessions to learn patterns. Large, diverse codebases may need >10 sessions to stabilize recommendations.
2. **No periodic cleanup**: Old timestamp entries are kept indefinitely; very old statistics persist in the profile.
3. **Single-machine scope**: Profiles don't sync across team members or machines. Each developer's machine learns independently.
4. **No A/B testing**: The heuristic for adjusting ratios is fixed; there's no way to experiment with different adjustment strategies per workspace.

---

## Related

- **CCR (Compress-Cache-Retrieve)** — the retrieval mechanism that signals over-compression
- **ContentRouter** — applies learned recommendations to future requests
- **Telemetry (TOIN)** — also records retrieval events for analytics
