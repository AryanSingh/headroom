"""Tests for host-target rtk installation overrides."""

from __future__ import annotations

import hashlib
import io
import tarfile
from pathlib import Path
from unittest.mock import patch

from cutctx.rtk import RTK_VERSION, get_rtk_path, get_rtk_version, installer


def test_managed_rtk_pin_matches_verified_upstream_release() -> None:
    assert RTK_VERSION == "v0.43.0"
    assert installer._PINNED_ARCHIVE_SHA256 == {
        (
            "v0.43.0",
            "aarch64-apple-darwin",
        ): "8a17e49acbd378997eb21d0eb6f7f861111f35b4fc9b1c74edf4c7448e576c65",
        (
            "v0.43.0",
            "aarch64-unknown-linux-gnu",
        ): "5519f7ca12e5c143a609f0d28a0a77b97413a8dce31c2681f1a41c24519a8731",
        (
            "v0.43.0",
            "x86_64-apple-darwin",
        ): "a85f60e2637811be68366208b8d8b9c5ba1b748cb5df4477ab20cd73d3c5d9f8",
        (
            "v0.43.0",
            "x86_64-pc-windows-msvc",
        ): "7c5e4a2ef816a4d4ed947ddd74ca3df851fc39ea87d49a3ca2bf3abc515a016b",
        (
            "v0.43.0",
            "x86_64-unknown-linux-musl",
        ): "ff8a1e7766496e175291a85aeca1dc97c9ff6df33e51e5893d1fbc78fea2a609",
    }


def test_get_rtk_version_parses_system_binary_output(tmp_path: Path) -> None:
    binary = tmp_path / "rtk"
    binary.write_bytes(b"binary")

    with patch("cutctx.rtk.subprocess.run") as run:
        run.return_value.returncode = 0
        run.return_value.stdout = "rtk 0.43.0\n"
        assert get_rtk_version(binary) == "v0.43.0"


def test_ensure_rtk_keeps_mismatched_system_binary(monkeypatch, tmp_path: Path) -> None:
    system_binary = tmp_path / "rtk"
    system_binary.write_bytes(b"binary")
    monkeypatch.setattr("cutctx.rtk.get_rtk_path", lambda: system_binary)
    monkeypatch.setattr("cutctx.rtk.get_rtk_version", lambda _path: "v0.42.0")

    with patch.object(installer.logger, "warning") as warning:
        assert installer.ensure_rtk() == system_binary

    warning.assert_called_once()


def test_ensure_rtk_diagnostic_uses_explicit_requested_version(monkeypatch, tmp_path: Path) -> None:
    system_binary = tmp_path / "rtk"
    system_binary.write_bytes(b"binary")
    monkeypatch.setattr("cutctx.rtk.get_rtk_path", lambda: system_binary)
    monkeypatch.setattr("cutctx.rtk.get_rtk_version", lambda _path: "v0.42.0")

    with patch.object(installer.logger, "warning") as warning:
        assert installer.ensure_rtk("v0.42.0") == system_binary

    warning.assert_not_called()


def test_get_rtk_path_finds_windows_managed_binary(tmp_path: Path) -> None:
    managed_dir = tmp_path / ".cutctx" / "bin"
    managed_dir.mkdir(parents=True)
    managed_path = managed_dir / "rtk.exe"
    managed_path.write_bytes(b"binary")

    with patch("cutctx.rtk.RTK_BIN_DIR", managed_dir):
        with patch("cutctx.rtk.RTK_BIN_PATH", managed_dir / "rtk"):
            with patch("cutctx.rtk.shutil.which", return_value=None):
                assert get_rtk_path() == managed_path


def test_get_target_triple_uses_override(monkeypatch) -> None:
    monkeypatch.setenv("CUTCTX_RTK_TARGET", "x86_64-pc-windows-msvc")
    assert installer._get_target_triple() == "x86_64-pc-windows-msvc"


def test_download_rtk_skips_verify_for_non_native_target(monkeypatch, tmp_path: Path) -> None:
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w:gz") as tf:
        info = tarfile.TarInfo(name="rtk")
        payload = b"fake-binary"
        info.size = len(payload)
        tf.addfile(info, io.BytesIO(payload))
    archive_bytes = archive.getvalue()
    monkeypatch.setenv("CUTCTX_RTK_SHA256", hashlib.sha256(archive_bytes).hexdigest())

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return archive_bytes

    monkeypatch.setenv("CUTCTX_RTK_TARGET", "x86_64-apple-darwin")

    with patch.object(installer, "RTK_BIN_DIR", tmp_path):
        with patch.object(installer, "urlopen", return_value=_Response()):
            with patch.object(installer.subprocess, "run") as subprocess_run:
                installed_path = installer.download_rtk("v0.43.0")

    assert installed_path == tmp_path / "rtk"
    assert installed_path.exists()
    subprocess_run.assert_not_called()
