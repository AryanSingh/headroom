from __future__ import annotations

import hashlib
from pathlib import Path

from .harness_adapter import ArtifactRef


class ArtifactBlobStore:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def _path_for(self, blob_id: str) -> Path:
        normalized = blob_id.lower()
        if len(normalized) != 64 or any(c not in "0123456789abcdef" for c in normalized):
            raise ValueError(f"invalid blob_id: {blob_id!r}")
        return self.root / "sha256" / normalized[:2] / normalized

    @staticmethod
    def _hash_bytes(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def put(
        self,
        data: bytes,
        *,
        media_type: str = "application/octet-stream",
        provenance: dict[str, str] | None = None,
    ) -> ArtifactRef:
        blob_id = self._hash_bytes(data)
        path = self._path_for(blob_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(data)
        return ArtifactRef(
            blob_id=blob_id,
            media_type=media_type,
            byte_size=len(data),
            provenance=dict(provenance or {}),
        )

    def ref_for_text(
        self,
        text: str,
        *,
        media_type: str = "text/plain",
        provenance: dict[str, str] | None = None,
    ) -> ArtifactRef:
        return self.put(text.encode("utf-8"), media_type=media_type, provenance=provenance)

    def exists(self, blob_id: str) -> bool:
        return self._path_for(blob_id).exists()

    def get(self, blob_id: str) -> bytes:
        path = self._path_for(blob_id)
        if not path.exists():
            raise FileNotFoundError(blob_id)
        return path.read_bytes()
