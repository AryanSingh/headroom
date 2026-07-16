# cutctx/relevance/

## Responsibility
Ranks context candidates by lexical, embedding, or hybrid relevance.

## Design
A common scorer contract supports BM25 and embedding strategies; hybrid scoring combines normalized components.

## Flow
Candidates and query enter a scorer, similarities are computed, and ranked/truncated results return to selection.

## Integration
Used by compression, retrieval, and memory ranking; embedding mode uses configured adapters.
