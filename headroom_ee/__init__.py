# SPDX-License-Identifier: LicenseRef-Headroom-Commercial
# Copyright (c) 2025-2026 Cutctx Labs. All rights reserved.
# Proprietary and confidential. NOT licensed under Apache-2.0.
# See headroom_ee/LICENSE (Cutctx Commercial License) and ../LICENSING.md.
"""headroom_ee — Cutctx commercial ("enterprise edition") components.

This package holds the proprietary, All-Rights-Reserved implementations that back
the entitlement-gated features exposed through the open-source ``headroom`` client.
It is a SEPARATE distribution from the Apache-2.0 ``headroom`` package and is
governed by the Cutctx Commercial License (``headroom_ee/LICENSE``).

The open-source ``headroom.<module>`` import paths are thin Apache-2.0 shims that
re-export the implementations here when this commercial distribution is installed.
See ``../LICENSING.md`` for the authoritative open-core boundary.

Do not redistribute.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Security guards — MUST run before any EE module is executed.
#
#  1. Anti-debug: deny debugger attachment (macOS ptrace PT_DENY_ATTACH) or
#     abort if a debugger is already attached (Linux / Windows).
#  2. Integrity: verify SHA-256 hashes of all compiled .so modules against
#     the signed MANIFEST.sha256.json to detect tampered binaries.
# ---------------------------------------------------------------------------

def _run_security_guards() -> None:
    """Execute all EE entry guards. Failures raise RuntimeError / IntegrityError."""
    import logging
    _log = logging.getLogger("headroom_ee")

    # Guard 1: anti-debug
    try:
        from headroom.security.antidebug import guard_ee_entry
        guard_ee_entry()
    except ImportError:
        _log.debug("headroom.security.antidebug not available — skipping anti-debug guard")

    # Guard 2: binary integrity
    try:
        from headroom.security.integrity import verify_ee_manifest
        verify_ee_manifest(strict=True)
    except ImportError:
        _log.debug("headroom.security.integrity not available — skipping integrity check")


_run_security_guards()

# ---------------------------------------------------------------------------

__all__: list[str] = []
__license__ = "LicenseRef-Headroom-Commercial"
