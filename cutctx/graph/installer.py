"""Download and install codebase-memory-mcp binary from GitHub releases."""

from __future__ import annotations

import logging
import os
import platform
import shutil
from pathlib import Path
from typing import Literal
from urllib.request import urlopen

from cutctx.install.binary_archive import install_verified_archive

logger = logging.getLogger(__name__)

CBM_VERSION = "v0.9.0"
CBM_REPO = "DeusData/codebase-memory-mcp"
CBM_BIN_DIR = Path.home() / ".local" / "bin"
CBM_BIN_NAME = "codebase-memory-mcp"

GITHUB_RELEASE_URL = f"https://github.com/{CBM_REPO}/releases/download"

_PINNED_ARCHIVE_SHA256 = {
    ("v0.9.0", "darwin-amd64"): "6af3d02a27f589901fa763d3971089337bc8c9838bbed5d0cf543ca9f1a9e543",
    ("v0.9.0", "darwin-arm64"): "faa02f0404230c451a9812230394481948f80183801fa5bf67044b41c2f25ed4",
    ("v0.9.0", "linux-amd64"): "e2832a8d207c26beaa30efa6222ed4a37cb3f526ca4bee060bfbf336ed6fc679",
    ("v0.9.0", "linux-arm64"): "68a345d9a6842f02a3cb07e187b28bc38c4f3a22967f47fadbcd0757ba93a680",
    ("v0.9.0", "windows-amd64"): "92f96896f952e539f0d6cb34d7892a25064b677ccbf808b8f8310ad897e86f2c",
}


def _expected_archive_sha256(version: str, platform_name: str) -> str:
    override = os.environ.get("CUTCTX_CBM_SHA256", "").strip().lower()
    expected = override or _PINNED_ARCHIVE_SHA256.get((version, platform_name), "")
    if not expected:
        raise RuntimeError(
            "No pinned SHA-256 is available for this codebase-memory version/platform; "
            "set CUTCTX_CBM_SHA256 to the trusted release digest"
        )
    return expected


def _get_download_url(
    version: str, platform_name: str
) -> tuple[str, Literal["tar.gz", "zip"]]:
    archive_type: Literal["tar.gz", "zip"] = (
        "zip" if platform_name.startswith("windows-") else "tar.gz"
    )
    filename = f"codebase-memory-mcp-{platform_name}.{archive_type}"
    return f"{GITHUB_RELEASE_URL}/{version}/{filename}", archive_type


def _detect_platform() -> str:
    """Detect platform and return the release asset suffix."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "darwin":
        arch = "arm64" if machine == "arm64" else "amd64"
        return f"darwin-{arch}"
    elif system == "linux":
        arch = "arm64" if machine in ("aarch64", "arm64") else "amd64"
        return f"linux-{arch}"
    elif system == "windows":
        return "windows-amd64"

    raise RuntimeError(f"Unsupported platform: {system} {machine}")


def get_cbm_path() -> Path | None:
    """Find codebase-memory-mcp binary, return path or None."""
    # Check PATH first
    found = shutil.which(CBM_BIN_NAME)
    if found:
        return Path(found)

    # Check our install location
    installed = CBM_BIN_DIR / CBM_BIN_NAME
    if installed.exists() and installed.is_file():
        return installed

    return None


def download_cbm(version: str | None = None) -> Path:
    """Download codebase-memory-mcp binary from GitHub releases.

    Returns path to installed binary.
    """
    version = version or CBM_VERSION
    plat = _detect_platform()
    url, archive_type = _get_download_url(version, plat)

    CBM_BIN_DIR.mkdir(parents=True, exist_ok=True)
    target_path = CBM_BIN_DIR / CBM_BIN_NAME

    logger.info("Downloading codebase-memory-mcp %s for %s ...", version, plat)

    try:
        if not url.startswith(("http://", "https://")):
            raise ValueError(f"Invalid URL: {url}")

        with urlopen(url, timeout=60) as response:  # noqa: S310
            data = response.read()
    except Exception as e:
        raise RuntimeError(f"Failed to download codebase-memory-mcp from {url}: {e}") from e

    install_verified_archive(
        data,
        expected_sha256=_expected_archive_sha256(version, plat),
        target_path=target_path,
        archive_type=archive_type,
    )

    # Verify
    try:
        import subprocess

        result = subprocess.run(
            [str(target_path), "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            ver = result.stdout.strip()
            logger.info("Installed: %s", ver)
        else:
            logger.warning("Binary installed but version check failed")
    except Exception:
        pass

    return target_path


def ensure_cbm() -> Path | None:
    """Ensure codebase-memory-mcp is available. Download if needed.

    Returns path to binary, or None if download failed.
    """
    existing = get_cbm_path()
    if existing:
        return existing

    try:
        return download_cbm()
    except RuntimeError as e:
        logger.warning("Failed to install codebase-memory-mcp: %s", e)
        return None
