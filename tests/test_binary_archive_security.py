"""Security contracts for managed third-party binary archives."""

from __future__ import annotations

import hashlib
import io
import tarfile
from pathlib import Path

import pytest

from cutctx.graph import installer as graph_installer
from cutctx.install.binary_archive import install_verified_archive
from cutctx.lean_ctx import installer as lean_ctx_installer
from cutctx.rtk import installer as rtk_installer


def _tar_archive(*, symlink: bool = False) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        member = tarfile.TarInfo("dist/tool")
        if symlink:
            member.type = tarfile.SYMTYPE
            member.linkname = "/tmp/attacker-controlled"
            archive.addfile(member)
        else:
            payload = b"verified binary"
            member.size = len(payload)
            archive.addfile(member, io.BytesIO(payload))
    return buffer.getvalue()


def test_verified_archive_rejects_digest_mismatch(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        install_verified_archive(
            _tar_archive(),
            expected_sha256="0" * 64,
            target_path=tmp_path / "tool",
            archive_type="tar.gz",
        )


def test_verified_archive_rejects_symlink_member(tmp_path: Path) -> None:
    payload = _tar_archive(symlink=True)
    with pytest.raises(RuntimeError, match="regular file"):
        install_verified_archive(
            payload,
            expected_sha256=hashlib.sha256(payload).hexdigest(),
            target_path=tmp_path / "tool",
            archive_type="tar.gz",
        )


def test_verified_archive_atomically_writes_regular_binary(tmp_path: Path) -> None:
    payload = _tar_archive()
    target = tmp_path / "tool"
    target.symlink_to(tmp_path / "must-not-be-written")

    install_verified_archive(
        payload,
        expected_sha256=hashlib.sha256(payload).hexdigest(),
        target_path=target,
        archive_type="tar.gz",
    )

    assert target.is_file()
    assert not target.is_symlink()
    assert target.read_bytes() == b"verified binary"
    assert not (tmp_path / "must-not-be-written").exists()


def test_pinned_binary_versions_cover_every_supported_target() -> None:
    assert len(graph_installer._PINNED_ARCHIVE_SHA256) == 5
    assert len(lean_ctx_installer._PINNED_ARCHIVE_SHA256) == 7
    assert len(rtk_installer._PINNED_ARCHIVE_SHA256) == 5
    for mapping in (
        graph_installer._PINNED_ARCHIVE_SHA256,
        lean_ctx_installer._PINNED_ARCHIVE_SHA256,
        rtk_installer._PINNED_ARCHIVE_SHA256,
    ):
        assert all(len(digest) == 64 for digest in mapping.values())


def test_codebase_memory_windows_release_uses_published_zip_asset() -> None:
    url, archive_type = graph_installer._get_download_url("v0.9.0", "windows-amd64")

    assert url.endswith("/codebase-memory-mcp-windows-amd64.zip")
    assert archive_type == "zip"
