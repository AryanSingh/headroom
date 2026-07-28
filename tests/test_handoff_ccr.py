from __future__ import annotations

from cutctx.cache.compression_store import CompressionStore
from cutctx.orchestration.artifact_store import ArtifactBlobStore
from cutctx.orchestration.handoff_ccr import compress_artifact_for_handoff, handoff_payload_from_artifacts


def test_compress_artifact_attaches_ccr_hash(tmp_path) -> None:
    blobs = ArtifactBlobStore(tmp_path / "artifacts")
    ccr = CompressionStore(default_ttl=3600)
    original = blobs.ref_for_text("x" * 5000, media_type="text/plain")
    compressed = compress_artifact_for_handoff(blobs, ccr, original)
    assert compressed.blob_id == original.blob_id
    assert compressed.ccr_hash
    assert ccr.exists(compressed.ccr_hash)


def test_handoff_payload_lists_refs_not_transcripts() -> None:
    from cutctx.orchestration.harness_adapter import ArtifactRef

    refs = [ArtifactRef(blob_id="a" * 64, ccr_hash="deadbeef")]
    payload = handoff_payload_from_artifacts(refs)
    assert payload["artifact_refs"] == [{"blob_id": "a" * 64, "ccr_hash": "deadbeef"}]
    assert "transcript" not in payload
