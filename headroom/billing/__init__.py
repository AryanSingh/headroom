# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Headroom Labs.
"""Import-path shim (Apache-2.0).

The billing package implementation moved to the proprietary ``headroom_ee`` package
under the Headroom Commercial License (see LICENSING.md). This shim re-exports it at
the historical ``headroom.billing`` import path — including submodules such as
``headroom.billing.license_db`` and ``headroom.billing.stripe_webhook`` — so existing
call sites keep working when the commercial ``headroom_ee`` distribution is installed.

Rebinding this package to ``headroom_ee.billing`` repoints its ``__path__`` at the
commercial package, so ``from headroom.billing.license_db import ...`` resolves to
the implementation under ``headroom_ee/billing/``.
"""

from __future__ import annotations

import sys as _sys

try:
    import headroom_ee.billing as _impl
except ImportError as _e:  # commercial component not installed (community edition)
    raise ImportError(
        "headroom.billing requires the proprietary 'headroom_ee' distribution "
        "(Headroom Commercial License -- see LICENSING.md)."
    ) from _e

_sys.modules[__name__] = _impl
