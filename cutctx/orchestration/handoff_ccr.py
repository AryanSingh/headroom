from __future__ import annotations

from cutctx.cache.compression_store import CompressionStore

from .artifact_store import ArtifactBlobStore
from .harness_adapter import ArtifactRef


def compress_artifact_for_handoff(
    store: ArtifactBlobStore,
    ccr: CompressionStore,
    ref: ArtifactRef,
) -> ArtifactRef:
    raw = store.get(ref.blob_id).decode("utf-8", errors="replace")
    digest = f"[cutctx-handoff blob={ref.blob_id[:12]}… chars={len(raw)}]"
    ccr_hash = ccr.store(
        original=raw,
        compressed=digest,
        original_tokens=max(1, len(raw) // 4),
        compressed_tokens=max(1, len(digest) // 4),
        compression_strategy="handoff_boundary",
    )
    provenance = dict(ref.provenance)
    provenance["handoff_ccr"] = "true"
    return ArtifactRef(
        blob_id=ref.blob_id,
        media_type=ref.media_type,
        byte_size=ref.byte_size,
        ccr_hash=ccr_hash,
        provenance=provenance,
    )


def handoff_payload_from_artifacts(refs: list[ArtifactRef]) -> dict[str, object]:
    return {"artifact_refs": [{"blob_id": ref.blob_id, "ccr_hash": ref.ccr_hash} for ref in refs]}
