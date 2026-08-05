# SPDX-License-Identifier: LicenseRef-Cutctx-Commercial
# Copyright (c) 2025-2026 Cutctx Labs. All rights reserved.
# Proprietary and confidential. NOT licensed under Apache-2.0.
# See cutctx_ee/LICENSE (Cutctx Commercial License) and ../LICENSING.md.
"""cutctx_ee — Cutctx commercial ("enterprise edition") components.

This package holds the proprietary, All-Rights-Reserved implementations that back
the entitlement-gated features exposed through the open-source ``cutctx`` client.
It is a SEPARATE distribution from the Apache-2.0 ``cutctx`` package and is
governed by the Cutctx Commercial License (``cutctx_ee/LICENSE``).

The open-source ``cutctx.<module>`` import paths are thin Apache-2.0 shims that
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

    _log = logging.getLogger("cutctx_ee")

    # Guard 1: anti-debug
    try:
        from cutctx.security.antidebug import guard_ee_entry

        guard_ee_entry()
    except ImportError:
        _log.debug("cutctx.security.antidebug not available — skipping anti-debug guard")

    # Guard 2: binary integrity.
    #
    # Audit-2026-08-03 H2: this passed strict=False, so a hash mismatch only
    # logged "Refusing to load EE modules" and then returned — the tampered
    # module imported and ran anyway, contradicting this module's own
    # docstring. It is enforcing now; ``IntegrityError`` propagates out of
    # ``import cutctx_ee`` and aborts loading, which is what the docstring
    # always claimed. This is only safe because H1 removed the permanent
    # false alarm (stale binaries + a git-tracked manifest that could never
    # match a local build). ``CUTCTX_SKIP_INTEGRITY_CHECK=1`` remains the
    # documented emergency escape hatch.
    try:
        from cutctx.security.integrity import verify_ee_manifest
    except ImportError:
        _log.debug("cutctx.security.integrity not available — skipping integrity check")
    else:
        verify_ee_manifest(strict=True)


_run_security_guards()

# ---------------------------------------------------------------------------

__all__: list[str] = []
__license__ = "LicenseRef-Cutctx-Commercial"
