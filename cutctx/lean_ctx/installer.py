"""Download and install lean-ctx binary from GitHub releases."""

from __future__ import annotations

import logging
import os
import platform
import subprocess
from pathlib import Path
from typing import Literal
from urllib.request import urlopen

from cutctx.install.binary_archive import install_verified_archive

from . import LEAN_CTX_BIN_DIR, LEAN_CTX_VERSION

logger = logging.getLogger(__name__)

GITHUB_RELEASE_URL = "https://github.com/yvgude/lean-ctx/releases/download"

_PINNED_ARCHIVE_SHA256 = {
    ("v3.4.7", "aarch64-apple-darwin"): "c4db95966f80ab47aadfca296d0f95937085cf601833f0288eeec8b9f02872cd",
    ("v3.4.7", "aarch64-unknown-linux-gnu"): "72435a42bb33afc3d3cd5a62426955c6488192826a3a84d57e26f587740534d9",
    ("v3.4.7", "aarch64-unknown-linux-musl"): "be68c45ebb19e30ae6fc4713ec56f148ef2dfa08669b2db4abe57706e625c0e8",
    ("v3.4.7", "x86_64-apple-darwin"): "9d55d9ed24d3b3726c16eea3cc16255538f286a880531b7fa90e7fb00361e2e2",
    ("v3.4.7", "x86_64-pc-windows-msvc"): "57ff7ff936228828ffc94e0803e1727c5ad03d92791283614406b7e4f66706b0",
    ("v3.4.7", "x86_64-unknown-linux-gnu"): "ec405e643a4c4cb3e7fdd2818801f11a6d0209cbcfe0ce085df1d62335a5053b",
    ("v3.4.7", "x86_64-unknown-linux-musl"): "d2cb70294044a04edc32b7bb9ba2e81f826c042db4840226058d2bd4941e0034",
}


def _expected_archive_sha256(version: str, target: str) -> str:
    override = os.environ.get("CUTCTX_LEAN_CTX_SHA256", "").strip().lower()
    expected = override or _PINNED_ARCHIVE_SHA256.get((version, target), "")
    if not expected:
        raise RuntimeError(
            "No pinned SHA-256 is available for this lean-ctx version/target; "
            "set CUTCTX_LEAN_CTX_SHA256 to the trusted release digest"
        )
    return expected


def _detect_runtime_target_triple() -> str:
    """Detect platform and return the lean-ctx release target triple."""
    system = platform.system()
    machine = platform.machine()

    if system == "Darwin":
        arch = "aarch64" if machine == "arm64" else "x86_64"
        return f"{arch}-apple-darwin"
    if system == "Linux":
        arch = "aarch64" if machine == "aarch64" else "x86_64"
        suffix = "unknown-linux-musl" if _is_musl() else "unknown-linux-gnu"
        return f"{arch}-{suffix}"
    if system == "Windows":
        return "x86_64-pc-windows-msvc"

    raise RuntimeError(f"Unsupported platform: {system} {machine}")


def _is_musl() -> bool:
    try:
        result = subprocess.run(
            ["ldd", "--version"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        return "musl" in (result.stdout + result.stderr).lower()
    except Exception:
        return False


def _get_target_triple() -> str:
    """Return the requested lean-ctx target triple, honoring explicit overrides."""
    return _get_explicit_target_triple() or _detect_runtime_target_triple()


def _get_explicit_target_triple() -> str:
    """Return the explicitly requested lean-ctx target triple, if any."""
    return (
        os.environ.get("CUTCTX_LEAN_CTX_TARGET", "").strip()
        or os.environ.get("LEAN_CTX_TARGET", "").strip()
    )


def _binary_name_for_target(target: str) -> str:
    """Return the expected binary name for a target triple."""
    return "lean-ctx.exe" if "windows" in target else "lean-ctx"


def _should_verify_target(target: str) -> bool:
    """Verify runtime-detected targets; explicit overrides may be cross-target."""
    if _get_explicit_target_triple():
        return False
    return target == _detect_runtime_target_triple()


def _get_download_url(version: str) -> tuple[str, Literal["tar.gz", "zip"]]:
    """Get download URL and extension for this platform."""
    target = _get_target_triple()
    ext: Literal["tar.gz", "zip"] = "zip" if "windows" in target else "tar.gz"
    url = f"{GITHUB_RELEASE_URL}/{version}/lean-ctx-{target}.{ext}"
    return url, ext


def download_lean_ctx(version: str | None = None) -> Path:
    """Download lean-ctx binary from GitHub releases."""
    version = version or LEAN_CTX_VERSION
    target = _get_target_triple()
    url, ext = _get_download_url(version)
    target_path = LEAN_CTX_BIN_DIR / _binary_name_for_target(target)

    LEAN_CTX_BIN_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("Downloading lean-ctx %s from %s ...", version, url)

    try:
        if not url.startswith(("http://", "https://")):
            raise ValueError(f"Invalid URL scheme in {url}")
        try:
            with urlopen(url, timeout=30) as response:
                data = response.read()
        except Exception as download_err:
            if "CERTIFICATE_VERIFY_FAILED" in str(download_err):
                raise RuntimeError(
                    "TLS verification failed downloading lean-ctx; "
                    "fix the local trust store and retry."
                ) from download_err
            raise
    except Exception as e:
        raise RuntimeError(f"Failed to download lean-ctx from {url}: {e}") from e

    install_verified_archive(
        data,
        expected_sha256=_expected_archive_sha256(version, target),
        target_path=target_path,
        archive_type=ext,
    )

    if _should_verify_target(target):
        try:
            result = subprocess.run(
                [str(target_path), "--version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
            )
            if result.returncode != 0:
                raise RuntimeError(f"lean-ctx verification failed: {result.stderr}")
            logger.info("lean-ctx installed: %s", result.stdout.strip())
        except FileNotFoundError as e:
            raise RuntimeError("lean-ctx binary not found after extraction") from e
        except subprocess.TimeoutExpired as e:
            raise RuntimeError("lean-ctx verification timed out") from e
    else:
        logger.info(
            "lean-ctx installed for target %s at %s (verification skipped)",
            target,
            target_path,
        )

    return target_path


def ensure_lean_ctx(version: str | None = None) -> Path | None:
    """Ensure lean-ctx is installed — download if needed."""
    from . import get_lean_ctx_path

    existing = get_lean_ctx_path()
    if existing:
        return existing

    try:
        return download_lean_ctx(version)
    except RuntimeError as e:
        logger.warning("Could not install lean-ctx: %s", e)
        return None
