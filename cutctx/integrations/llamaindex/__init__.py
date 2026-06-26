"""LlamaIndex integration for Cutctx.

Provides:
- CutctxNodePostprocessor: drop-in NodePostprocessor for any LlamaIndex pipeline.
  Filters retrieved nodes by relevance, then optionally compresses surviving content.

Install: pip install cutctx-ai[llamaindex]

Example:
    from llama_index.core import VectorStoreIndex
    from cutctx.integrations.llamaindex import CutctxNodePostprocessor

    index = VectorStoreIndex.from_documents(documents)
    query_engine = index.as_query_engine(
        node_postprocessors=[
            CutctxNodePostprocessor(
                top_n=8,           # keep at most 8 nodes
                min_score=0.25,    # drop nodes scoring below 0.25
                compress=True,     # also compress surviving node text
            )
        ]
    )
    response = query_engine.query("How does authentication work?")
"""

from .postprocessor import CutctxNodePostprocessor, NodeFilterMetrics

__all__ = ["CutctxNodePostprocessor", "NodeFilterMetrics"]
