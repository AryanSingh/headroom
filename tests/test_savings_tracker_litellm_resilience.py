# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""Regression test for cutctx.proxy.savings_tracker._get_litellm_module.

2026-07-03 incident: this helper only caught ImportError around
`import litellm`, but litellm's own internal circular-import bug surfaces
as AttributeError ("partially initialized module 'litellm' has no
attribute 'litellm_core_utils'"), not ImportError. That let the exception
propagate out of this best-effort, optional cost-estimation path, all the
way up through record_request/emit_request_outcome, and crash the entire
proxy process on essentially any live request that needed a USD estimate.

The fix (broadening to `except Exception`) was reverted once already by a
concurrent edit on the same file during the incident, before the proxy had
even been confirmed stable — hence this test, so any future narrowing of
the exception type fails the suite instead of silently reintroducing a
proxy-crashing bug.
"""

from __future__ import annotations

import sys
from types import ModuleType

import pytest

from cutctx.proxy import savings_tracker


@pytest.fixture(autouse=True)
def _reset_litellm_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate each test from the module-level litellm cache/availability."""
    monkeypatch.setattr(savings_tracker, "litellm", None)
    monkeypatch.setattr(savings_tracker, "LITELLM_AVAILABLE", True)


def test_get_litellm_module_survives_attribute_error_during_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A circular-import AttributeError during `import litellm` must not
    escape _get_litellm_module — it must be caught and return None, exactly
    like a plain ImportError would."""

    real_import = __import__

    def _fake_import(name, *args, **kwargs):
        if name == "litellm" or name.startswith("litellm."):
            raise AttributeError(
                "partially initialized module 'litellm' has no attribute "
                "'litellm_core_utils' (most likely due to a circular import)"
            )
        return real_import(name, *args, **kwargs)

    monkeypatch.setitem(sys.modules, "litellm", None)
    monkeypatch.delitem(sys.modules, "litellm", raising=False)
    monkeypatch.setattr("builtins.__import__", _fake_import)

    result = savings_tracker._get_litellm_module()

    assert result is None


def test_get_litellm_module_survives_plain_import_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The original, narrower failure mode must still degrade gracefully too."""

    real_import = __import__

    def _fake_import(name, *args, **kwargs):
        if name == "litellm" or name.startswith("litellm."):
            raise ImportError("No module named 'litellm'")
        return real_import(name, *args, **kwargs)

    monkeypatch.delitem(sys.modules, "litellm", raising=False)
    monkeypatch.setattr("builtins.__import__", _fake_import)

    result = savings_tracker._get_litellm_module()

    assert result is None


def test_get_litellm_module_returns_module_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A healthy import still returns the real module, not None."""

    fake_litellm = ModuleType("litellm")
    monkeypatch.setitem(sys.modules, "litellm", fake_litellm)

    result = savings_tracker._get_litellm_module()

    assert result is fake_litellm


def test_estimate_compression_savings_usd_never_raises_on_broken_litellm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: the actual cost-estimation call site used from
    record_request must degrade to 0.0, not propagate, when litellm is
    unusable for any reason."""

    def _broken_get_litellm_module():
        return None

    monkeypatch.setattr(savings_tracker, "_get_litellm_module", _broken_get_litellm_module)

    result = savings_tracker._estimate_compression_savings_usd("gpt-5.4", 1000)

    assert result == 0.0
