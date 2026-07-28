from __future__ import annotations

import pytest

from cutctx.orchestration.artifact_store import ArtifactBlobStore


def test_put_is_content_addressed_and_idempotent(tmp_path) -> None:
    store = ArtifactBlobStore(tmp_path / "artifacts")
    data = b"diff --git a/foo.py\n"
    first = store.put(data, media_type="text/x-patch", provenance={"task": "implement"})
    second = store.put(data, media_type="text/x-patch")
    assert first.blob_id == second.blob_id
    assert first.byte_size == len(data)
    assert store.exists(first.blob_id)
    assert store.get(first.blob_id) == data


def test_ref_for_text_stores_utf8(tmp_path) -> None:
    store = ArtifactBlobStore(tmp_path / "artifacts")
    ref = store.ref_for_text("plan: add harness adapter", provenance={"role": "planner"})
    assert ref.media_type == "text/plain"
    assert store.get(ref.blob_id).decode("utf-8") == "plan: add harness adapter"


def test_get_unknown_blob_raises(tmp_path) -> None:
    store = ArtifactBlobStore(tmp_path / "artifacts")
    with pytest.raises(FileNotFoundError):
        store.get("0" * 64)
