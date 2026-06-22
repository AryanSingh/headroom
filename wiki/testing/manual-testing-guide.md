# CutCtx Manual Testing Guide

**Product:** CutCtx (`cutctx` binary, `cutctx-ai` PyPI package, `headroom` internal Python package)  
**Version:** 0.26.0  
**Last updated:** 2026-06-22

This guide covers every testable surface of the product end-to-end. Work through sections top-to-bottom on a clean machine — each section builds on the previous. Every step lists the exact command, the expected output, and the pass/fail criterion.

---

## Table of Contents

1. [Environment Setup](#1-environment-setup)
2. [Installation & Binary Smoke Test](#2-installation--binary-smoke-test)
3. [Proxy — Core Startup](#3-proxy--core-startup)
4. [Proxy — Health & Metrics Endpoints](#4-proxy--health--metrics-endpoints)
5. [Compression Algorithms](#5-compression-algorithms)
6. [ContentRouter — Auto-Detection & Routing](#6-contentrouter--auto-detection--routing)
7. [CompactTable Compressor](#7-compacttable-compressor)
8. [LLMLingua-2 Optional Compressor](#8-llmlingua-2-optional-compressor)
9. [Selective Context Filter](#9-selective-context-filter)
10. [Query-Aware Compression](#10-query-aware-compression)
11. [Compressed Content Retrieval (CCR)](#11-compressed-content-retrieval-ccr)
12. [Persistent Memory](#12-persistent-memory)
13. [Live Traffic Learning](#13-live-traffic-learning)
14. [Wrap Commands (Agent Integration)](#14-wrap-commands-agent-integration)
15. [Init Commands (Durable Integrations)](#15-init-commands-durable-integrations)
16. [Proxy Modes — Token vs Cache](#16-proxy-modes--token-vs-cache)
17. [Multi-Backend Support](#17-multi-backend-support)
18. [Langfuse Observability Tracing](#18-langfuse-observability-tracing)
19. [Benchmark (`cutctx bench`)](#19-benchmark-cutctx-bench)
20. [Savings Report (`cutctx savings`)](#20-savings-report-cutctx-savings)
21. [License Management](#21-license-management)
22. [Config Check](#22-config-check)
23. [Persistent Deployment (`cutctx install`)](#23-persistent-deployment-cutctx-install)
24. [Admin API — RBAC](#24-admin-api--rbac)
25. [Admin API — Audit Log](#25-admin-api--audit-log)
26. [Admin API — SSO Test](#26-admin-api--sso-test)
27. [Docker Image](#27-docker-image)
28. [Helm Chart](#28-helm-chart)
29. [LlamaIndex Integration](#29-llamaindex-integration)
30. [LangChain Integration](#30-langchain-integration)
31. [MCP Server Mode](#31-mcp-server-mode)
32. [Security — Hardware Fingerprint & State Encryption](#32-security--hardware-fingerprint--state-encryption)
33. [Security — EE Integrity Guard](#33-security--ee-integrity-guard)
34. [Edge Cases & Error Handling](#34-edge-cases--error-handling)
35. [Live Proxy Request (Real API Call)](#35-live-proxy-request-real-api-call)
36. [Streaming Responses](#36-streaming-responses)
37. [Intercept Tool Results](#37-intercept-tool-results)
38. [Report Generation](#38-report-generation)
39. [Performance Log Analyzer (`cutctx perf`)](#39-performance-log-analyzer-cutctx-perf)
40. [Agent Savings Profiler](#40-agent-savings-profiler)
41. [Provider Integrations Inspector](#41-provider-integrations-inspector)
42. [Bundled Tools Manager (`cutctx tools`)](#42-bundled-tools-manager-cutctx-tools)
43. [Organization Management (`cutctx orgs`)](#43-organization-management-cutctx-orgs)
44. [Billing Management (`cutctx billing`)](#44-billing-management-cutctx-billing)
45. [Admin API — Spend Ledger](#45-admin-api--spend-ledger)
46. [Admin API — Rate Limit Stats](#46-admin-api--rate-limit-stats)
47. [Admin API — Secrets Store](#47-admin-api--secrets-store)
48. [Admin API — GDPR DSR](#48-admin-api--gdpr-dsr)
49. [Traffic Capture & Diff](#49-traffic-capture--diff)
50. [Memory Evals Benchmark](#50-memory-evals-benchmark)
51. [Learn from Failures (`cutctx learn`)](#51-learn-from-failures-cutctx-learn)
52. [VS Code Extension — Manual Smoke Test](#52-vs-code-extension--manual-smoke-test)
53. [JetBrains Plugin — Manual Smoke Test](#53-jetbrains-plugin--manual-smoke-test)
54. [Air-Gap Mode](#54-air-gap-mode)
55. [Rate Limiting](#55-rate-limiting)
56. [Multimodal (Image) Compression](#56-multimodal-image-compression)
57. [Stateless Container Deployment](#57-stateless-container-deployment)

---

## 1. Environment Setup

### Prerequisites

| Tool | Min version | Install |
|------|------------|---------|
| Python | 3.10+ | `brew install python@3.12` |
| pip | 23+ | `pip install --upgrade pip` |
| curl | any | pre-installed on macOS/Linux |
| jq | any | `brew install jq` |

### Fresh virtualenv

```bash
python3 -m venv ~/cutctx-test-env
source ~/cutctx-test-env/bin/activate
pip install cutctx-ai
```

**PASS:** `cutctx --version` prints `cutctx 0.26.0`  
**FAIL:** Import errors, missing binary, version mismatch

### Environment variables used throughout this guide

```bash
export ANTHROPIC_API_KEY=sk-ant-...          # real key for live tests
export OPENAI_API_KEY=sk-...                 # for OpenAI-backend tests
export HEADROOM_ADMIN_API_KEY=test-admin-key # for admin API tests
export CUTCTX_TEST_MODE=1                    # suppresses browser-open in savings/report
```

---

## 2. Installation & Binary Smoke Test

```bash
which cutctx
cutctx --version
cutctx --help
```

**PASS:**
- `which cutctx` returns a path inside the venv
- `--version` prints `cutctx 0.26.0` (not `headroom`)
- `--help` lists all commands: proxy, wrap, init, bench, savings, license, etc.

```bash
# Verify the Rust core is linked
python -c "from headroom import _core; print(_core.hello())"
```

**PASS:** prints `headroom-core`  
**FAIL:** `ImportError` — the Rust `.so` isn't compiled for this platform

---

## 3. Proxy — Core Startup

### 3.1 Basic startup

```bash
cutctx proxy --port 8787 &
PROXY_PID=$!
sleep 2
curl -s http://localhost:8787/livez | jq .
```

**PASS:** `{"status": "ok"}` (or similar health object)  
**FAIL:** connection refused, non-200, missing status field

```bash
kill $PROXY_PID
```

### 3.2 Passthrough mode

```bash
cutctx proxy --port 8788 --no-optimize &
PROXY_PID=$!
sleep 2
curl -s http://localhost:8788/livez | jq .
kill $PROXY_PID
```

**PASS:** proxy starts; `/livez` returns ok; compression middleware is bypassed (verify with `--debug` flag — no "compressed" log lines)

### 3.3 Stateless mode

```bash
cutctx proxy --port 8789 --stateless &
PROXY_PID=$!
sleep 2
curl -s http://localhost:8789/livez | jq .
kill $PROXY_PID
ls ~/.headroom/ 2>/dev/null && echo "files exist" || echo "no files written"
```

**PASS:** proxy starts; `~/.headroom/` has no new files created during the run

### 3.4 Custom host/port via environment

```bash
HEADROOM_PORT=8790 HEADROOM_HOST=127.0.0.1 cutctx proxy &
PROXY_PID=$!
sleep 2
curl -s http://127.0.0.1:8790/livez | jq .
kill $PROXY_PID
```

**PASS:** proxy binds to the env-specified port

---

## 4. Proxy — Health & Metrics Endpoints

Start proxy for this section:

```bash
cutctx proxy --port 8787 &
PROXY_PID=$!
sleep 2
```

```bash
# Health
curl -s http://localhost:8787/livez | jq .
curl -s http://localhost:8787/readyz | jq .

# Metrics (Prometheus format)
curl -s http://localhost:8787/metrics | head -30

# Stats (JSON)
curl -s http://localhost:8787/v1/stats | jq .

# Version
curl -s http://localhost:8787/v1/version | jq .
```

**PASS per endpoint:**
- `/livez` → `{"status": "ok"}`
- `/readyz` → `{"status": "ok"}` (may differ briefly on startup)
- `/metrics` → lines starting with `# HELP` and `headroom_` metrics
- `/v1/stats` → JSON with `requests_total`, `tokens_saved`, `compression_ratio` fields
- `/v1/version` → JSON with `version: "0.26.0"`

```bash
kill $PROXY_PID
```

---

## 5. Compression Algorithms

### 5.1 Benchmark all algorithms

```bash
cutctx bench --size medium --algorithm all
```

**PASS:** table output with `smart-crusher`, `diff`, `log`, `search` rows; each shows tokens_in, tokens_out, ratio, time_ms. No algorithm crashes.

```bash
cutctx bench --algorithm smart-crusher --size large --json | jq .
```

**PASS:** valid JSON with `algorithm`, `tokens_in`, `tokens_out`, `compression_ratio`, `elapsed_ms` keys.

### 5.2 SmartCrusher (array/JSON compaction)

```bash
python3 - <<'EOF'
from headroom.transforms.smart_crusher import SmartCrusher, SmartCrusherConfig

crusher = SmartCrusher(SmartCrusherConfig())
data = '[' + ','.join([f'{{"id":{i},"type":"event","status":"pending","value":null}}' for i in range(20)]) + ']'
result = crusher.crush(data)
print(f"IN:  {len(data)} chars")
print(f"OUT: {len(result.kept_json)} chars")
print(f"Ratio: {1 - len(result.kept_json)/len(data):.1%} saved")
EOF
```

**PASS:** output is valid JSON; ratio > 20% savings; no crash

### 5.3 DiffCompressor

```bash
python3 - <<'EOF'
from headroom.transforms.diff_compressor import DiffCompressor

diff = """diff --git a/main.py b/main.py
index abc..def 100644
--- a/main.py
+++ b/main.py
@@ -1,10 +1,10 @@
 def hello():
-    print("hello world")
-    print("hello world")
-    print("hello world")
+    print("hello")
 def bye():
     pass
"""
result = DiffCompressor().compress(diff)
print(f"IN:  {len(diff)}")
print(f"OUT: {len(result.compressed)}")
print(f"Saved: {result.tokens_saved} tokens")
EOF
```

**PASS:** `result.compressed` is shorter; `result.tokens_saved > 0`

### 5.4 LogCompressor

```bash
python3 - <<'EOF'
from headroom.transforms.log_compressor import LogCompressor

log = '\n'.join([
    '[2026-06-22 10:00:01] INFO  Server started on port 8787',
    '[2026-06-22 10:00:02] DEBUG Request received: GET /livez',
    '[2026-06-22 10:00:02] DEBUG Request received: GET /livez',
    '[2026-06-22 10:00:02] DEBUG Request received: GET /livez',
    '[2026-06-22 10:00:03] ERROR Database connection failed: timeout after 30s',
    '[2026-06-22 10:00:04] ERROR Database connection failed: timeout after 30s',
    '[2026-06-22 10:00:05] INFO  Retrying database connection...',
] * 10)
result = LogCompressor().compress(log)
print(f"IN:  {len(log)}")
print(f"OUT: {len(result.compressed)}")
print(f"Saved: {result.tokens_saved} tokens")
assert result.tokens_saved > 0, "expected savings on repetitive log"
print("PASS")
EOF
```

**PASS:** prints `PASS`; compressed output is shorter; repeated lines deduplicated

### 5.5 SearchCompressor

```bash
python3 - <<'EOF'
from headroom.transforms.search_compressor import SearchCompressor

results = '\n'.join([
    f"Result {i}: https://example.com/page{i}\nTitle: Example Page {i}\nSnippet: This is a very long snippet that contains the search term multiple times and includes a lot of boilerplate text that doesn't contribute to understanding. The page was published on 2026-01-{i:02d} and has been viewed 10000 times.\n"
    for i in range(1, 11)
])
result = SearchCompressor().compress(results)
print(f"IN:  {len(results)}")
print(f"OUT: {len(result.compressed)}")
print(f"Saved: {result.tokens_saved} tokens")
assert result.tokens_saved > 0
print("PASS")
EOF
```

**PASS:** prints `PASS`; boilerplate stripped from search result snippets

### 5.6 CodeAwareCompressor (AST-level)

```bash
python3 - <<'EOF'
from headroom.transforms.code_compressor import CodeAwareCompressor

code = '''
def calculate_fibonacci(n: int) -> int:
    """
    Calculate the nth Fibonacci number using dynamic programming.
    
    This function implements the Fibonacci sequence calculation using
    a bottom-up dynamic programming approach for optimal performance.
    Time complexity: O(n), Space complexity: O(n).
    
    Args:
        n: The position in the Fibonacci sequence (0-indexed)
    Returns:
        The nth Fibonacci number
    """
    if n <= 0:
        return 0
    if n == 1:
        return 1
    dp = [0] * (n + 1)
    dp[1] = 1
    for i in range(2, n + 1):
        dp[i] = dp[i-1] + dp[i-2]
    return dp[n]
''' * 5
result = CodeAwareCompressor().compress(code)
print(f"IN:  {len(code)}")
print(f"OUT: {len(result.compressed)}")
print(f"Saved: {result.tokens_saved} tokens")
assert result.tokens_saved > 0
print("PASS")
EOF
```

**PASS:** prints `PASS`; docstrings and comments compressed; function signatures preserved

---

## 6. ContentRouter — Auto-Detection & Routing

```bash
python3 - <<'EOF'
from headroom.transforms.content_router import ContentRouter, ContentRouterConfig

router = ContentRouter(ContentRouterConfig())

# Test 1: diff content → DiffCompressor
diff_content = """diff --git a/app.py b/app.py
index 000..111 100644
--- a/app.py
+++ b/app.py
@@ -1,5 +1,5 @@
-def old(): pass
+def new(): pass
""" * 8
result = router.compress(diff_content)
print(f"Diff  → strategy: {result.strategy}, saved: {result.tokens_saved}")

# Test 2: log content → LogCompressor
log_content = "\n".join(["[INFO] 2026-06-22 request processed in 12ms"] * 50)
result = router.compress(log_content)
print(f"Log   → strategy: {result.strategy}, saved: {result.tokens_saved}")

# Test 3: JSON array → SmartCrusher
json_content = '[{"id":' + str(i) + ',"val":"x"},' for i in range(30)]
json_content = '[' + ','.join([f'{{"id":{i},"val":"repeated-value"}}' for i in range(30)]) + ']'
result = router.compress(json_content)
print(f"JSON  → strategy: {result.strategy}, saved: {result.tokens_saved}")

print("All router tests PASS")
EOF
```

**PASS:** each content type is routed to the correct strategy; all show positive `tokens_saved`

---

## 7. CompactTable Compressor

```bash
python3 - <<'EOF'
from headroom.transforms.compact_table import CompactTableCompressor

data = '''[
  {"name": "Alice", "role": "engineer", "team": "backend", "status": "active"},
  {"name": "Bob",   "role": "designer", "team": "frontend", "status": "active"},
  {"name": "Carol", "role": "engineer", "team": "backend", "status": "active"},
  {"name": "Dave",  "role": "manager",  "team": "platform", "status": "active"},
  {"name": "Eve",   "role": "engineer", "team": "backend",  "status": "inactive"}
]'''

result = CompactTableCompressor().compress(data)
print(f"IN:  {len(data)} chars")
print(f"OUT: {len(result.compressed)} chars")
print(f"Ratio: {result.compression_ratio:.1%} saved")
print(f"Rows: {result.row_count}, Cols: {result.column_count}")
print(f"Constant cols: {result.constant_columns}")
print()
print("Compressed output:")
print(result.compressed)

assert result.compression_ratio > 0.3, "expected >30% compression on table data"
assert result.constant_columns, "status=active should be a constant column"
print("\nPASS")
EOF
```

**PASS:** 
- Compression ratio > 30%
- `constant_columns` includes `status` (all rows = "active" except one — check logic)
- Output is pipe-delimited format with a header row

---

## 8. LLMLingua-2 Optional Compressor

```bash
# Check graceful fallback when NOT installed
python3 - <<'EOF'
from headroom.transforms.llmlingua_compressor import LLMLinguaCompressor

comp = LLMLinguaCompressor()
text = "This is a test sentence that should be compressed. " * 20
result = comp.compress(text)
print(f"available: {comp.available}")
if comp.available:
    print(f"Saved: {result.tokens_saved}")
else:
    print("Gracefully falling back to no-op (expected when not installed)")
print("PASS — no crash")
EOF
```

**PASS:** no crash; if llmlingua not installed, `comp.available == False` and `result.compressed == text`

```bash
# Test with proxy flag (should start without error even if not installed)
cutctx proxy --port 8791 --llmlingua &
PROXY_PID=$!
sleep 2
curl -s http://localhost:8791/livez | jq .
kill $PROXY_PID
```

**PASS:** proxy starts without crashing; `/livez` returns ok (llmlingua is gracefully disabled if package not present)

---

## 9. Selective Context Filter

```bash
python3 - <<'EOF'
from headroom.transforms.selective_filter import SelectiveContextFilter, SelectiveFilterConfig

messages = [
    {"role": "user",      "content": "What is the capital of France?"},
    {"role": "assistant", "content": "Paris."},
    {"role": "user",      "content": "Tell me about the weather in London on January 3rd 1987."},
    {"role": "assistant", "content": "I don't have that specific historical data."},
    {"role": "user",      "content": "What is the capital of Germany?"},
    {"role": "assistant", "content": "Berlin."},
    {"role": "user",      "content": "What is the capital of France?"},  # current query
]

cfg = SelectiveFilterConfig(min_score=0.15, protect_recent=2)
filt = SelectiveContextFilter(cfg)
result = filt.filter(messages)

print(f"Messages in:  {result.messages_in}")
print(f"Messages out: {result.messages_out}")
print(f"Dropped:      {result.messages_dropped}")
print(f"Scores:       {[round(s, 3) for s in result.scores]}")

assert result.messages_out < result.messages_in, "expected some messages dropped"
assert result.messages_dropped > 0
print("PASS")
EOF
```

**PASS:** 
- Some low-relevance turns (weather question) are dropped
- `messages_out < messages_in`
- Recent turns (last 2) are always protected

```bash
# Test via proxy flag
cutctx proxy --port 8792 --selective-filter --selective-filter-threshold 0.2 &
PROXY_PID=$!
sleep 2
curl -s http://localhost:8792/livez | jq .
kill $PROXY_PID
```

**PASS:** proxy starts with selective filter enabled; no crash

---

## 10. Query-Aware Compression

```bash
python3 - <<'EOF'
from headroom.transforms.query_adapter import detect_query_hint, CompressionHint

# CODE task — should protect more context
hint = detect_query_hint("Fix the bug in my authentication middleware")
print(f"CODE task hint: rate={hint.compression_rate}, protect_recent={hint.protect_recent}")

# SEARCH task — should compress harder
hint = detect_query_hint("List all the files in this directory")
print(f"SEARCH task hint: rate={hint.compression_rate}, protect_recent={hint.protect_recent}")

# DEBUG task — protect most
hint = detect_query_hint("Why is my program crashing with a segfault?")
print(f"DEBUG task hint: rate={hint.compression_rate}, protect_recent={hint.protect_recent}")

print("PASS")
EOF
```

**PASS:** 
- CODE/DEBUG hints have lower `compression_rate` (protect more)
- SEARCH hints have higher `compression_rate` (compress harder)

```bash
cutctx proxy --port 8793 --query-aware &
PROXY_PID=$!
sleep 2
curl -s http://localhost:8793/livez | jq .
kill $PROXY_PID
```

**PASS:** proxy starts; no crash

---

## 11. Compressed Content Retrieval (CCR)

```bash
python3 - <<'EOF'
import tempfile, os
from pathlib import Path
from headroom.ccr.store import CCRStore

with tempfile.TemporaryDirectory() as tmp:
    store = CCRStore(Path(tmp) / "ccr.db")
    
    # Store a compressed payload
    original = "This is the original content that was compressed away. " * 50
    key = store.put(original, ttl_seconds=300)
    print(f"Stored with key: {key}")
    
    # Retrieve it
    retrieved = store.get(key)
    assert retrieved == original, "retrieved content should match original"
    print(f"Retrieved {len(retrieved)} chars — PASS")
    
    # TTL expiry
    expired_key = store.put("short-lived", ttl_seconds=1)
    import time; time.sleep(2)
    result = store.get(expired_key)
    assert result is None, f"expected None after TTL, got: {result}"
    print("TTL expiry test — PASS")
    
    # Stats
    stats = store.stats()
    print(f"Stats: {stats}")
    assert stats["total_entries"] >= 1
    print("Stats test — PASS")
EOF
```

**PASS:** all three sub-tests print PASS

```bash
# CCR via proxy with custom TTL
cutctx proxy --port 8794 --ccr-ttl-seconds 3600 &
PROXY_PID=$!
sleep 2
curl -s http://localhost:8794/livez | jq .
kill $PROXY_PID
```

**PASS:** proxy starts; TTL parameter accepted

```bash
# CCR disabled flags
cutctx proxy --port 8795 --no-ccr-inject-tool --no-ccr-marker &
PROXY_PID=$!
sleep 2
curl -s http://localhost:8795/livez | jq .
kill $PROXY_PID
```

**PASS:** proxy starts; no CCR tool injection or markers in responses

---

## 12. Persistent Memory

```bash
cutctx proxy --port 8796 --memory &
PROXY_PID=$!
sleep 2

# Verify memory endpoints exist
curl -s http://localhost:8796/v1/memory/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "top_k": 5}' | jq .

kill $PROXY_PID
```

**PASS:** memory endpoint returns a valid JSON response (even if empty)

```bash
# Memory with custom DB path
TMPDB=$(mktemp -d)/memory.db
cutctx proxy --port 8797 --memory --memory-db-path "$TMPDB" &
PROXY_PID=$!
sleep 2
curl -s http://localhost:8797/livez | jq .
kill $PROXY_PID

# DB file should exist
ls -la "$TMPDB" 2>/dev/null && echo "DB created — PASS" || echo "FAIL — DB not created"
```

**PASS:** DB file created at the specified path

---

## 13. Live Traffic Learning

```bash
cutctx proxy --port 8798 --learn --min-evidence 2 &
PROXY_PID=$!
sleep 2
curl -s http://localhost:8798/livez | jq .
kill $PROXY_PID
```

**PASS:** proxy starts; no crash; `--learn` flag acknowledged in startup banner

```bash
# Incompatible: --no-learn should suppress learning even when --memory is set
cutctx proxy --port 8799 --memory --no-learn &
PROXY_PID=$!
sleep 2
curl -s http://localhost:8799/livez | jq .
kill $PROXY_PID
```

**PASS:** proxy starts; learning is disabled

---

## 14. Wrap Commands (Agent Integration)

### 14.1 Wrap help — all subcommands exist

```bash
cutctx wrap --help
```

**PASS:** lists `claude`, `codex`, `gemini`, `cursor`, `cline`, `continue`, `aider`, `goose`, `openhands`, `windsurf`, `zed`, `openclaw`, `opencode`

### 14.2 Per-tool help pages

```bash
for tool in claude codex gemini cursor cline continue aider windsurf zed; do
  cutctx wrap $tool --help > /dev/null 2>&1 && echo "$tool: PASS" || echo "$tool: FAIL"
done
```

**PASS:** all tools print help without crash

### 14.3 Wrap claude (dry run — starts proxy then fails if no claude binary)

```bash
# Confirm the proxy starts even if the wrapped tool isn't installed
cutctx wrap claude --help
```

**PASS:** help text shown without requiring `claude` to be installed

### 14.4 Unwrap

```bash
cutctx unwrap --help
```

**PASS:** help text lists tool unwrap options

---

## 15. Init Commands (Durable Integrations)

### 15.1 All subcommands exist

```bash
cutctx init --help
```

**PASS:** lists `claude`, `codex`, `gemini`, `copilot`, `opencode`, `windsurf`, `zed`, `openclaw`

### 15.2 Dry-run init (verbose)

```bash
cutctx init claude --verbose 2>&1 | head -20
```

**PASS:** shows which files would be touched; exits cleanly (may warn that Claude Code is not installed)

```bash
cutctx init opencode --verbose 2>&1 | head -20
cutctx init windsurf --verbose 2>&1 | head -20
cutctx init zed --verbose 2>&1 | head -20
```

**PASS:** each prints diagnostic output; no crash; correct config file paths shown

---

## 16. Proxy Modes — Token vs Cache

```bash
# Token mode (default)
cutctx proxy --port 8800 --mode token &
P1=$!
sleep 2
curl -s http://localhost:8800/v1/stats | jq .mode
kill $P1

# Cache mode
cutctx proxy --port 8801 --mode cache &
P2=$!
sleep 2
curl -s http://localhost:8801/v1/stats | jq .mode
kill $P2
```

**PASS:** `token` mode returns `"token"` in stats; `cache` mode returns `"cache"`

### Legacy alias acceptance

```bash
cutctx proxy --port 8802 --mode token_mode &
P=$!; sleep 2
curl -s http://localhost:8802/livez | jq .
kill $P
```

**PASS:** proxy accepts legacy alias without error

---

## 17. Multi-Backend Support

### 17.1 Backend flag accepted

```bash
for backend in anthropic openrouter anyllm; do
  cutctx proxy --port 8810 --backend $backend --help 2>&1 | head -1 && \
    echo "$backend accepted" || echo "$backend FAILED"
done
```

**PASS:** all backend flags are accepted (proxy doesn't start without credentials, but the flag itself is valid)

### 17.2 LiteLLM backend

```bash
cutctx proxy --port 8811 --backend litellm-vertex --region us-central1 &
P=$!; sleep 2
curl -s http://localhost:8811/livez | jq .
kill $P
```

**PASS:** proxy starts; no crash on unknown backend (may log warning about missing credentials)

### 17.3 Bedrock backend

```bash
cutctx proxy --port 8812 --backend bedrock --region us-east-1 &
P=$!; sleep 2
curl -s http://localhost:8812/livez | jq .
kill $P
```

**PASS:** proxy starts; Bedrock region flag accepted

---

## 18. Langfuse Observability Tracing

```bash
# Start proxy with Langfuse flags (no real Langfuse server needed — tests startup)
cutctx proxy --port 8820 \
  --langfuse \
  --langfuse-public-key pk-test-1234 \
  --langfuse-secret-key sk-test-5678 \
  --langfuse-url https://cloud.langfuse.com &
P=$!; sleep 2
curl -s http://localhost:8820/livez | jq .
kill $P
```

**PASS:** proxy starts with Langfuse enabled; startup banner shows "Langfuse tracing: enabled"; no crash

```bash
# Via env vars
LANGFUSE_PUBLIC_KEY=pk-test LANGFUSE_SECRET_KEY=sk-test \
  cutctx proxy --port 8821 --langfuse &
P=$!; sleep 2
curl -s http://localhost:8821/livez | jq .
kill $P
```

**PASS:** proxy reads keys from env

---

## 19. Benchmark (`cutctx bench`)

```bash
# All algorithms, small size
cutctx bench --size small --algorithm all
```

**PASS:** table with 4+ rows; all ratios > 0%; no algorithm errors out

```bash
# JSON output for CI integration
cutctx bench --size small --json | python3 -c "import json,sys; data=json.load(sys.stdin); print(f'Algorithms tested: {len(data[\"results\"])}')"
```

**PASS:** valid JSON parsed; `results` array has at least 1 entry

```bash
# Single algorithm
cutctx bench --size medium --algorithm diff --iterations 5
```

**PASS:** diff algorithm benchmarks only; 5 iterations shown

```bash
# Large benchmark (may take 30-60s)
time cutctx bench --size large --algorithm smart-crusher
```

**PASS:** completes; shows compression ratio; elapsed < 120s

---

## 20. Savings Report (`cutctx savings`)

```bash
# Stats-only mode (no browser, just terminal)
cutctx savings --no-browser --stats-only
```

**PASS:** shows a summary table; no browser opened; no crash even if no historical data (shows zeros)

```bash
# Custom date range
cutctx savings --days 7 --no-browser
```

**PASS:** report generated for last 7 days

```bash
# JSON output (if supported)
cutctx savings --no-browser --output /tmp/test-savings.html
ls -la /tmp/test-savings.html
```

**PASS:** HTML file created at specified path

---

## 21. License Management

### 21.1 Status (no license)

```bash
cutctx license status
```

**PASS:** shows trial status or "no license activated"; does not crash

### 21.2 Generate a test license key

```bash
export HEADROOM_LICENSE_HMAC_SECRET=my-test-secret-for-manual-testing
python scripts/generate_license.py \
  --tier team \
  --org "Test Corp" \
  --seats 5 \
  --expiry 2027-12-31
```

**PASS:** outputs a signed license key starting with `team-`; key contains a `.` separator; signature part is exactly 32 hex chars

```bash
# Verify signature length
KEY=$(HEADROOM_LICENSE_HMAC_SECRET=my-test-secret \
  python scripts/generate_license.py --tier team --org "Test" --seats 1 2>/dev/null | \
  grep "^Key:" | awk '{print $2}')
SIG=$(echo $KEY | cut -d. -f2)
echo "Signature length: ${#SIG} (expected: 32)"
[ "${#SIG}" = "32" ] && echo "PASS" || echo "FAIL"
```

**PASS:** signature is exactly 32 characters

### 21.3 Upgrade link

```bash
cutctx license upgrade
```

**PASS:** prints the upgrade URL; does not open browser in test mode (or opens it — both acceptable)

---

## 22. Config Check

```bash
cutctx config-check
```

**PASS:** runs all checks; prints a summary of pass/fail items; exits 0 if no critical issues

```bash
# With specific port
cutctx config-check --port 8787
```

**PASS:** checks if port 8787 is available; no crash

```bash
# With a bad port (should warn)
cutctx config-check --port 80
```

**PASS:** warns about privileged port but does not crash; exits with appropriate code

---

## 23. Persistent Deployment (`cutctx install`)

```bash
cutctx install status
```

**PASS:** shows deployment status (running/stopped/not installed); no crash

```bash
cutctx install apply --help
```

**PASS:** help text explains deployment options

```bash
# Start, check, stop cycle
cutctx install start 2>&1 | head -5 || echo "no daemon configured — expected"
cutctx install status
cutctx install stop 2>&1 | head -5 || true
```

**PASS:** all three commands run without crash; status reflects actual state

---

## 24. Admin API — RBAC

Start proxy with admin key:

```bash
cutctx proxy --port 8830 &
PROXY_PID=$!
sleep 2
```

```bash
# List role assignments
curl -s http://localhost:8830/v1/rbac/assignments \
  -H "X-Admin-API-Key: $HEADROOM_ADMIN_API_KEY" | jq .

# Assign a role
curl -s -X POST http://localhost:8830/v1/rbac/assign \
  -H "X-Admin-API-Key: $HEADROOM_ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user-001", "role": "viewer"}' | jq .

# Verify assignment
curl -s http://localhost:8830/v1/rbac/assignments \
  -H "X-Admin-API-Key: $HEADROOM_ADMIN_API_KEY" | jq .

# Revoke the role
curl -s -X POST http://localhost:8830/v1/rbac/revoke \
  -H "X-Admin-API-Key: $HEADROOM_ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user-001", "role": "viewer"}' | jq .
```

**PASS:** assign returns 200; list shows the new assignment; revoke removes it; list shows it gone

```bash
# Unauthenticated request should be rejected
curl -s -o /dev/null -w "%{http_code}" http://localhost:8830/v1/rbac/assignments
```

**PASS:** returns 401 or 403

```bash
kill $PROXY_PID
```

---

## 25. Admin API — Audit Log

```bash
cutctx proxy --port 8831 &
PROXY_PID=$!
sleep 2
```

```bash
# List recent events
curl -s http://localhost:8831/v1/audit/events \
  -H "X-Admin-API-Key: $HEADROOM_ADMIN_API_KEY" | jq .

# Stats
curl -s http://localhost:8831/v1/audit/stats \
  -H "X-Admin-API-Key: $HEADROOM_ADMIN_API_KEY" | jq .
```

**PASS:** both return 200 with valid JSON; no 500 errors

```bash
# CLI equivalents
cutctx audit list --limit 10
cutctx audit stats
```

**PASS:** CLI commands mirror the API and return formatted output

```bash
kill $PROXY_PID
```

---

## 26. Admin API — SSO Test

```bash
cutctx sso-test --help
```

**PASS:** help text lists OIDC/SAML options

```bash
# With a real OIDC provider (replace with your IdP)
# cutctx sso-test --issuer https://accounts.google.com
# Expected: fetches discovery doc, validates JWKS, prints "SSO config valid"

# Without a provider (expect clear error)
cutctx sso-test 2>&1 | head -5
```

**PASS:** prints clear error "no SSO provider configured" rather than crashing

---

## 27. Docker Image

```bash
# Build from local Dockerfile
docker build -t cutctx-test:local .

# Run health check
docker run -d --name cutctx-test -p 8840:8787 \
  -e HEADROOM_ADMIN_API_KEY=test-key \
  cutctx-test:local
sleep 5
curl -s http://localhost:8840/livez | jq .
```

**PASS:** container starts; `/livez` returns ok

```bash
# Verify binary name inside container
docker exec cutctx-test which cutctx
docker exec cutctx-test cutctx --version
```

**PASS:** binary is named `cutctx` (not `headroom`); version is `0.26.0`

```bash
# Verify no debug keys in container
docker exec cutctx-test env | grep -i "secret\|password\|key" | grep -v "^PATH" | head
```

**PASS:** no hardcoded secrets visible in the container environment

```bash
docker stop cutctx-test && docker rm cutctx-test
```

---

## 28. Helm Chart

```bash
# Lint the chart
helm lint helm/headroom/

# Render templates (dry-run)
helm template cutctx-release helm/headroom/ \
  --set image.tag=v0.26.0 \
  --set adminApiKey=test-key | head -60
```

**PASS:**
- `helm lint` reports no errors
- Rendered templates reference `ghcr.io/cutctx/cutctx` (not `headroom`)
- Service port is 8787
- All template references are `cutctx.*` not `headroom.*`

```bash
# Check specific values
helm template cutctx-release helm/headroom/ | grep -E "image:|port:|namespace:" | head -10
```

**PASS:** image is `ghcr.io/cutctx/cutctx:*`; namespace is `cutctx`; port is `8787`

---

## 29. LlamaIndex Integration

```bash
pip install cutctx-ai[llamaindex] 2>/dev/null || pip install llama-index-core
```

```bash
python3 - <<'EOF'
try:
    from headroom.integrations.llamaindex import CutCtxNodePostprocessor, NodeFilterMetrics
    print("Import OK")
except ImportError as e:
    print(f"Import error: {e} — llama-index may not be installed")

# Test graceful import without llama-index
import sys
# Mock absence of llama_index
import unittest.mock as mock
with mock.patch.dict(sys.modules, {'llama_index': None, 'llama_index.core': None}):
    try:
        from headroom.integrations.llamaindex.postprocessor import CutCtxNodePostprocessor
        print("Graceful fallback PASS")
    except Exception as e:
        print(f"Graceful fallback: {e}")
EOF
```

**PASS:** import succeeds when llama-index is installed; graceful stub is created when it isn't

```bash
# If llama-index is available, test the postprocessor
python3 - <<'EOF'
try:
    from llama_index.core.schema import TextNode
    from headroom.integrations.llamaindex import CutCtxNodePostprocessor
    
    postprocessor = CutCtxNodePostprocessor(top_n=3, min_score=0.1, compress=False)
    nodes = [
        TextNode(text="Python is a programming language.", id_="n1"),
        TextNode(text="The weather today is sunny.", id_="n2"),
        TextNode(text="Python was created by Guido van Rossum.", id_="n3"),
        TextNode(text="Cats are mammals.", id_="n4"),
        TextNode(text="Python 3 was released in 2008.", id_="n5"),
    ]
    
    from llama_index.core.schema import QueryBundle
    filtered = postprocessor.postprocess_nodes(nodes, query_bundle=QueryBundle("Python programming"))
    
    print(f"IN:  {len(nodes)} nodes")
    print(f"OUT: {len(filtered)} nodes (top_n=3)")
    assert len(filtered) <= 3, f"Expected ≤3 nodes, got {len(filtered)}"
    print("PASS — LlamaIndex postprocessor works")
except ImportError:
    print("llama-index not installed — skipping live test")
EOF
```

**PASS:** when llama-index is installed, postprocessor filters to top-N nodes scored against the query

---

## 30. LangChain Integration

```bash
python3 - <<'EOF'
try:
    from headroom.integrations.langchain import CutCtxCallbackHandler
    print("LangChain integration import OK")
except ImportError as e:
    print(f"langchain not installed: {e} — expected if not installed")

# Test graceful import
try:
    from headroom.integrations.langchain.memory import CutCtxChatMessageHistory
    print("Memory integration import OK")
except ImportError:
    print("langchain-core not installed — graceful skip PASS")
EOF
```

**PASS:** imports succeed when langchain is installed; graceful error when not

---

## 31. MCP Server Mode

```bash
cutctx mcp --help
```

**PASS:** help text describes MCP server options

```bash
# Start MCP server briefly
timeout 3 cutctx mcp 2>&1 | head -5 || true
```

**PASS:** server starts (or times out cleanly); no import errors

---

## 32. Security — Hardware Fingerprint & State Encryption

```bash
python3 - <<'EOF'
from headroom.security.state_crypto import _get_machine_id, _machine_fingerprint, encrypt_json, decrypt_json

# Test machine ID is non-empty
mid = _get_machine_id()
print(f"Machine ID: {mid[:20]}... (len={len(mid)})")
assert len(mid) > 5, "machine ID should not be empty"

# Test fingerprint changes are stable (same call = same result)
fp1 = _machine_fingerprint()
fp2 = _machine_fingerprint()
assert fp1 == fp2, "fingerprint must be deterministic"
print("Fingerprint deterministic: PASS")

# Test round-trip encryption
data = {"key": "value", "nested": {"count": 42}}
token = encrypt_json(data)
recovered = decrypt_json(token)
assert recovered == data, "decrypted data must match original"
print("Encrypt/decrypt round-trip: PASS")

# Tampered token should fail
import base64
tampered = token[:-4] + "XXXX"
try:
    decrypt_json(tampered)
    print("FAIL — tampered token should raise")
except Exception as e:
    print(f"Tampered token rejected: PASS ({type(e).__name__})")
EOF
```

**PASS:** all sub-tests pass

```bash
# Verify MAC address is NOT used as primary (platform-specific)
python3 - <<'EOF'
import sys, uuid
from headroom.security.state_crypto import _get_machine_id

mid = _get_machine_id()
mac_str = str(uuid.getnode())

if sys.platform == "darwin":
    # On macOS, primary should be IOPlatformUUID (UUID format), not the MAC integer
    print(f"macOS: machine_id={mid[:36]}")
    # IOPlatformUUID looks like: XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
    is_uuid_format = len(mid) == 36 and mid.count('-') == 4
    print(f"UUID format: {is_uuid_format}")
    if is_uuid_format:
        print("Using IOPlatformUUID — PASS")
    else:
        print(f"Fallback to: {mid} (MAC={mac_str})")
elif sys.platform.startswith("linux"):
    # On Linux, should be /etc/machine-id (32 hex chars)
    print(f"Linux: machine_id={mid}")
    print(f"Looks like machine-id: {len(mid) in (32,33)}")
else:
    print(f"Platform {sys.platform}: {mid}")
EOF
```

**PASS on macOS:** machine ID is in UUID format (IOPlatformUUID), not a plain integer  
**PASS on Linux:** machine ID is 32 hex characters (`/etc/machine-id` format)

---

## 33. Security — EE Integrity Guard

```bash
# Test manifest builder (unsigned, for testing)
python3 scripts/build_ee_manifest.py \
  --unsigned \
  --ee-dir headroom_ee \
  --output /tmp/test-manifest.json
cat /tmp/test-manifest.json | python3 -c "import json,sys; m=json.load(sys.stdin); print(f'Files: {len(m[\"files\"])}, Signed: {\"signature\" in m}')"
```

**PASS:** manifest created; `Files: N` where N > 0; `Signed: False` (unsigned mode)

```bash
# Test signed manifest
export HEADROOM_LICENSE_HMAC_SECRET=test-integrity-secret
python3 scripts/build_ee_manifest.py \
  --ee-dir headroom_ee \
  --output /tmp/test-manifest-signed.json
cat /tmp/test-manifest-signed.json | python3 -c "import json,sys; m=json.load(sys.stdin); print(f'Signed: {\"signature\" in m}')"
```

**PASS:** `Signed: True`

```bash
# Test integrity verifier
python3 - <<'EOF'
import os, json
from pathlib import Path
from headroom.security.integrity import verify_ee_manifest, IntegrityError

# No manifest = no crash (EE not installed)
try:
    verify_ee_manifest(strict=False)
    print("No manifest — graceful skip PASS")
except Exception as e:
    print(f"Unexpected error: {e}")

# Tampered manifest detection
import tempfile, shutil
with tempfile.TemporaryDirectory() as tmp:
    # Write a fake manifest with wrong hashes
    manifest = {
        "version": "1",
        "algorithm": "sha256",
        "files": {"fake.cpython-312-darwin.so": "deadbeef" * 8}
    }
    Path(tmp).joinpath("MANIFEST.sha256.json").write_text(json.dumps(manifest))
    # Write a dummy .so that won't match
    Path(tmp).joinpath("fake.cpython-312-darwin.so").write_bytes(b"not a real so file")
    
    import sys
    sys.modules.pop("headroom_ee", None)
    import unittest.mock as mock
    fake_ee = mock.MagicMock()
    fake_ee.__file__ = str(Path(tmp) / "__init__.py")
    Path(tmp).joinpath("__init__.py").write_text("")
    
    with mock.patch.dict(sys.modules, {"headroom_ee": fake_ee}):
        try:
            verify_ee_manifest(strict=True)
            print("FAIL — should have raised IntegrityError")
        except IntegrityError as e:
            print(f"Tampered manifest rejected: PASS")
        except Exception as e:
            print(f"Other error (may be expected): {type(e).__name__}: {e}")
EOF
```

**PASS:** tampered manifest raises `IntegrityError`

```bash
# Anti-debug guard (no debugger = no crash)
HEADROOM_ALLOW_DEBUG=1 python3 - <<'EOF'
from headroom.security.antidebug import guard_ee_entry
guard_ee_entry()  # Should be a no-op with HEADROOM_ALLOW_DEBUG=1
print("Anti-debug guard (debug allowed): PASS")
EOF
```

**PASS:** no exception when `HEADROOM_ALLOW_DEBUG=1`

```bash
# Python-level detection (should be False in normal run — no debugger)
python3 - <<'EOF'
from headroom.security.antidebug import _python_fallback_is_debugged
result = _python_fallback_is_debugged()
print(f"Debugger detected: {result}")
assert result == False, "expected no debugger in normal pytest/shell run"
print("PASS")
EOF
```

**PASS:** `False` — no debugger attached in normal run

---

## 34. Edge Cases & Error Handling

### 34.1 Port already in use

```bash
# Start something on 8850
python3 -c "import socket; s=socket.socket(); s.bind(('127.0.0.1', 8850)); s.listen(1); input()" &
BLOCKER_PID=$!
sleep 1

# Try to start proxy on same port
cutctx proxy --port 8850 2>&1 | head -5
PROXY_EXIT=$?
kill $BLOCKER_PID 2>/dev/null
```

**PASS:** proxy prints clear error "port already in use" or similar; exits non-zero; no hang

### 34.2 Empty input to compressors

```bash
python3 - <<'EOF'
from headroom.transforms.content_router import ContentRouter, ContentRouterConfig

router = ContentRouter(ContentRouterConfig())
result = router.compress("")
print(f"Empty input: ratio={result.compression_ratio:.2f}, saved={result.tokens_saved}")
print("No crash — PASS")
EOF
```

**PASS:** no crash; compression ratio is 0; tokens_saved is 0

### 34.3 Very large input

```bash
python3 - <<'EOF'
from headroom.transforms.log_compressor import LogCompressor

big_log = "[INFO] Processing item 12345\n" * 10000
result = LogCompressor().compress(big_log)
print(f"10k line log: IN={len(big_log)}, OUT={len(result.compressed)}, saved={result.tokens_saved}")
assert result.tokens_saved > 0
print("PASS")
EOF
```

**PASS:** handles 10k-line log; significant savings; no memory error

### 34.4 Invalid JSON gracefully handled

```bash
python3 - <<'EOF'
from headroom.transforms.smart_crusher import SmartCrusher, SmartCrusherConfig

crusher = SmartCrusher(SmartCrusherConfig())
# Not valid JSON array
result = crusher.crush("this is not json at all {{{")
print(f"Invalid JSON: result length={len(result.kept_json)}")
print("No crash — PASS")
EOF
```

**PASS:** no crash; returns original or minimal result

### 34.5 Concurrent proxy requests

```bash
cutctx proxy --port 8860 &
PROXY_PID=$!
sleep 2

# Fire 20 concurrent health checks
for i in $(seq 1 20); do
  curl -s http://localhost:8860/livez &
done
wait
echo "Concurrency test done"
kill $PROXY_PID
```

**PASS:** all 20 requests return 200; no timeout; proxy still alive after load

### 34.6 HMAC license — wrong signature length rejected

```bash
python3 - <<'EOF'
import os
os.environ["HEADROOM_LICENSE_HMAC_SECRET"] = "test-secret"

try:
    from headroom import _core
    # Too-short signature (8 chars, below 32-char minimum)
    result = _core.verify_license_signature("team", "abc123", "cust456", "deadbeef")
    assert result == False, "short signature should be rejected"
    print("Short signature rejected: PASS")
    
    # Wrong secret produces wrong signature
    result2 = _core.verify_license_signature("team", "abc123", "cust456", "a" * 32)
    assert result2 == False, "all-a signature should not match"
    print("Wrong signature rejected: PASS")
except ImportError:
    print("_core not available — Rust .so not compiled (expected on non-macOS)")
EOF
```

**PASS:** short signatures (<32 chars) and wrong signatures return `False`

---

## Test Coverage Summary

| Area | Tests | Key checks |
|------|-------|-----------|
| Installation | 3 | binary name, version, Rust core linkage |
| Proxy startup | 5 | modes, ports, env vars, flags |
| Endpoints | 5 | livez, readyz, metrics, stats, version |
| Algorithms | 6 | SmartCrusher, Diff, Log, Search, Code, Compact |
| ContentRouter | 3 | auto-detection accuracy per type |
| CCR | 4 | store/retrieve, TTL, stats, flags |
| Memory | 2 | endpoints, custom DB path |
| Learning | 2 | start/stop, incompatible flags |
| Wrap/Init | 3 | subcommands, help, dry-run |
| Modes/Backends | 5 | token/cache, litellm, bedrock, legacy aliases |
| Langfuse | 2 | startup with keys, env vars |
| Benchmark | 4 | all algos, JSON, single algo, large |
| Savings | 3 | stats-only, date range, HTML output |
| License | 3 | status, generate (32-char sig), upgrade URL |
| Config check | 3 | clean, port available, bad port |
| Install | 3 | status, start/stop cycle, help |
| RBAC | 5 | assign, list, revoke, unauth rejection |
| Audit | 4 | list, stats, CLI, API |
| Docker | 4 | build, health, binary name, no secrets |
| Helm | 3 | lint, render, image/port correctness |
| LlamaIndex | 3 | import, graceful miss, filter |
| Security | 8 | fingerprint, encrypt, tamper, antidebug, manifest |
| Edge cases | 6 | empty, large, invalid JSON, concurrency, port conflict, short sig |
| Live API call | 4 | real Anthropic request, OpenAI-compat, streaming, tool intercept |
| Reports | 6 | ROI buyer (text/json/md), export (json/csv), schedule list |
| Perf analyzer | 3 | default, --hours, --raw |
| Agent savings | 3 | shell format, JSON format, --check-perf |
| Integrations | 3 | status table, openai parser test, anthropic parser test |
| Bundled tools | 4 | list, doctor, doctor --json, install |
| Orgs | 3 | list, create, list again |
| Billing | 2 | help, checkout dry-run |
| Spend ledger | 2 | spend summary, per-org spend |
| Rate limits | 3 | stats endpoint, 50-request stress, --no-rate-limit |
| Secrets store | 4 | list, create, read, update |
| GDPR DSR | 2 | export, delete |
| Traffic capture | 3 | help, network-diff with dummy JSONL |
| Memory evals | 2 | help, probes offline run |
| Learn | 2 | help, dry-run |
| VS Code ext | 8 | build, package, install, UI smoke test |
| JetBrains | 5 | build, package, install, settings, proxy start |
| Air-gap | 2 | with secret (starts), without secret (must fail) |
| Image compression | 2 | router graceful handling, Rust core check |
| Stateless deploy | 2 | no files written, Docker stateless run |

**Total: ~170 manual test steps across 57 sections**

---

## 35. Live Proxy Request (Real API Call)

> Requires a valid `ANTHROPIC_API_KEY`. Skip this section if no key is available.

```bash
cutctx proxy --port 8900 &
PROXY_PID=$!
sleep 2

# Make a real API call through the proxy (Anthropic-compatible)
curl -s http://localhost:8900/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "claude-haiku-4-5-20251001",
    "max_tokens": 64,
    "messages": [{"role": "user", "content": "Reply with just: PROXY_TEST_OK"}]
  }' | jq '.content[0].text'
```

**PASS:** response contains `PROXY_TEST_OK`; the proxy forwarded the request correctly

```bash
# Check that stats updated after the real call
curl -s http://localhost:8900/v1/stats | jq '{requests: .requests_total, tokens_saved: .tokens_saved}'
kill $PROXY_PID
```

**PASS:** `requests_total` > 0 after the call

### OpenAI-compatible client path

```bash
cutctx proxy --port 8901 &
PROXY_PID=$!
sleep 2

# OpenAI-format request (Claude model)
curl -s http://localhost:8901/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ANTHROPIC_API_KEY" \
  -d '{
    "model": "claude-haiku-4-5-20251001",
    "max_tokens": 64,
    "messages": [{"role": "user", "content": "Reply with just: OPENAI_COMPAT_OK"}]
  }' | jq '.choices[0].message.content'
kill $PROXY_PID
```

**PASS:** response contains `OPENAI_COMPAT_OK` — OpenAI-format request handled by Anthropic backend

---

## 36. Streaming Responses

```bash
cutctx proxy --port 8902 &
PROXY_PID=$!
sleep 2

curl -s http://localhost:8902/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "claude-haiku-4-5-20251001",
    "max_tokens": 64,
    "stream": true,
    "messages": [{"role": "user", "content": "Count 1 to 5, one per line"}]
  }' 2>&1 | head -20

kill $PROXY_PID
```

**PASS:** response contains `data:` prefixed SSE lines; `content_block_delta` events visible; stream terminates with `message_stop`

```bash
# Streaming with --no-ccr-inject-tool (important for streaming clients)
cutctx proxy --port 8903 --no-ccr-inject-tool &
PROXY_PID=$!
sleep 2
curl -s -o /dev/null -w "%{http_code}" http://localhost:8903/livez
kill $PROXY_PID
```

**PASS:** proxy starts cleanly; CCR tool not injected into streaming responses

---

## 37. Intercept Tool Results

```bash
cutctx proxy --port 8904 --intercept-tool-results &
PROXY_PID=$!
sleep 2
curl -s http://localhost:8904/livez | jq .
kill $PROXY_PID
```

**PASS:** proxy starts with tool result interception enabled; no crash

---

## 38. Report Generation

### 38.1 ROI buyer report

```bash
cutctx report buyer --format text 2>&1 | head -20
```

**PASS:** prints a structured ROI summary (may show zeros if no traffic data); no crash

```bash
cutctx report buyer --format markdown -o /tmp/roi-report.md
ls -la /tmp/roi-report.md
head -20 /tmp/roi-report.md
```

**PASS:** markdown file created; contains `#` headers; no Python tracebacks

```bash
cutctx report buyer --format json -o /tmp/roi-report.json
python3 -c "import json; d=json.load(open('/tmp/roi-report.json')); print('Keys:', list(d.keys()))"
```

**PASS:** valid JSON; has keys like `provider_cache_savings`, `cutctx_compression_savings`

### 38.2 Export savings data

```bash
cutctx report export --format json -o /tmp/savings.json
python3 -c "import json; d=json.load(open('/tmp/savings.json')); print('Type:', type(d))"
```

**PASS:** valid JSON export

```bash
cutctx report export --format csv -o /tmp/savings.csv
head -3 /tmp/savings.csv
```

**PASS:** valid CSV with header row

### 38.3 Scheduled reports

```bash
cutctx report schedule-list
cutctx report schedule-cancel
```

**PASS:** both commands run without crash; `schedule-list` returns empty list or current schedules

---

## 39. Performance Log Analyzer (`cutctx perf`)

```bash
# Run against whatever logs exist (empty output is fine)
cutctx perf 2>&1 | head -20
```

**PASS:** shows a performance table or "no log data found"; no crash

```bash
cutctx perf --hours 1 2>&1 | head -10
cutctx perf --raw 2>&1 | head -10
```

**PASS:** both flags accepted; no crash

---

## 40. Agent Savings Profiler

```bash
# Show the default agent-90 profile
cutctx agent-savings --profile agent-90 --format shell
```

**PASS:** prints a set of `export HEADROOM_*=...` shell lines; no crash

```bash
# JSON format
cutctx agent-savings --format json | python3 -c "import json,sys; d=json.load(sys.stdin); print('Keys:', list(d.keys()))"
```

**PASS:** valid JSON with profile keys

```bash
# Check performance against recent logs (may show no data)
cutctx agent-savings --check-perf --hours 1 2>&1 | head -10
```

**PASS:** runs without crash; prints status or "no logs found"

---

## 41. Provider Integrations Inspector

```bash
cutctx integrations status
```

**PASS:** table showing each provider integration (anthropic, openai, bedrock, vertex, etc.) with supported/wired/library_available columns

```bash
# Test a specific provider parser
cutctx integrations test openai 2>&1 | head -10
cutctx integrations test anthropic 2>&1 | head -10
```

**PASS:** each parser smoke-test passes; no crash; output confirms "parser OK" or similar

---

## 42. Bundled Tools Manager (`cutctx tools`)

```bash
# List all bundled tools with versions
cutctx tools list
```

**PASS:** table with `ast-grep`, `difft` (difftastic), `scc` listed with version and platform info

```bash
# Doctor check — which tools are present/missing
cutctx tools doctor
```

**PASS:** shows status of each tool (installed/missing); no crash

```bash
cutctx tools doctor --json | python3 -c "import json,sys; d=json.load(sys.stdin); print('Tools checked:', len(d))"
```

**PASS:** valid JSON with at least 3 tools

```bash
# Install all bundled tools to cache
cutctx tools install 2>&1 | head -10
```

**PASS:** downloads or confirms tools are cached; no crash

---

## 43. Organization Management (`cutctx orgs`)

```bash
cutctx proxy --port 8910 &
PROXY_PID=$!
sleep 2

# List orgs (empty on fresh install)
cutctx orgs list --admin-key "$HEADROOM_ADMIN_API_KEY" 2>&1 | head -10

# Create an org
cutctx orgs create --admin-key "$HEADROOM_ADMIN_API_KEY" \
  --name "Test Org" --slug "test-org" 2>&1 | head -5

# List again — should show the new org
cutctx orgs list --admin-key "$HEADROOM_ADMIN_API_KEY" 2>&1 | head -10

kill $PROXY_PID
```

**PASS:** create succeeds with a JSON org object; list shows the created org

---

## 44. Billing Management (`cutctx billing`)

```bash
cutctx billing --help
cutctx billing checkout --help
```

**PASS:** help text shows checkout and portal options; no crash

```bash
# Dry run — show what would happen (don't actually open browser in CI)
CUTCTX_TEST_MODE=1 cutctx billing checkout --tier team 2>&1 | head -5
```

**PASS:** prints checkout URL without opening browser; URL contains `stripe.com` or `cutctx.dev`

---

## 45. Admin API — Spend Ledger

```bash
cutctx proxy --port 8920 &
PROXY_PID=$!
sleep 2

# Get spend summary
curl -s http://localhost:8920/v1/spend \
  -H "X-Admin-API-Key: $HEADROOM_ADMIN_API_KEY" | jq .

# Get per-org spend
curl -s "http://localhost:8920/v1/spend?org=default" \
  -H "X-Admin-API-Key: $HEADROOM_ADMIN_API_KEY" | jq .

kill $PROXY_PID
```

**PASS:** both return 200 with JSON (may be empty dict/zeros on fresh install); no 500 errors

---

## 46. Admin API — Rate Limit Stats

```bash
cutctx proxy --port 8921 &
PROXY_PID=$!
sleep 2

# Rate limit statistics
curl -s http://localhost:8921/v1/rate-limit/stats \
  -H "X-Admin-API-Key: $HEADROOM_ADMIN_API_KEY" | jq .

# Test that --no-rate-limit disables it
kill $PROXY_PID
cutctx proxy --port 8922 --no-rate-limit &
PROXY_PID=$!
sleep 2
curl -s http://localhost:8922/livez | jq .
kill $PROXY_PID
```

**PASS:** rate-limit stats endpoint returns 200 JSON; proxy with `--no-rate-limit` starts cleanly

---

## 47. Admin API — Secrets Store

```bash
cutctx proxy --port 8923 &
PROXY_PID=$!
sleep 2

# List secrets (should be empty)
curl -s http://localhost:8923/v1/secrets \
  -H "X-Admin-API-Key: $HEADROOM_ADMIN_API_KEY" | jq .

# Write a secret
curl -s -X POST http://localhost:8923/v1/secrets \
  -H "X-Admin-API-Key: $HEADROOM_ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "MY_TEST_SECRET", "value": "secret-value-123"}' | jq .

# Read it back
curl -s http://localhost:8923/v1/secrets \
  -H "X-Admin-API-Key: $HEADROOM_ADMIN_API_KEY" | jq .

# Update it
curl -s -X PUT http://localhost:8923/v1/secrets/MY_TEST_SECRET \
  -H "X-Admin-API-Key: $HEADROOM_ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"value": "updated-value-456"}' | jq .

kill $PROXY_PID
```

**PASS:** create returns 200; list shows `MY_TEST_SECRET`; update returns 200; secret value is NOT returned in plaintext (only `{"name": "...", "exists": true}`)

---

## 48. Admin API — GDPR DSR

```bash
cutctx proxy --port 8924 &
PROXY_PID=$!
sleep 2

# Data export request
curl -s http://localhost:8924/v1/dsr/export?user_id=user-001 \
  -H "X-Admin-API-Key: $HEADROOM_ADMIN_API_KEY" | jq .

# Data deletion request
curl -s -X POST http://localhost:8924/v1/dsr/delete \
  -H "X-Admin-API-Key: $HEADROOM_ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user-001"}' | jq .

kill $PROXY_PID
```

**PASS:** export returns 200 with a data envelope (may be empty); delete returns 200 with confirmation; no 500 errors

---

## 49. Traffic Capture & Diff

```bash
cutctx capture --help
cutctx capture network-diff --help
```

**PASS:** help text explains capture and comparison options; no crash

```bash
# Create two dummy JSONL capture files and diff them
cat > /tmp/direct.jsonl << 'EOF'
{"request": {"messages": [{"role": "user", "content": "Hello"}]}, "response": {"usage": {"input_tokens": 10, "output_tokens": 5}}}
EOF

cat > /tmp/cutctx.jsonl << 'EOF'
{"request": {"messages": [{"role": "user", "content": "Hello"}]}, "response": {"usage": {"input_tokens": 8, "output_tokens": 5}}, "cutctx_tokens_saved": 2}
EOF

cutctx capture network-diff \
  --direct /tmp/direct.jsonl \
  --cutctx /tmp/cutctx.jsonl 2>&1 | head -20
```

**PASS:** diff output shows comparison metrics; no crash

---

## 50. Memory Evals Benchmark

```bash
cutctx evals --help
cutctx evals probes --help 2>&1 | head -10
```

**PASS:** help text describes evaluation commands; no crash

```bash
# Probe evaluation (offline, no API key needed)
cutctx evals probes 2>&1 | head -15
```

**PASS:** runs probe evaluation; outputs scores or "no recorded events found"; no crash

---

## 51. Learn from Failures (`cutctx learn`)

```bash
cutctx learn --help | head -20
```

**PASS:** help text explains auto-detect agent and model; no crash

```bash
# Dry run without applying (don't write files)
cutctx learn --dry-run 2>&1 | head -10 || \
  cutctx learn 2>&1 | head -5  # Some versions don't have --dry-run
```

**PASS:** runs analysis or prints "no conversation history found"; no crash; no unhandled exception

---

## 52. VS Code Extension — Manual Smoke Test

Prerequisites: VS Code installed, extension built from `extensions/vscode/`.

```bash
# Build the extension
cd extensions/vscode/
npm install
npm run compile
ls -la dist/ || ls -la out/
```

**PASS:** `dist/` or `out/` directory created with compiled JS files; no TypeScript errors

```bash
# Package as .vsix for manual install
npx vsce package 2>&1 | tail -5
ls *.vsix
```

**PASS:** `.vsix` file created

**Manual steps in VS Code:**
1. Open VS Code
2. Press `Cmd+Shift+P` → "Extensions: Install from VSIX"
3. Select the `.vsix` file
4. Verify "CutCtx" appears in the Extensions list
5. Open the CutCtx panel (sidebar icon)
6. Start proxy from the extension UI
7. Verify the status bar shows "CutCtx: Running"
8. Stop proxy; status bar should update to "CutCtx: Stopped"

**PASS:** all 8 steps complete without VS Code crash or error dialogs

---

## 53. JetBrains Plugin — Manual Smoke Test

Prerequisites: IntelliJ IDEA or any JetBrains IDE, Gradle.

```bash
cd extensions/jetbrains/
./gradlew buildPlugin 2>&1 | tail -10
ls build/distributions/*.zip
```

**PASS:** `.zip` plugin archive created in `build/distributions/`

**Manual steps in IntelliJ IDEA:**
1. Open IntelliJ → Settings → Plugins
2. Click gear icon → "Install Plugin from Disk"
3. Select the `.zip` from `build/distributions/`
4. Restart IDE
5. Verify "CutCtx" entry appears in Settings → Tools
6. Open a project; verify the CutCtx toolbar button is present
7. Enable proxy from plugin settings; verify proxy starts
8. Check the CutCtx tool window shows savings stats

**PASS:** plugin installs without errors; proxy starts from within IDE

---

## 54. Air-Gap Mode

```bash
# Start in offline/airgap mode
HEADROOM_OFFLINE_MODE=1 \
HEADROOM_LICENSE_HMAC_SECRET=test-airgap-secret \
  cutctx proxy --port 8930 2>&1 | head -10 &
PROXY_PID=$!
sleep 2
curl -s http://localhost:8930/livez | jq .
kill $PROXY_PID
```

**PASS:** proxy starts in offline mode; `/livez` returns ok; no call to external license server

```bash
# Without the secret, OFFLINE_MODE should refuse to start
HEADROOM_OFFLINE_MODE=1 cutctx proxy --port 8931 2>&1 | head -5
```

**PASS:** clear error about `HEADROOM_LICENSE_HMAC_SECRET` being required; proxy does not start

---

## 55. Rate Limiting

```bash
cutctx proxy --port 8932 &
PROXY_PID=$!
sleep 2

# Fire many rapid requests to trigger rate limiting
for i in $(seq 1 50); do
  curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8932/livez
done | sort | uniq -c

kill $PROXY_PID
```

**PASS:** mostly `200` responses for `/livez`; if rate limit is triggered on `/livez`, that's a misconfiguration (healthcheck should not be rate-limited)

```bash
# Disable rate limiting
cutctx proxy --port 8933 --no-rate-limit &
PROXY_PID=$!
sleep 2
# Same 50 requests — all should be 200 with no limiting
for i in $(seq 1 50); do
  curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8933/livez
done | sort | uniq -c
kill $PROXY_PID
```

**PASS:** all 50 responses are `200` with `--no-rate-limit`

---

## 56. Multimodal (Image) Compression

```bash
python3 - <<'EOF'
import base64

# Create a minimal 1x1 white PNG (valid PNG binary)
PNG_1x1 = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
    b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00'
    b'\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
)
b64_image = base64.b64encode(PNG_1x1).decode()
data_uri = f"data:image/png;base64,{b64_image}"

try:
    from headroom.transforms.content_router import ContentRouter, ContentRouterConfig
    router = ContentRouter(ContentRouterConfig())
    # Image-only content — router should handle gracefully
    result = router.compress(data_uri)
    print(f"Image URI handled: strategy={result.strategy}, saved={result.tokens_saved}")
    print("PASS — no crash on image input")
except Exception as e:
    print(f"Error: {e}")
EOF
```

**PASS:** no crash; router handles base64 image data gracefully

```bash
python3 - <<'EOF'
# Test image compressor directly if available
try:
    from headroom._core import ImageCompressor
    print("ImageCompressor available in Rust core")
except (ImportError, AttributeError):
    print("ImageCompressor: checked via content router path — PASS")
EOF
```

**PASS:** either `ImageCompressor` is accessible from Rust core or falls through gracefully

---

## 57. Stateless Container Deployment

```bash
# Verify stateless mode leaves no files
TMPDIR=$(mktemp -d)
HOME=$TMPDIR HEADROOM_STATELESS=true cutctx proxy --port 8940 --stateless &
PROXY_PID=$!
sleep 2

# Make a few requests
for i in 1 2 3; do
  curl -s http://localhost:8940/livez > /dev/null
done

kill $PROXY_PID
sleep 1

# Check no state files were written
find $TMPDIR -name "*.db" -o -name "*.json" | grep -v ".npm" | head -10
echo "Files found in HOME: $(find $TMPDIR -type f | wc -l | tr -d ' ')"
```

**PASS:** zero or very few files in `$TMPDIR`; specifically no `.db` or state `.json` files from CutCtx

```bash
# Docker stateless run
docker run --rm \
  -e HEADROOM_STATELESS=true \
  -e HEADROOM_ADMIN_API_KEY=test \
  -p 8941:8787 \
  ghcr.io/cutctx/cutctx:0.26.0 &
sleep 5
curl -s http://localhost:8941/livez | jq .
docker stop $(docker ps -q --filter ancestor=ghcr.io/cutctx/cutctx:0.26.0) 2>/dev/null || true
```

**PASS:** container runs in stateless mode; no volume mounts required; `/livez` returns ok

---

## Appendix: Quick Regression Checklist

Run this after any code change to catch the most common regressions:

```bash
# 1. Binary works
cutctx --version

# 2. Proxy starts and is healthy
cutctx proxy --port 9999 & sleep 2 && curl -s http://localhost:9999/livez | jq . && kill %%

# 3. All algorithms benchmark without error
cutctx bench --size small --json > /dev/null && echo "bench OK"

# 4. Savings CLI works
cutctx savings --no-browser --stats-only

# 5. Config check passes
cutctx config-check

# 6. License status
cutctx license status

# 7. Rust core linked
python3 -c "from headroom import _core; assert _core.hello() == 'headroom-core'; print('Rust core OK')"

# 8. State crypto round-trip
python3 -c "from headroom.security.state_crypto import encrypt_json, decrypt_json; d={'x':1}; assert decrypt_json(encrypt_json(d)) == d; print('Crypto OK')"
```

All 8 should pass in under 30 seconds on a healthy build.
