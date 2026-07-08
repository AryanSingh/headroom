"""Shared pytest fixtures for Cutctx tests."""

# CRITICAL: Must be set before ANY imports that could trigger sentence_transformers
# The Rust tokenizers use parallelism that deadlocks with pytest-asyncio
import os

os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["CUTCTX_CCR_BACKEND"] = "memory"
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

import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock


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

