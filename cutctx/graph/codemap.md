# cutctx/graph/

## Responsibility
Builds and maintains a symbol/reference graph for project-aware context selection.

## Design
Graphification, resolution, reachability, checksum-pinned helper installation, and filesystem watching are separated services over a shared graph index.

## Flow
Sources are scanned into nodes/edges, references are resolved, queries select reachable context, and watchers refresh affected state.

## Integration
Used by graph-aware proxy interceptors and CLI commands; integrates with local project files.
