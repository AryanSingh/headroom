"""Download and install rtk binary from GitHub releases."""

from __future__ import annotations

import logging
import os
import platform
import subprocess
from pathlib import Path
from typing import Literal
from urllib.request import urlopen

from cutctx.install.binary_archive import install_verified_archive

from . import RTK_BIN_DIR, RTK_BIN_PATH, RTK_VERSION

logger = logging.getLogger(__name__)

GITHUB_RELEASE_URL = "https://github.com/rtk-ai/rtk/releases/download"

_PINNED_ARCHIVE_SHA256 = {
    ("v0.28.2", "aarch64-apple-darwin"): "5dede8ac36648960a3ad52611856b9047a7817b755750d2bdbda8d4e9931db4d",
    ("v0.28.2", "aarch64-unknown-linux-gnu"): "9dbf6dd22cfdf8b85b916505a5e96e1721d7af4cbe2f3dc90b87c9d677d01636",
    ("v0.28.2", "x86_64-apple-darwin"): "5ce5dab3b744a6ecce7ff9deea9fd4606f72c6490c9ee447d74883d9393dcbc7",
    ("v0.28.2", "x86_64-pc-windows-msvc"): "8bd4ae58b8657f9afd82c76f28e06232b0e8f994e949176206425dcc6005936a",
    ("v0.28.2", "x86_64-unknown-linux-musl"): "c7b61e87b8430e42b04ab84fbe1b3b41b563454b0181247fd04844b8e9194371",
}


def _expected_archive_sha256(version: str, target: str) -> str:
    override = os.environ.get("CUTCTX_RTK_SHA256", "").strip().lower()
    expected = override or _PINNED_ARCHIVE_SHA256.get((version, target), "")
    if not expected:
        raise RuntimeError(
            "No pinned SHA-256 is available for this rtk version/target; "
            "set CUTCTX_RTK_SHA256 to the trusted release digest"
        )
    return expected


def _detect_runtime_target_triple() -> str:
    """Detect platform and return the rtk release target triple."""
    system = platform.system()
    machine = platform.machine()

    if system == "Darwin":
        arch = "aarch64" if machine == "arm64" else "x86_64"
        return f"{arch}-apple-darwin"
    elif system == "Linux":
        arch = "aarch64" if machine == "aarch64" else "x86_64"
        suffix = "unknown-linux-gnu" if arch == "aarch64" else "unknown-linux-musl"
        return f"{arch}-{suffix}"
    elif system == "Windows":
        return "x86_64-pc-windows-msvc"

    raise RuntimeError(f"Unsupported platform: {system} {machine}")


def _get_target_triple() -> str:
    """Return the requested rtk target triple, honoring explicit overrides."""
    return os.environ.get("CUTCTX_RTK_TARGET", "").strip() or _detect_runtime_target_triple()


def _binary_name_for_target(target: str) -> str:
    """Return the expected binary name for a target triple."""
    return "rtk.exe" if "windows" in target else "rtk"


def _should_verify_target(target: str) -> bool:
    """Verify only when the requested target matches the current runtime."""
    return target == _detect_runtime_target_triple()


def _get_download_url(version: str) -> tuple[str, Literal["tar.gz", "zip"]]:
    """Get download URL and extension for this platform.

    Returns (url, extension) where extension is 'tar.gz' or 'zip'.
    """
    target = _get_target_triple()

    if "windows" in target:
        ext: Literal["tar.gz", "zip"] = "zip"
    else:
        ext = "tar.gz"

    url = f"{GITHUB_RELEASE_URL}/{version}/rtk-{target}.{ext}"
    return url, ext


def download_rtk(version: str | None = None) -> Path:
    """Download rtk binary from GitHub releases.

    Args:
        version: Version to download (e.g., "v0.28.2"). Defaults to pinned version.

    Returns:
        Path to the installed binary.

    Raises:
        RuntimeError: If download or extraction fails.
    """
    version = version or RTK_VERSION
    target = _get_target_triple()
    url, ext = _get_download_url(version)
    target_path = RTK_BIN_DIR / _binary_name_for_target(target)

    RTK_BIN_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("Downloading rtk %s from %s ...", version, url)

    try:
        # Validate URL scheme to prevent B310 warning
        if not url.startswith(("http://", "https://")):
            raise ValueError(f"Invalid URL scheme in {url}")

        # Fail closed on TLS errors rather than executing an unverifiable download.
        try:
            with urlopen(url, timeout=30) as response:
                data = response.read()
        except Exception as download_err:
            if "CERTIFICATE_VERIFY_FAILED" in str(download_err):
                raise RuntimeError(
                    "TLS verification failed downloading rtk; fix the local trust store and retry."
                ) from download_err
            raise
    except Exception as e:
        raise RuntimeError(f"Failed to download rtk from {url}: {e}") from e

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
                raise RuntimeError(f"rtk verification failed: {result.stderr}")
            logger.info("rtk installed: %s", result.stdout.strip())
        except FileNotFoundError as e:
            raise RuntimeError("rtk binary not found after extraction") from e
        except subprocess.TimeoutExpired as e:
            raise RuntimeError("rtk verification timed out") from e
    else:
        logger.info("rtk installed for target %s at %s (verification skipped)", target, target_path)

    return target_path


def register_claude_hooks(rtk_path: Path | None = None) -> bool:
    """Register rtk hooks in Claude Code settings.

    Runs `rtk init --global` which adds a PreToolUse hook to
    ~/.claude/settings.json that rewrites Bash commands through rtk.

    Returns True if hooks were registered successfully.
    """
    rtk_path = rtk_path or RTK_BIN_PATH

    try:
        result = subprocess.run(
            [str(rtk_path), "init", "--global", "--auto-patch"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        if result.returncode == 0:
            logger.info("rtk hooks registered in Claude Code")
            return True
        else:
            logger.warning("rtk init failed: %s", result.stderr)
            return False
    except Exception as e:
        logger.warning("Failed to register rtk hooks: %s", e)
        return False


def ensure_rtk(version: str | None = None) -> Path | None:
    """Ensure rtk is installed — download if needed.

    Returns path to rtk binary, or None if installation failed.
    """
    from . import get_rtk_path

    existing = get_rtk_path()
    if existing:
        return existing

    try:
        return download_rtk(version)
    except RuntimeError as e:
        logger.warning("Could not install rtk: %s", e)
        return None
