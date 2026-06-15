# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Headroom Labs.
"""Import-path shim (Apache-2.0).

The implementation moved to the proprietary ``headroom_ee`` package under the
Headroom Commercial License (see LICENSING.md). This shim re-exports it at the
historical ``headroom.trial`` path so existing call sites keep working when the
commercial ``headroom_ee`` distribution is installed.
"""
from __future__ import annotations

import sys as _sys

try:
    import headroom_ee.trial as _impl
except ImportError as _e:  # commercial component not installed (community edition)
    raise ImportError(
        "headroom.trial requires the proprietary 'headroom_ee' distribution "
        "(Headroom Commercial License -- see LICENSING.md)."
    ) from _e

_sys.modules[__name__] = _impl
