# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""Import-path shim (Apache-2.0).

The implementation moved to the proprietary ``headroom_ee`` package under the
Cutctx Commercial License (see LICENSING.md). This shim re-exports it at the
historical ``headroom.trial`` path so existing call sites keep working when the
commercial ``headroom_ee`` distribution is installed.
"""

from __future__ import annotations

import sys as _sys
from typing import TYPE_CHECKING

try:
    import headroom_ee.trial as _impl
except ImportError as _e:  # commercial component not installed (community edition)
    raise ImportError(
        "headroom.trial requires the proprietary 'headroom_ee' distribution "
        "(Cutctx Commercial License -- see LICENSING.md)."
    ) from _e

_sys.modules[__name__] = _impl  # type: ignore[assignment]

if TYPE_CHECKING:
    # Re-export the public API for static type-checkers (mypy/IDEs). At runtime the
    # sys.modules rebind above makes `from headroom.trial import X` resolve to
    # headroom_ee.trial; this makes the same names visible to static analysis.
    from headroom_ee.trial import *  # noqa: F401,F403
