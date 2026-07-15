"""Cutctx CLI package.

Submodules are imported lazily so lightweight commands such as
`cutctx capabilities` do not fail just because an unrelated optional
command depends on an extra package.
"""

from __future__ import annotations

from importlib import import_module

_LAZY_SUBMODULES = {
    "agent_savings",
    "audit",
    "billing",
    "capabilities",
    "capture",
    "config_check",
    "evals",
    "evidence",
    "init",
    "install",
    "integrations",
    "intercept",
    "learn",
    "license",
    "mcp",
    "memory",
    "orgs",
    "perf",
    "proxy",
    "rbac",
    "report",
    "savings",
    "setup",
    "sso_test",
    "tools",
    "wrap",
}

__all__ = ["main", *_LAZY_SUBMODULES]


def __getattr__(name: str):
    if name == "main":
        from .main import main

        return main
    if name in _LAZY_SUBMODULES:
        module = import_module(f"{__name__}.{name}")
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
