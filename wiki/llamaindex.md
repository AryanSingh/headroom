# LlamaIndex Integration

`CutCtxNodePostprocessor` slots into any LlamaIndex retrieval pipeline as a
standard `NodePostprocessor`. It filters retrieved nodes by relevance (dropping
off-topic results) and optionally compresses surviving node text before synthesis.

## Install

```bash
pip install cutctx-ai[llamaindex]
```

## Quick start

```python
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from headroom.integrations.llamaindex import CutCtxNodePostprocessor

documents = SimpleDirectoryReader("./data").load_data()
index = VectorStoreIndex.from_documents(documents)

query_engine = index.as_query_engine(
    similarity_top_k=20,                         # retrieve 20 candidates
    node_postprocessors=[
        CutCtxNodePostprocessor(
            top_n=6,           # keep 6 most relevant
            min_score=0.2,     # drop anything < 0.2 relevance
            compress=True,     # compress surviving node text
        )
    ],
)

response = query_engine.query("How does authentication work?")
```

## Parameters

| Parameter | Default | Description |
|---|---|---|
| `top_n` | `10` | Max nodes to return |
| `min_score` | `0.0` | Drop nodes below this relevance score (0–1) |
| `compress` | `False` | Compress surviving node text with CutCtx |
| `scorer` | `"bm25"` | Scoring backend: `"bm25"` (default) or `"hybrid"` (needs `[relevance]`) |

## Metrics

```python
postprocessor = CutCtxNodePostprocessor(top_n=8, compress=True)
# ... run query ...
m = postprocessor.last_metrics
print(f"{m.nodes_in} → {m.nodes_out} nodes, {m.nodes_dropped} dropped")
print(f"Compression ratio: {m.compression_ratio:.2f}")
```

## With hybrid scoring (semantic + BM25)

```bash
pip install cutctx-ai[llamaindex,relevance]
```

```python
postprocessor = CutCtxNodePostprocessor(top_n=8, scorer="hybrid")
```
