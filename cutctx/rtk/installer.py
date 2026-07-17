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
        version: Version to download (e.g., "v0.43.0"). Defaults to pinned version.

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
    from . import get_rtk_path, get_rtk_version

    existing = get_rtk_path()
    if existing:
        installed_version = get_rtk_version(existing)
        if installed_version and installed_version != RTK_VERSION:
            logger.warning(
                "Using system rtk %s at %s; managed installer pin is %s",
                installed_version,
                existing,
                RTK_VERSION,
            )
        return existing

    try:
        return download_rtk(version)
    except RuntimeError as e:
        logger.warning("Could not install rtk: %s", e)
        return None
