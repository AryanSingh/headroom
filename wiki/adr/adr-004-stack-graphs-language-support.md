# ADR-004: Stack Graphs Initial Language Support

- **Status:** Accepted (scope expanded during implementation)
- **Date:** 2026-06-30
- **Drivers:** chopratejas

---

## Context

GitHub's [`tree-sitter-stack-graphs`](https://github.com/github/stack-graphs) provides deterministic, syntax-based cross-file code navigation (go-to-definition). Each language requires:

1. A **tree-sitter grammar** — parses source code into an AST
2. A **TSG (Tree-Sitter Graph) rule file** — defines language-specific rules for building the stack graph (scopes, references, definitions)

The initial plan proposed **Python only** for v1, with JavaScript/TypeScript deferred to v2. However, during implementation of the Rust `StackGraphManager` module (`crates/cutctx-core/src/stack_graph/mod.rs`), several factors drove scope expansion:

- **tree-sitter-javascript** grammar is an extremely small dependency (~200 KB compiled)
- The **tree-sitter-stack-graphs** test fixtures include mature JS/TSX TSG rules
- JavaScript and TypeScript are the second-most-common languages in AI coding agent workloads
- Adding both grammars in a single Cargo dependency update is cheaper than two separate releases

## Decision

**v1 supports Python + JavaScript/TypeScript**, not just Python as originally planned.

| Language | Grammar Crate | TSG Rules | Status |
|----------|--------------|-----------|--------|
| Python | `tree-sitter-python` | Bundled (`include_str!`) | Full support |
| JavaScript | `tree-sitter-javascript` | Bundled (`include_str!`) | Full support |
| TypeScript / TSX | `tree-sitter-javascript` (JS grammar) | Bundled (JS rules) | Full support (JS grammar used as TS/TSX grammar pending dedicated TS grammar) |

TSG rules are bundled as Rust `include_str!()` strings compiled directly into the `cutctx-core` crate. This means:
- No external rule files to distribute
- Rules are always in sync with the crate version
- Load time is instant (no filesystem I/O at startup)

Languages without TSG rules (Rust, Go, Java, C, C++) register file-level scope nodes only — they appear in the graph but cannot resolve cross-file references.

## Consequences

### Positive

- **Python and JS/TS coverage from day one** — covers the vast majority of AI coding agent codebases
- **No TSG file management** — bundling via `include_str!()` eliminates distribution and versioning concerns
- **Deterministic resolution** — both languages resolve exactly (no embedding thresholds, no ML)
- **Test coverage** — the Rust integration tests (`test_stack_graphs.rs`) exercise cross-file resolution in both Python and JavaScript

### Negative

- **Rust compile time** — each tree-sitter grammar is compiled to a native `.so` via Cargo; adding `tree-sitter-javascript` on top of `tree-sitter-python` adds ~2-3 minutes to first build
- **Binary size** — each grammar adds ~1-3 MB to the compiled wheel
- **TypeScript uses JS grammar** — TypeScript-specific syntax (decorators, parameter properties, enums) uses the JavaScript TSG rules, which may miss some TS-specific patterns. A dedicated `tree-sitter-typescript` grammar is a future improvement
- **Other languages wait** — Rust, Go, Java, C, C++ have grammars registered but no TSG rules. Users of those languages get scope-only fallback

### Mitigations

- CI caches compiled Rust artifacts, so the build time penalty is one-time
- Fallback behavior is explicit and logged: unsupported languages warn at `add_file()` time but do not error
- Cargo feature gates could be added in the future to allow per-language compilation (e.g., `--features stack-graphs-python-only`) if binary size becomes a concern

## Future Languages

| Language | Blocking Issue | Target |
|----------|---------------|--------|
| TypeScript (dedicated) | Dedicated TS grammar + TSG rules | v1.1 |
| Rust | TSG rules need authoring | v1.2 |
| Go | TSG rules need authoring | v1.2 |
| Java | TSG rules need authoring | v1.3 |

## Related

- [Stack Graphs Documentation](../stack-graphs.md)
- [Stack Graphs Architecture](../stack-graphs.md#architecture)
- [Integration Plan §4.3.2 — Rust Module](../plans/2026-06-30-usearch-stack-graphs-integration-plan.md#432-modrs--stackgraphmanager)
