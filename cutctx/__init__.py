"""Public CutCtx Python package alias.

This module provides a user-facing `cutctx` import path while the
implementation continues to live under the historical `headroom` package.
"""

from __future__ import annotations

import sys
from importlib import import_module

import headroom as _headroom
from headroom import *  # noqa: F403
from headroom import __all__ as _HEADROOM_ALL
from headroom import __doc__ as _HEADROOM_DOC
from headroom import __version__ as _HEADROOM_VERSION

__all__ = list(_HEADROOM_ALL)
__all__.append("__version__")
__doc__ = (_HEADROOM_DOC or "").replace("Cutctx", "CutCtx")
__version__ = _HEADROOM_VERSION

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


_PUBLIC_SUBMODULES = (
    "audit",
    "billing",
    "cache",
    "ccr",
    "client",
    "cli",
    "compress",
    "config",
    "entitlements",
    "evals",
    "exceptions",
    "hooks",
    "image",
    "install",
    "integrations",
    "learn",
    "memory",
    "mcp_registry",
    "models",
    "observability",
    "org",
    "paths",
    "pipeline",
    "profiles",
    "providers",
    "proxy",
    "rbac",
    "relevance",
    "reporting",
    "security",
    "seats",
    "shared_context",
    "sso",
    "storage",
    "telemetry",
    "tokenizer",
    "transforms",
    "utils",
)

for _submodule in _PUBLIC_SUBMODULES:
    try:
        _module = import_module(f"headroom.{_submodule}")
    except Exception:
        continue
    sys.modules[f"{__name__}.{_submodule}"] = _module
    globals()[_submodule] = _module
