"""Anti-debug and anti-dump guards for the Cutctx EE runtime.

Called once at EE import time (before any proprietary code executes).
The Rust-core path is preferred because it runs at a lower level; the
pure-Python fallback covers the case where ``headroom._core`` has not
been loaded yet (e.g., during initial install before compilation).

Usage::

    from headroom.security.antidebug import guard_ee_entry
    guard_ee_entry()   # raises RuntimeError if debugger detected
"""

from __future__ import annotations

import logging
import os
import sys
from typing import NoReturn

logger = logging.getLogger("headroom.security.antidebug")

# Environment variable that disables the guard in controlled dev environments.
# Set ``HEADROOM_ALLOW_DEBUG=1`` in pytest / profiling sessions only.
_ALLOW_DEBUG_ENV = "HEADROOM_ALLOW_DEBUG"


def _is_debug_allowed() -> bool:
    return os.environ.get(_ALLOW_DEBUG_ENV, "").strip() in ("1", "true", "yes")


# ---------------------------------------------------------------------------
# Platform-native detection (Python fallbacks, no Rust required)
# ---------------------------------------------------------------------------

def _linux_tracer_pid() -> int:
    """Read TracerPid from /proc/self/status. Returns 0 if not traced."""
    try:
        with open("/proc/self/status", encoding="ascii") as fh:
            for line in fh:
                if line.startswith("TracerPid:"):
                    return int(line.split(":", 1)[1].strip())
    except OSError:
        pass
    return 0


def _windows_is_debugged() -> bool:
    """Call IsDebuggerPresent via ctypes on Windows."""
    try:
        import ctypes
        return bool(ctypes.windll.kernel32.IsDebuggerPresent())  # type: ignore[attr-defined]
    except Exception:
        return False


def _python_fallback_is_debugged() -> bool:
    """Pure-Python debugger detection — platform-specific."""
    if sys.platform.startswith("linux"):
        return _linux_tracer_pid() != 0
    if sys.platform == "win32":
        return _windows_is_debugged()
    # macOS: no cheap pure-Python check; rely on Rust ptrace deny
    return False


# ---------------------------------------------------------------------------
# Rust-core path
# ---------------------------------------------------------------------------

def _rust_deny_attach() -> bool:
    """Call headroom._core.deny_debugger_attach() if the .so is loaded.

    Returns True if a debugger was detected (Linux/Windows).
    Returns False on success (macOS: deny-attach mode) or if Rust not loaded.
    """
    try:
        from headroom import _core  # type: ignore[import]
        return getattr(_core, "deny_debugger_attach", lambda: False)()
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def guard_ee_entry() -> None:
    """Assert that no debugger is attached before running EE code.

    Execution path:
      1. Try Rust ``_core.deny_debugger_attach()``.
         - macOS: calls ptrace(PT_DENY_ATTACH) — the process becomes
           unattachable. Returns False (no detection result).
         - Linux/Windows: returns True if debugger attached.
      2. Python fallback for Linux/Windows if Rust not available.
      3. Raise ``RuntimeError`` if debugger detected.
      4. No-op if ``HEADROOM_ALLOW_DEBUG=1`` is set.

    Raises:
        RuntimeError: A debugger is attached and ``HEADROOM_ALLOW_DEBUG``
            is not set.
    """
    if _is_debug_allowed():
        logger.debug("antidebug: HEADROOM_ALLOW_DEBUG set, skipping guard")
        return

    # Rust path (preferred)
    rust_detected = _rust_deny_attach()
    if rust_detected:
        _abort_debugger_detected()

    # Python fallback (Linux / Windows when Rust .so not yet compiled)
    py_detected = _python_fallback_is_debugged()
    if py_detected:
        _abort_debugger_detected()


def _abort_debugger_detected() -> NoReturn:
    logger.error(
        "headroom_ee: debugger detected — refusing to load proprietary modules. "
        "Set HEADROOM_ALLOW_DEBUG=1 only in approved development environments."
    )
    raise RuntimeError(
        "headroom_ee: debugger detected. "
        "Set HEADROOM_ALLOW_DEBUG=1 to allow debugging in non-production environments."
    )
