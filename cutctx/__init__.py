"""Public CutCtx Python package alias.

This module provides a user-facing `cutctx` import path while the
implementation continues to live under the historical `headroom` package.
"""

from __future__ import annotations

import headroom as _headroom
from headroom import *  # noqa: F403
from headroom import __all__ as _HEADROOM_ALL
from headroom import __doc__ as _HEADROOM_DOC
from headroom import __version__

__all__ = list(_HEADROOM_ALL)
__doc__ = (_HEADROOM_DOC or "").replace("Headroom", "CutCtx")

_ALIASES = {
    "CutCtxClient": "HeadroomClient",
    "CutCtxConfig": "HeadroomConfig",
    "CutCtxMode": "HeadroomMode",
    "CutCtxError": "HeadroomError",
    "CutCtxTracer": "HeadroomTracer",
    "CutCtxOtelMetrics": "HeadroomOtelMetrics",
}

__all__.extend(_ALIASES.keys())


def __getattr__(name: str):
    if name in _ALIASES:
        return getattr(_headroom, _ALIASES[name])
    return getattr(_headroom, name)
