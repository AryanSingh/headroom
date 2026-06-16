"""Memory export policy and format.

Implements the B5 memory portability policy. Headroom guarantees that
raw memory content and its source provenance are always portable and
can be exported without friction. 

However, the proprietary intelligence layers — value models, curation
graphs, semantic embeddings, and derived relationships — are the
product of the data flywheel and are not included in raw exports.
"""

from typing import Any


def export_raw(memories: list[Any]) -> list[dict[str, Any]]:
    """Export memory content and provenance, stripping intelligence layers.
    
    Args:
        memories: List of Memory or MemoryRecord objects.
        
    Returns:
        List of dicts containing only portable fields.
    """
    portable = []
    for memory in memories:
        # Support both Memory and MemoryRecord shapes
        m_dict = memory.model_dump() if hasattr(memory, "model_dump") else getattr(memory, "__dict__", {})
        if not m_dict and isinstance(memory, dict):
            m_dict = memory

        portable.append({
            "id": m_dict.get("id"),
            "content": m_dict.get("content", ""),
            "created_at": m_dict.get("created_at"),
            "valid_from": m_dict.get("valid_from"),
            "valid_until": m_dict.get("valid_until"),
            "provenance": m_dict.get("provenance", {}),
            # Explicitly omitted: value_score, importance, access_count,
            # promotion_chain, embedding, entity_refs, related_entities
        })
    return portable
