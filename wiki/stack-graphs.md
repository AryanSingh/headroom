# Stack Graphs — Cross-File Code Navigation

Cutctx's stack graphs integration uses GitHub's [`tree-sitter-stack-graphs`](https://github.com/github/stack-graphs) to provide **deterministic, syntax-based cross-file code navigation**. When enabled, the proxy builds a precise symbol graph of your codebase — resolving go-to-definition across files without embeddings, ML models, or external APIs.

## Overview

### The Problem

LLM coding agents often read files to understand symbol definitions: "Where is this function defined? What does this import resolve to?" Without a code navigation system, the agent must either:

1. **Read every file** — expensive in tokens and latency
2. **Use Grep** — returns text matches, not semantic resolution (e.g. can't distinguish definition from usage)
3. **Use Graphify** — provides semantic relationships (call graphs, clustering) but is approximate, not exact

### What Stack Graphs Add

Stack graphs provide **exact, deterministic symbol resolution** — the same kind of go-to-definition you get from an IDE or language server:

- **Cross-file resolution** — following imports, class inheritance, and function calls across module boundaries
- **Syntax-based** — uses tree-sitter AST parsing + scope rules; no ML, no hallucinations
- **File-incremental** — re-indexes only changed files, not the whole project
- **Deterministic** — same code always yields the same graph; no embedding similarity thresholds

### How They Differ from Graphify

| Aspect | Stack Graphs | Graphify (Knowledge Graph) |
|--------|-------------|---------------------------|
| **Type** | Exact syntax-based | Semantic knowledge graph |
| **Granularity** | Per-symbol (go-to-definition) | Per-node (BFS subgraph) |
| **Cross-file** | ✅ Full import resolution | ✅ Relationships + clustering |
| **Deterministic** | ✅ Yes (same code → same graph) | ❌ No (ML-based clustering) |
| **ML required** | ❌ No | ✅ Requires `graphifyy` + `networkx` |
| **Use case** | "Where is this defined?" | "What is related to this code?" |
| **Language support** | Python, JavaScript, TypeScript | Any with tree-sitter grammar |

Stack graphs and Graphify are **complementary**: stack graphs tell the agent exactly where a symbol is defined; Graphify tells the agent what code is semantically related.

---

## Enabling Stack Graphs

### CLI Flag

```bash
cutctx proxy --stack-graph
```

### Environment Variable

```bash
export CUTCTX_STACK_GRAPH=1
cutctx proxy
```

When enabled, the proxy:
1. Creates a `StackGraphResolver` at startup
2. Indexes the current project directory in a background thread (up to 1000 files by default)
3. Exposes resolution via the proxy pipeline (future: interceptors can use it to inline definitions)
4. Keeps the graph incrementally updated via `CodeGraphWatcher` — files changed after startup are re-indexed automatically

### Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `--stack-graph` / `CUTCTX_STACK_GRAPH` | `false` | Enable stack graph indexing |
| `max_files` (hardcoded) | 1000 | Maximum files to index per project |

---

## Status & Stats

Stack graph status is exposed at the `/stats` endpoint under the `stack_graph` key:

```json
{
  "stack_graph": {
    "enabled": true,
    "files_indexed": 42,
    "nodes": 2847
  }
}
```

---

## Supported Languages

| Language | Extension | TSG Rules | Status |
|----------|-----------|-----------|--------|
| **Python** | `.py` | ✅ Bundled | Full support |
| **JavaScript** | `.js`, `.jsx` | ✅ Bundled | Full support |
| **TypeScript** | `.ts`, `.tsx` | ✅ Bundled (uses JS grammar) | Full support |

Additional languages can be added by bundling TSG rule files. See the Rust module at `crates/cutctx-core/src/stack_graph/tsg_rules/` for examples.

---

## Architecture

```
Proxy startup:
┌────────────────────────────────────────────┐
│  cutctx proxy --stack-graph                │
│                                            │
│  1. cli/proxy.py parses --stack-graph flag │
│  2. models.py sets stack_graph_enabled=True│
│  3. server.py creates StackGraphResolver   │
│  4. Background thread:                     │
│     resolver.index_project(cwd)            │
└──────────────────┬─────────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────────┐
│  StackGraphResolver (Python facade)        │
│  cutctx/graph/resolver.py                  │
│                                            │
│  index_file(path) → Rust add_file()        │
│  resolve(path, line, col) → Rust resolve() │
│  file_count / node_count → stats           │
└──────────────────┬─────────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────────┐
│  PyStackGraphManager (PyO3 binding)        │
│  crates/cutctx-py/src/lib.rs               │
│                                            │
│  Thread-safe Mutex<StackGraphManager>      │
│  PyO3 method forwarding                    │
└──────────────────┬─────────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────────┐
│  StackGraphManager (Rust core)             │
│  crates/cutctx-core/src/stack_graph/       │
│                                            │
│  register_language(lang)                   │
│    → load tree-sitter grammar              │
│    → load TSG rules                        │
│                                            │
│  add_file(path, source)                    │
│    → detect language from extension        │
│    → parse AST with tree-sitter            │
│    → apply TSG rules to build graph        │
│                                            │
│  resolve_reference(path, line, col)        │
│    → locate symbol in graph                │
│    → BFS through stack graph paths         │
│    → return target file/line/col           │
└────────────────────────────────────────────┘
```

### Incremental Updates

When `CodeGraphWatcher` detects a file change, it calls `resolver.index_file(path)` automatically:

```python
# cutctx/graph/watcher.py
if _stack_graph_resolver is not None:
    _stack_graph_resolver.index_file(str(changed_path))
```

This keeps the stack graph up to date without full re-indexing.

### Files

| File | Purpose |
|------|---------|
| `crates/cutctx-core/src/stack_graph/mod.rs` | Rust `StackGraphManager` — core graph management, language registration, TSG rule loading, symbol resolution |
| `crates/cutctx-core/src/stack_graph/tsg_rules/python.tsg` | Python TSG definitions for scope and symbol resolution |
| `crates/cutctx-core/src/stack_graph/tsg_rules/javascript.tsg` | JavaScript/TypeScript TSG definitions |
| `crates/cutctx-py/src/lib.rs` | PyO3 binding — `PyStackGraphManager` class exposed as `cutctx._core.StackGraphManager` |
| `cutctx/graph/resolver.py` | Python `StackGraphResolver` facade — `index_project()`, `index_file()`, `resolve()` |
| `cutctx/graph/__init__.py` | Re-exports `StackGraphResolver`, `stack_graph_available()` |
| `cutctx/cli/proxy.py` | `--stack-graph` CLI flag |
| `cutctx/proxy/models.py` | `stack_graph_enabled: bool` field on `ProxyConfig` |
| `cutctx/proxy/server.py` | Startup wiring — creates resolver, background indexing, `/stats` exposure |
| `cutctx/graph/watcher.py` | Incremental re-indexing on file change |
| `crates/cutctx-core/tests/test_stack_graphs.rs` | Rust integration tests |
| `tests/test_stack_graph_resolver.py` | Python integration tests |

---

## Usage

### Programmatic (Python SDK)

```python
from cutctx.graph import StackGraphResolver

resolver = StackGraphResolver()

# Index a project
count = resolver.index_project("/path/to/my-project")
print(f"Indexed {count} files")

# Index a single file
resolver.index_file("/path/to/my-project/src/main.py")

# Resolve a symbol reference
result = resolver.resolve(
    path="/path/to/my-project/src/main.py",
    line=42,
    column=10,
)
if result:
    print(f"Defined at: {result['target_file']}:{result['target_line']}:{result['target_column']}")
    print(f"Symbol: {result['symbol_name']}")
else:
    print("Could not resolve reference")

# Stats
print(f"Files: {resolver.file_count}, Nodes: {resolver.node_count}")

# Clear and re-index
resolver.clear()
```

### Check Availability

```python
from cutctx.graph import stack_graph_available

if stack_graph_available():
    resolver = StackGraphResolver()
else:
    print("Stack graphs not available (cutctx-core wheel may be missing)")
```

---

## Limitations

1. **Language coverage**: Currently supports Python, JavaScript, and TypeScript. Other languages (Rust, Go, Java) have tree-sitter grammars registered but no TSG rules yet — they register file-level scope only.
2. **Large projects**: Indexing is bounded by `max_files=1000` by default. Projects exceeding this will see partial coverage.
3. **First-build latency**: Initial indexing of a large project takes a few seconds in the background thread.
4. **TSG rule maturity**: The bundled TSG rules cover common patterns (imports, class/function definitions) but may not handle all language idioms. Resolution falls back gracefully when no path is found.
5. **No dynamic resolution**: Stack graphs are static — they resolve based on source code structure, not runtime type information.
