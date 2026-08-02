from __future__ import annotations

import hashlib
import hmac
import json
import zipfile
from pathlib import Path

import pytest

from scripts.verify_ee_wheel import WheelVerificationError, verify_wheel


def _signed_manifest(files: dict[str, bytes], secret: str) -> dict[str, object]:
    payload: dict[str, object] = {
        "version": "1",
        "algorithm": "sha256",
        "files": {name.removeprefix("cutctx_ee/"): hashlib.sha256(data).hexdigest() for name, data in files.items()},
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return {**payload, "signature": hmac.new(secret.encode(), canonical, hashlib.sha256).hexdigest()}


def _write_wheel(
    tmp_path: Path,
    files: dict[str, bytes],
    secret: str,
    *,
    manifest_files: dict[str, bytes] | None = None,
    include_manifest: bool = True,
) -> Path:
    wheel = tmp_path / "cutctx_ee-1.2.3-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("cutctx_ee/__init__.py", '__version__ = "1.2.3"\n')
        for name, data in files.items():
            archive.writestr(name, data)
        if include_manifest:
            archive.writestr(
                "cutctx_ee/MANIFEST.sha256.json",
                json.dumps(_signed_manifest(manifest_files or files, secret)),
            )
    return wheel


def test_verify_wheel_accepts_signed_native_payload(tmp_path: Path) -> None:
    secret = "test-secret"
    wheel = _write_wheel(tmp_path, {"cutctx_ee/module.abi3.so": b"native"}, secret)

    result = verify_wheel(wheel, secret)

    assert result["native_module_count"] == 1
    assert result["manifest_sha256"]


def test_verify_wheel_rejects_changed_native_payload(tmp_path: Path) -> None:
    secret = "test-secret"
    wheel = _write_wheel(
        tmp_path,
        {"cutctx_ee/module.abi3.so": b"changed"},
        secret,
        manifest_files={"cutctx_ee/module.abi3.so": b"native"},
    )

    with pytest.raises(WheelVerificationError, match="MISMATCH"):
        verify_wheel(wheel, secret)


def test_verify_wheel_rejects_missing_manifest(tmp_path: Path) -> None:
    wheel = _write_wheel(
        tmp_path,
        {"cutctx_ee/module.abi3.so": b"native"},
        "test-secret",
        include_manifest=False,
    )

    with pytest.raises(WheelVerificationError, match="MANIFEST"):
        verify_wheel(wheel, "test-secret")


def test_verify_wheel_rejects_ee_source_leak(tmp_path: Path) -> None:
    secret = "test-secret"
    wheel = _write_wheel(
        tmp_path,
        {"cutctx_ee/module.abi3.so": b"native", "cutctx_ee/proprietary.py": b"secret source"},
        secret,
    )

    with pytest.raises(WheelVerificationError, match="source"):
        verify_wheel(wheel, secret)
