"""Fail-closed installation of pinned third-party binary archives."""

from __future__ import annotations

import hashlib
import hmac
import io
import os
import re
import stat
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Literal

MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_BINARY_BYTES = 128 * 1024 * 1024
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _verified_digest(data: bytes, expected_sha256: str) -> None:
    expected = expected_sha256.strip().lower()
    if not _SHA256_RE.fullmatch(expected):
        raise RuntimeError("A valid pinned SHA-256 digest is required for binary installation")
    actual = hashlib.sha256(data).hexdigest()
    if not hmac.compare_digest(actual, expected):
        raise RuntimeError(
            f"Binary archive SHA-256 mismatch (expected {expected}, got {actual})"
        )


def _read_tar_binary(data: bytes, binary_name: str) -> bytes:
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        matches = [member for member in archive.getmembers() if Path(member.name).name == binary_name]
        if len(matches) != 1:
            raise RuntimeError(f"Expected exactly one {binary_name!r} binary in archive")
        member = matches[0]
        if not member.isfile():
            raise RuntimeError("Binary archive member must be a regular file")
        if member.size < 1 or member.size > MAX_BINARY_BYTES:
            raise RuntimeError("Binary archive member has an unsafe size")
        source = archive.extractfile(member)
        if source is None:
            raise RuntimeError("Binary archive member could not be read")
        payload = source.read(MAX_BINARY_BYTES + 1)
    if len(payload) != member.size or len(payload) > MAX_BINARY_BYTES:
        raise RuntimeError("Binary archive member size did not match its metadata")
    return payload


def _read_zip_binary(data: bytes, binary_name: str) -> bytes:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        matches = [info for info in archive.infolist() if Path(info.filename).name == binary_name]
        if len(matches) != 1:
            raise RuntimeError(f"Expected exactly one {binary_name!r} binary in archive")
        member = matches[0]
        file_type = (member.external_attr >> 16) & 0o170000
        if member.is_dir() or file_type == stat.S_IFLNK:
            raise RuntimeError("Binary archive member must be a regular file")
        if member.file_size < 1 or member.file_size > MAX_BINARY_BYTES:
            raise RuntimeError("Binary archive member has an unsafe size")
        with archive.open(member) as source:
            payload = source.read(MAX_BINARY_BYTES + 1)
    if len(payload) != member.file_size or len(payload) > MAX_BINARY_BYTES:
        raise RuntimeError("Binary archive member size did not match its metadata")
    return payload


def install_verified_archive(
    data: bytes,
    *,
    expected_sha256: str,
    target_path: Path,
    archive_type: Literal["tar.gz", "zip"],
) -> Path:
    """Verify, safely extract, and atomically replace a managed binary."""
    if len(data) < 1 or len(data) > MAX_ARCHIVE_BYTES:
        raise RuntimeError("Binary archive has an unsafe size")
    _verified_digest(data, expected_sha256)

    binary_name = target_path.name
    try:
        payload = (
            _read_tar_binary(data, binary_name)
            if archive_type == "tar.gz"
            else _read_zip_binary(data, binary_name)
        )
    except (tarfile.TarError, zipfile.BadZipFile) as exc:
        raise RuntimeError(f"Failed to extract verified binary archive: {exc}") from exc

    target_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=f".{binary_name}.", dir=target_path.parent, delete=False
        ) as temporary:
            temporary.write(payload)
            temporary.flush()
            os.fsync(temporary.fileno())
            os.fchmod(temporary.fileno(), 0o755)
            temporary_path = Path(temporary.name)
        os.replace(temporary_path, target_path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return target_path


__all__ = ["install_verified_archive"]
