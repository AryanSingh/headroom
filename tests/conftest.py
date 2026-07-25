"""Shared pytest fixtures for Cutctx tests."""

# CRITICAL: Must be set before ANY imports that could trigger sentence_transformers
# The Rust tokenizers use parallelism that deadlocks with pytest-asyncio
import os

os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["CUTCTX_CCR_BACKEND"] = "memory"
os.environ.setdefault("CUTCTX_WEBHOOKS_IN_MEMORY", "1")
# Secure-by-default: tests need a known admin key for admin endpoints.
# The test mode bypass (CUTCTX_TEST_MODE) has been REMOVED as a security
# hardening measure. Tests authenticate via this key instead.
os.environ.setdefault("CUTCTX_ADMIN_API_KEY", "test-admin-key-for-ci")
_SUITE_DEFAULT_ADMIN_KEY = os.environ["CUTCTX_ADMIN_API_KEY"]

# Admin-gated proxy routes (added as part of the QA/product-audit security
# hardening pass) reject requests that don't carry the admin key above.
# Older tests built their TestClient before that hardening landed and don't
# send it. Rather than touch every call site, default every TestClient to
# carry it. This only applies when the suite-wide default key above is still
# in effect: a handful of test files (test_route_modules.py,
# test_dsr_endpoints.py, test_management_api_entitlements.py) monkeypatch
# CUTCTX_ADMIN_API_KEY to their own value specifically to test the
# unauthenticated-rejection path, and injecting a header there would falsely
# "authenticate" a request that's supposed to prove auth is required.
# Per-request headers (e.g. a test deliberately sending a wrong key) still
# take precedence over this client-level default either way.
try:
    from starlette.testclient import TestClient as _TestClient

    _orig_test_client_init = _TestClient.__init__

    def _test_client_init_with_admin_key(self, *args, **kwargs):
        _orig_test_client_init(self, *args, **kwargs)
        if os.environ.get("CUTCTX_ADMIN_API_KEY") == _SUITE_DEFAULT_ADMIN_KEY:
            self.headers.setdefault("x-cutctx-admin-key", _SUITE_DEFAULT_ADMIN_KEY)

    _TestClient.__init__ = _test_client_init_with_admin_key
except ImportError:
    pass


import json
import logging
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest


@pytest.fixture(autouse=True)
def _restore_runtime_state():
    """Keep per-test process state from leaking into later tests.

    The remaining QA-report failures are all cross-test contamination
    issues, so we restore the process cwd and reset the small set of
    module-level singletons that can survive past a test boundary.
    """

    cwd = Path.cwd()
    environ = os.environ.copy()
    yield

    if Path.cwd() != cwd:
        os.chdir(cwd)
    # A number of legacy tests assign directly to os.environ instead of using
    # monkeypatch. Restore the exact per-test environment so configuration,
    # database-path, and feature-flag state cannot leak into later tests.
    os.environ.clear()
    os.environ.update(environ)

    try:
        from cutctx_ee.rbac import reset_rbac_checker

        reset_rbac_checker()
    except Exception:
        pass

    try:
        import cutctx.proxy.webhooks as webhooks_module

        webhooks_module._dispatcher = None  # type: ignore[attr-defined]
    except Exception:
        pass

    try:
        import cutctx.subscription.tracker as tracker_module

        tracker_module._tracker_instance = None  # type: ignore[attr-defined]
    except Exception:
        pass

    try:
        from cutctx.proxy.intelligence_pipeline import (
            clear_runtime_flag,
            get_all_runtime_flags,
        )

        for key in get_all_runtime_flags():
            clear_runtime_flag(key)
    except Exception:
        pass

    try:
        from cutctx.proxy.circuit_breaker import reset_all_circuit_breakers

        reset_all_circuit_breakers()
    except Exception:
        pass


# KNOWN LIMITATION — cross-suite licensing tests.
#
# Running `pytest tests/ cutctx_ee/tests/` in ONE session still fails 3-4
# licensing tests (test_license_routes.py checkout-seat/start-trial, and
# test_license_validation_contract.py::test_remote_unavailability_preserves_local_fallback).
# Reproduce quickly with:
#
#   pytest tests/ cutctx_ee/tests/ -p no:randomly \
#       -k "license or seat or trial or entitlement or billing"
#
# Established so far: each suite is green on its own (tests/ 9,186 passed;
# cutctx_ee/tests 53 passed), the affected tests pass individually even with the
# EE suite collected, and CI never combines the two directories in one
# invocation (see .github/workflows/ci.yml, which runs `pytest tests`). The
# trigger is EE-suite participation rather than import order alone; the routes
# end up with a real LicenseDB despite monkeypatching
# `cutctx_ee.billing.license_db.get_license_db`. Not yet root-caused.
#
# Fixed along the way: `license_db` used to freeze its path from Path.home() at
# import time, so collection captured the developer's real ~/.cutctx/licenses.db.
# It now resolves per call and honours CUTCTX_LICENSE_DB_PATH.

#: Node-id substrings identifying tests that touch licensing state. Only these
#: get HOME redirected — see the fixture below for why that must not be global.
_LICENSE_TEST_MARKERS = ("license", "licence", "seat", "trial", "entitlement", "billing")


@pytest.fixture(autouse=True)
def _isolate_license_state(request, tmp_path, monkeypatch):
    """Isolate licensing state so tests cannot read the developer's real data.

    `LicenseDB` resolves its path from ``Path.home() / ".cutctx" /
    "licenses.db"``, and `cutctx_ee.billing.client` keeps module-level
    `_VALIDATION_CACHE` / `_CRL_CACHE` dicts. Without isolation, licensing
    tests read the developer's real ~/.cutctx/licenses.db — which is why four
    of them failed only when the OSS and EE suites shared a pytest session:
    seats had been consumed and trial tokens marked used by earlier runs.

    **HOME is redirected only for licensing tests, deliberately.** Redirecting
    it for every test moved the HuggingFace/fastembed model caches (which live
    under HOME) to a fresh tmp_path per test, forcing model re-initialisation
    and pushing the suite from ~7.5 minutes past a 10-minute timeout. Cache
    clearing is cheap, so that part stays global; the expensive part is scoped.
    """
    if any(marker in request.node.nodeid.lower() for marker in _LICENSE_TEST_MARKERS):
        # Point the licence DB at a per-test file explicitly. Redirecting HOME
        # alone is not sufficient: `license_db` used to freeze its path from
        # Path.home() at import time, so a module imported during collection
        # captured the real home directory before any fixture ran.
        monkeypatch.setenv("CUTCTX_LICENSE_DB_PATH", str(tmp_path / "licenses.db"))
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("CUTCTX_HOME", str(tmp_path / ".cutctx"))

    # Clear the module-level license caches to prevent cross-test pollution
    try:
        from cutctx_ee.billing import client

        client._VALIDATION_CACHE.clear()
        client._CRL_CACHE.clear()
        client._CRL_CACHE["revoked"] = set()
        client._CRL_CACHE["expires_at"] = 0.0
    except Exception:
        pass

    yield

    # Clean up after the test
    try:
        from cutctx_ee.billing import client

        client._VALIDATION_CACHE.clear()
        client._CRL_CACHE.clear()
        client._CRL_CACHE["revoked"] = set()
        client._CRL_CACHE["expires_at"] = 0.0
    except Exception:
        pass


@pytest.fixture(autouse=True)
def _cleanup_cutctx_logger():
    """Restore cutctx logger propagation and remove file handlers after
    every test.

    Several proxy lifecycle paths call ``_setup_file_logging()`` which
    sets ``cutctx_logger.propagate = False`` and adds a
    ``RotatingFileHandler``. This prevents caplog from capturing
    ``cutctx.*`` log records (caplog attaches handlers to the root
    logger). This fixture ensures clean logger state for every test.
    """
    yield
    cutctx_logger = logging.getLogger("cutctx")
    cutctx_logger.propagate = True
    for handler in list(cutctx_logger.handlers):
        if "RotatingFile" in type(handler).__name__:
            cutctx_logger.removeHandler(handler)
            handler.close()


# ---------------------------------------------------------------------------
# Playwright browser availability guard
#
# The browser-based dashboard/docs tests use ``pytest.importorskip`` to skip
# when the *playwright package* is missing — but that does not cover the far
# more common case where the package is installed yet the browser binary is
# not (fresh checkout, CI without `playwright install`, contributor machines).
# There ``chromium.launch()`` raises a hard error and the whole test turns red
# for a purely environmental reason. This hook detects the browser binary once
# and, when absent, converts those failures into explicit skips. Where the
# browser IS installed, the tests run normally and full coverage is preserved.
# ---------------------------------------------------------------------------
import functools as _functools  # noqa: E402
import os as _os  # noqa: E402
import types as _types  # noqa: E402

import pytest as _pytest  # noqa: E402


@_functools.lru_cache(maxsize=1)
def _chromium_browser_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return False
    try:
        with sync_playwright() as pw:
            path = pw.chromium.executable_path
        return bool(path) and _os.path.exists(path)
    except Exception:
        return False


def _module_uses_playwright(module: object) -> bool:
    """True if a test module bound the playwright package at import time.

    Every browser test does ``x = pytest.importorskip("playwright.sync_api")``,
    binding the playwright module under some name; detect that regardless of
    the chosen variable name.
    """
    for value in vars(module).values():
        if isinstance(value, _types.ModuleType) and getattr(value, "__name__", "").startswith(
            "playwright"
        ):
            return True
    return False


def pytest_collection_modifyitems(config, items):
    if _chromium_browser_available():
        return
    skip_no_browser = _pytest.mark.skip(
        reason="Playwright chromium browser not installed; run `playwright install chromium`"
    )
    for item in items:
        module = getattr(item, "module", None)
        if module is not None and _module_uses_playwright(module):
            item.add_marker(skip_no_browser)
