"""Regression coverage for the release artifact leak/integrity guard."""

from __future__ import annotations

import importlib.util
import zipfile
import zlib
from pathlib import Path


def _load_guard():
    path = Path(__file__).parents[1] / "scripts" / "assert_oss_wheel_clean.py"
    spec = importlib.util.spec_from_file_location("oss_wheel_guard", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_guard_accepts_a_valid_oss_wheel(tmp_path: Path) -> None:
    guard = _load_guard()
    wheel = tmp_path / "cutctx_ai-0.30.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(guard.EXPECT_PRESENT, "# Apache shim\n")

    assert guard.main(["guard", str(tmp_path)]) == 0


def test_guard_rejects_a_wheel_with_a_corrupt_member(monkeypatch, tmp_path: Path, capsys) -> None:
    guard = _load_guard()
    wheel = tmp_path / "cutctx_ai-0.30.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(guard.EXPECT_PRESENT, "# Apache shim\n")

    def corrupt_members(_: Path) -> list[str]:
        raise ValueError("invalid compressed data in sboms/cutctx-py.cyclonedx.json")

    monkeypatch.setattr(guard, "_members", corrupt_members)

    assert guard.main(["guard", str(tmp_path)]) == 1
    assert "CORRUPT ARTIFACT" in capsys.readouterr().out


def test_guard_reports_decompression_errors(monkeypatch, tmp_path: Path, capsys) -> None:
    guard = _load_guard()
    wheel = tmp_path / "cutctx_ai-0.30.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(guard.EXPECT_PRESENT, "# Apache shim\n")

    def decompression_error(_: Path) -> list[str]:
        raise zlib.error("invalid block type")

    monkeypatch.setattr(guard, "_members", decompression_error)

    assert guard.main(["guard", str(tmp_path)]) == 1
    assert "CORRUPT ARTIFACT" in capsys.readouterr().out
