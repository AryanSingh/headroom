"""Black-box tests for the retired standalone binary installer."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
INSTALLER = ROOT / "scripts" / "install-binary.sh"


def _run(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(exist_ok=True)
    marker = tmp_path / "unexpected-command"
    for command in ("curl", "cosign", "uv", "pipx", "pip", "sed"):
        stub = fake_bin / command
        stub.write_text(
            f"#!/bin/sh\nprintf '%s\\n' {command} >> '{marker}'\nexit 99\n",
            encoding="utf-8",
        )
        stub.chmod(0o755)

    env = os.environ.copy()
    env.pop("CUTCTX_VERSION", None)
    env.pop("PREFIX", None)
    env.update({"HOME": str(tmp_path / "home"), "PATH": f"{fake_bin}:/usr/bin:/bin"})
    result = subprocess.run(
        ["/bin/bash", str(INSTALLER), *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert not marker.exists(), "compatibility shim must not download or execute an installer"
    return result


def test_fails_closed_with_supported_install_commands(tmp_path: Path) -> None:
    result = _run(tmp_path)

    assert result.returncode != 0
    assert "Standalone binary installation is not supported" in result.stderr
    assert 'uv tool install --python 3.13 "cutctx-ai[proxy]"' in result.stderr
    assert 'pipx install --python python3.13 "cutctx-ai[proxy]"' in result.stderr


def test_version_argument_pins_supported_package_install(tmp_path: Path) -> None:
    result = _run(tmp_path, "--version", "1.2.3")

    assert result.returncode != 0
    assert '"cutctx-ai[proxy]==1.2.3"' in result.stderr
    assert "1.2.3" in result.stderr


def test_prefix_argument_emits_prefix_aware_pipx_command(tmp_path: Path) -> None:
    prefix = tmp_path / "custom prefix"

    result = _run(tmp_path, "--prefix", str(prefix))

    assert result.returncode != 0
    assert f"PIPX_BIN_DIR='{prefix}/bin'" in result.stderr
    assert f"PIPX_HOME='{prefix}/share/pipx'" in result.stderr


@pytest.mark.parametrize(
    "args,error",
    [
        (("--bogus",), "Unknown option: --bogus"),
        (("--version",), "--version requires a value"),
        (("--version", "--help"), "--version requires a value"),
        (("--prefix",), "--prefix requires a value"),
        (("--prefix", "--help"), "--prefix requires a value"),
        (("--version", "01.2.3"), "Invalid version: 01.2.3"),
        (("--version", "1.2.3.."), "Invalid version: 1.2.3.."),
        (("--version", "1.2.3", "--version", "2.3.4"), "Duplicate option: --version"),
        (("--prefix", "/tmp/a", "--prefix", "/tmp/b"), "Duplicate option: --prefix"),
    ],
)
def test_rejects_invalid_arguments(tmp_path: Path, args: tuple[str, ...], error: str) -> None:
    result = _run(tmp_path, *args)

    assert result.returncode != 0
    assert error in result.stderr


def test_help_is_successful_and_truthful(tmp_path: Path) -> None:
    result = _run(tmp_path, "--help")

    assert result.returncode == 0
    assert "compatibility shim" in result.stdout
    assert "does not download or execute binaries" in result.stdout
