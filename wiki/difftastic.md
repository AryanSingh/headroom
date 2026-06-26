# Structural Diff Compression (Difftastic)

Cutctx's Difftastic integration replaces verbose unified-diff output (`git diff`, `git show`) with **AST-aware structural diffs** using [`difft`](https://github.com/Wilfred/difftastic) (difftastic, MIT). Function bodies moved between files produce **0 diff lines**, whitespace changes are silently dropped, and only semantically meaningful changes are shown — giving the LLM a compact view of what actually changed.

## Overview

### The Problem with Unified Diffs

Cutctx's existing `DiffCompressor` processes unified diffs in line-oriented fashion — it strips metadata headers and trims context lines. But it has a fundamental blind spot: **it is not AST-aware**. When a developer moves a 50-line function from one file to another, the unified diff shows 50 deletions + 50 additions (100 lines). The existing compressor preserves all 100 lines because it cannot recognize the move.

### What Difftastic Does Differently

Difftastic parses source files into their ASTs and diffs the trees rather than raw lines:

| Property | Unified Diff | Difftastic (structural) |
|----------|-------------|------------------------|
| **Moved code** | N deletions + N additions (all 100 lines preserved) | **0 lines** (recognized as a move) |
| **Whitespace changes** | All +/- lines preserved | **Silently dropped** |
| **Formatting (trailing commas, etc.)** | 1 removal + 1 addition | **0 output** |
| **Language support** | Agnostic (line-based) | **30+ languages** parsed to AST |
| **Context** | N fixed context lines per hunk | Nodes surrounding changed AST nodes |
| **Typical reduction** | 40–70% (metadata + context trimming) | 60–95% (semantic-only output) |

### Two Integration Points

```
                    Incoming tool result
                           │
               ┌───────────▼───────────┐
               │  DifftasticInterceptor │  ◄── Point 1 (Primary)
               │  (interceptor)         │       Intercepts Bash/Run tool
               │                       │       results with git diff output
               └───────────┬───────────┘
                           │
               ┌───────────▼───────────┐
               │  ContentRouter         │  ◄── Point 2 (Secondary)
               │  (DIFF strategy)       │       DifftasticBackend handles
               │                       │       diff content from non-Bash tools
               └───────────┬───────────┘
                           │
                       upstream LLM
```

**Point 1: DifftasticInterceptor** — Sits in the `ToolResultInterceptor` pipeline. Matches Bash/Run/computer tool results whose output looks like a git-format unified diff (`diff --git a/`), splits it into per-file old/new content, runs `difft` on each file pair, and reassembles a compact structural representation.

**Point 2: DifftasticBackend** — A thin wrapper in `diff_compressor.py` that provides the same `DifftasticBackend.compress()` interface as `DiffCompressor`. Used by `ContentRouter` when content classified as `DIFF` arrives through non-Bash paths (pasted diffs, tool responses, etc.).

### Interceptor Data Flow

```
Bash tool result (git diff)
  │
  ├─ _is_git_diff() — detect diff headers
  │
  ├─ _split_into_file_diffs() — split multi-file diffs
  │     [(old_path, new_path, section_text), ...]
  │
  ├─ for each file pair:
  │     _reconstruct_old_new() — rebuild old/new content from hunks
  │     └─ write to temp files
  │     └─ _run_difft() — subprocess: difft old new
  │     └─ return structural output
  │
  ├─ reassemble with file headers
  │
  └─ never enlarge — if difft output ≥ original, pass through
```

## Activation

### CLI Flag

```bash
# Enable with auto-fetched binary
cutctx proxy --difftastic

# With custom context and binary path
cutctx proxy --difftastic --difftastic-context-lines 2
cutctx proxy --difftastic --difftastic-binary /usr/local/bin/difft
```

### Environment Variables

```bash
CUTCTX_DIFFTASTIC=1 cutctx proxy
CUTCTX_DIFFTASTIC_CONTEXT_LINES=2 CUTCTX_DIFFTASTIC=1 cutctx proxy
CUTCTX_DIFFTASTIC_BINARY=/usr/local/bin/difft CUTCTX_DIFFTASTIC=1 cutctx proxy
```

## Configuration

### ProxyConfig Fields

| Field | Default | Description |
|-------|---------|-------------|
| `difftastic_enabled` | `False` | Enable structural diff compression |
| `difftastic_binary` | `"difft"` | Path or name of the difft binary |
| `difftastic_context_lines` | `3` | Context lines around changes (0–20) |

### CLI Options

| Flag | Env Var | Default | Description |
|------|---------|---------|-------------|
| `--difftastic` | `CUTCTX_DIFFTASTIC` | — | Enable structural diff compression |
| `--difftastic-binary` | `CUTCTX_DIFFTASTIC_BINARY` | `auto` | Path or name of difft binary |
| `--difftastic-context-lines` | `CUTCTX_DIFFTASTIC_CONTEXT_LINES` | `3` | Context lines (0–20) |

### Finer-Grained Env Controls

| Env Var | Default | Description |
|---------|---------|-------------|
| `CUTCTX_DIFFTASTIC_MIN_CHARS` | `200` | Minimum diff size (chars) before interception |
| `CUTCTX_DIFFTASTIC_TIMEOUT` | `10` | Per-file subprocess timeout in seconds |

## Binary Management

### Auto-Fetch (Recommended)

Difftastic (`difft`) is already registered in `cutctx/tools.json` as v0.64.0. Cutctx auto-fetches it on first use:

```bash
# Pre-fetch all tools (including difft)
cutctx tools install

# Fetch only difft
cutctx tools install --tool difft

# Check status
cutctx tools doctor
```

Supported platforms: `linux-x86_64`, `linux-aarch64`, `darwin-x86_64`, `darwin-aarch64`, `windows-x86_64`.

### Manual Installation

```bash
# macOS
brew install difftastic

# Rust / Cargo
cargo install difftastic

# Direct download
# https://github.com/Wilfred/difftastic/releases/tag/0.64.0
```

### Binary Resolution Order

The `DifftasticInterceptor` resolves the binary in this order:

1. **Explicit path** from `--difftastic-binary` (absolute path or name on PATH)
2. **`shutil.which("difft")`** — PATH lookup
3. **`cutctx.binaries.resolve("difft")`** — auto-fetch from GitHub releases

## Requirements

### No Python Dependency

Difftastic is a **standalone binary** — no Python package dependency. The binary is auto-fetched via `cutctx tools install` or `cutctx.binaries.resolve("difft")`.

### Graceful Degradation

When the `difft` binary is unavailable:
- **DifftasticInterceptor**: `transform()` returns `None` → the original diff passes through unchanged.
- **DifftasticBackend**: Falls back to the standard `DiffCompressor`.

## Usage

### Basic Interceptor Example

```python
from cutctx.proxy.interceptors.difftastic_interceptor import DifftasticInterceptor

interceptor = DifftasticInterceptor(binary_path="/path/to/difft", context_lines=3)

# Simulate what the proxy sees from a Bash tool result
git_diff = """\
diff --git a/greet.py b/greet.py
index aaa..bbb 100644
--- a/greet.py
+++ b/greet.py
@@ -1,4 +1,5 @@
 def greet(name):
+    \"\"\"Greet someone.\"\"\"
     print(f"Hello, {name}")
     return name
"""

result = interceptor.transform("Bash", {"command": "git diff"}, git_diff)
if result:
    print(result)
    # [cutctx: structural diff via difft for greet.py -> greet.py]
    # def greet(name):
    # +    \"\"\"Greet someone.\"\"\"
    #     print(f"Hello, {name}")
    #     return name
```

### Unified Diff vs Structural Diff Comparison

**Unified diff** (before, 15 lines):
```
diff --git a/utils/old.py b/utils/new.py
index abc..def 100644
--- a/utils/old.py
+++ b/utils/new.py
@@ -1,15 +1,20 @@
-def validate_email(email):
-    # Old implementation
-    import re
-    pattern = r'^\\w+@\\w+\\.\\w+$'
-    return bool(re.match(pattern, email))
-
-
 def send_notification(user, msg):
     print(f"Sending to {user}: {msg}")
 
+
+def validate_email(email):
+    """Validate email format."""
+    import re
+    pattern = r'^\\w+@\\w+\\.\\w+$'
+    return bool(re.match(pattern, email))
+
+
 def process_user(data):
     email = data.get("email")
     if validate_email(email):
         print(f"Valid email: {email}")
```

**Structural diff** (after, 7 lines — 53% reduction):
```
[cutctx: structural diff via difft for utils/old.py -> utils/new.py]

1 def send_notification(user, msg):
2     print(f"Sending to {user}: {msg}")
3
4 1.1 Add validate_email docstring
5     """Validate email format."""
6
7 1.2 def process_user(data):
```

The `validate_email` function moved from one location to another — **zero diff lines for the move** (it was recognized as structurally identical). Only the docstring addition appears as a change.

### Multi-File Diff

```
[cutctx: structural diff via difft for auth.py -> auth.py]
[cutctx: structural diff via difft for models.py -> models.py]

1 def login(username, password):
2     +    validate_input(username)
3     return authenticate(username, password)

1.1 class User:
2     +    is_active: bool
```

Each file is processed independently and tagged with `[cutctx: structural diff via difft for ...]`.

### DifftasticBackend (ContentRouter DIFF Strategy)

```python
from cutctx.transforms.diff_compressor import DifftasticBackend

backend = DifftasticBackend(
    binary_path="/path/to/difft",
    context_lines=3,
)
result = backend.compress(git_diff_content)
print(result.compressed)
print(f"Files affected: {result.files_affected}")
print(f"Lines saved: {result.original_line_count - result.compressed_line_count}")
```

### Checking Binary Availability

```python
from cutctx import binaries

# Check if already available
exe = binaries.which("difft")
if exe:
    print(f"difft found at: {exe}")
else:
    print("difft not on PATH — will attempt auto-fetch")
```

```bash
# Via CLI
cutctx tools doctor | grep difft
cutctx tools install --tool difft
```

## Never-Enlarge Contract

The interceptor guarantees it **never returns something larger than the input**:

```python
result = interceptor.transform("Bash", {"command": "git diff"}, unified_diff)

# result is None (not enlarged content) when:
# - difft output is longer than the original diff
# - difft binary is unavailable
# - difft times out or errors
# - the diff is too short to bother (< MIN_CHARS_TO_TRANSFORM)
```

This means enabling `--difftastic` is always safe — if the structural diff isn't shorter, the user sees the original unified diff.

## Progressive Disclosure

The interceptor uses a **hash of the command** as its progressive disclosure key:

```python
key = interceptor.progressive_disclosure_key("Bash", {"command": "git diff HEAD"})
# "difft:sha256hex..."
```

If the LLM runs the same `git diff` twice, the second result passes through unmodified (the interceptor knows the LLM has already seen the structural version and is asking for more detail).

## Verification

### Check Binary Availability

```bash
cutctx tools doctor | grep difft
# Expected: "difft: found at /path/to/difft-0.64.0-..." or "difft: not found"

# Auto-fetch if missing
cutctx tools install --tool difft
```

### Smoke Test

```bash
# Create test files
echo 'def hello():\n    print("world")' > /tmp/old.py
echo 'def hello():\n    print("world!")' > /tmp/new.py

# Run difft via Cutctx passthrough
cutctx diff /tmp/old.py /tmp/new.py

# Expected: structural output showing the String value change
```

### Run Interceptor Tests

```bash
# Unit tests (no difft required)
pytest tests/test_difftastic_interceptor.py -v

# Integration tests (requires difft binary)
pytest tests/test_difftastic_interceptor.py -v -k "Integration"
```

### Verify CLI Flags

```bash
cutctx proxy --help | grep -A3 "difftastic"
# Must show: --difftastic, --difftastic-binary, --difftastic-context-lines
```

### Real Diff Test

```bash
python - <<'EOF'
from cutctx.proxy.interceptors.difftastic_interceptor import DifftasticInterceptor
from cutctx import binaries

exe = binaries.which("difft")
if exe is None:
    print("difft not found — run 'cutctx tools install --tool difft'")
    exit(1)

interceptor = DifftasticInterceptor(binary_path=str(exe), context_lines=3)

import subprocess
git_diff = subprocess.run(
    ["git", "diff", "HEAD~1", "HEAD"],
    capture_output=True, text=True,
    cwd="/Users/aryansingh/Documents/Claude/Projects/cutctx"
).stdout

if not git_diff.strip():
    print("No diff found")
    exit(0)

original_lines = len(git_diff.splitlines())
result = interceptor.transform("Bash", {"command": "git diff HEAD~1 HEAD"}, git_diff)

if result is None:
    print(f"No improvement (original {original_lines} lines was already compact)")
else:
    structural_lines = len(result.splitlines())
    pct = (1 - structural_lines / original_lines) * 100
    print(f"Original: {original_lines} lines → Structural: {structural_lines} lines ({pct:.1f}% reduction)")
    print("--- Structural diff output (first 40 lines) ---")
    print("\n".join(result.splitlines()[:40]))
EOF
```

## Troubleshooting

| Problem | Likely Cause | Solution |
|---------|-------------|----------|
| Interceptor never activates | difft binary not found | `cutctx tools install --tool difft` |
| `transform()` always returns `None` | difft output not shorter than original | This is expected for small diffs — the never-enlarge contract is working |
| Proxy logs: "difft binary not available" | Binary auto-fetch failed | Install manually: `brew install difftastic` or `cargo install difftastic` |
| Proxy logs: "difft returned rc=2" | difft couldn't parse the file | Binary is installed but file extension is unsupported — falls back gracefully |
| Proxy logs: "difft timed out" | Large file causing slow parsing | Rare — difft is fast for most inputs. Check file size. |
| No structural output for specific language | Language not supported by difftastic | difft supports 30+ languages — check difftastic docs for current list. Falls back to unified diff. |

### Supported Languages

Difftastic supports 30+ languages including: Python, TypeScript, JavaScript, Go, Rust, Java, C, C++, Ruby, Kotlin, Swift, Scala, Haskell, Elixir, Clojure, PHP, Shell, JSON, YAML, TOML, HTML, CSS, and more. For unsupported languages, the interceptor falls back to the original unified diff for that file.

---

## See Also

- [Transforms Reference](transforms.md) — Other compression transforms
- [Compression Overview](compression.md) — Universal compression
- [diff_compressor.py](https://github.com/chopratejas/cutctx/blob/main/cutctx/transforms/diff_compressor.py) — Source
