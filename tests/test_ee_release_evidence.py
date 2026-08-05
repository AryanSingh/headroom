from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from pathlib import Path

from scripts.ee_release_evidence import build_release_evidence


def test_release_evidence_binds_wheel_and_manifest_hashes(tmp_path: Path) -> None:
    wheel = tmp_path / "cutctx_ee-1.2.3.whl"
    wheel.write_bytes(b"wheel")

    evidence = build_release_evidence(
        wheel,
        {
            "wheel": wheel.name,
            "wheel_sha256": sha256(b"wheel").hexdigest(),
            "manifest_sha256": "abc",
            "native_module_count": 1,
            "native_modules": ["module.abi3.so"],
        },
        git_sha="deadbeef",
        version="1.2.3",
        created_at=datetime(2026, 8, 2, 0, 0, 0),
    )

    assert evidence["git_sha"] == "deadbeef"
    assert evidence["version"] == "1.2.3"
    assert evidence["wheel_sha256"] == sha256(b"wheel").hexdigest()
    assert evidence["manifest_sha256"] == "abc"
    assert evidence["native_modules"] == ["module.abi3.so"]
    assert evidence["verification_passed"] is True
    assert evidence["created_at"] == "2026-08-02T00:00:00+00:00"


def test_release_evidence_rejects_verification_for_different_wheel(tmp_path: Path) -> None:
    wheel = tmp_path / "cutctx_ee-1.2.3.whl"
    wheel.write_bytes(b"wheel")

    import pytest

    with pytest.raises(ValueError, match="different wheel"):
        build_release_evidence(
            wheel,
            {
                "wheel": "other.whl",
                "wheel_sha256": sha256(b"wheel").hexdigest(),
                "manifest_sha256": "abc",
                "native_module_count": 1,
                "native_modules": ["module.abi3.so"],
            },
            git_sha="deadbeef",
            version="1.2.3",
        )
