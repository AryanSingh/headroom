# crates/cutctx-core/src/stack_graph/

## Responsibility
Indexes Python and JavaScript-family source into stack graphs and resolves cross-file definitions, references, reachability, and callers.

## Design
`StackGraphManager` owns parsers, graph arenas, partial paths, file handles, and a source cache. Tree-sitter queries construct scope/symbol nodes; embedded `.tsg` files document graph rules. Because the graph is append-only, removal/reindex rebuilds from cached sources.

## Flow
Register/detect language -> parse each file -> add scopes, definitions, references, and edges -> BFS APIs traverse forward or reverse with depth/size guards -> return `ResolvedReference` locations with confidence.

## Integration
- Exposed by `cutctx-core` and wrapped by `cutctx-py`.
- Uses tree-sitter Python/JavaScript grammars, stack-graphs, LSP positions, and streaming query iteration.
