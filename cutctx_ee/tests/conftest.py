"""Shared pytest fixtures for cutctx_ee tests."""

import pytest


@pytest.fixture(autouse=True)
def _isolate_license_state(tmp_path, monkeypatch):
    """Isolate license database and validation cache for each test.

    The license module caches validation results in _VALIDATION_CACHE and
    _CRL_CACHE, and LicenseDB writes to ~/.cutctx/licenses.db by default.
    Without isolation, tests that interact with licensing pollute subsequent
    tests: cached answers override monkeypatches, and database state persists
    across test boundaries.

    This fixture:
    1. Redirects HOME to a temporary directory so ~/.cutctx is test-local
    2. Clears module-level caches before/after each test
    """
    # Isolate the license database to a temp directory by redirecting HOME
    # Explicit licence-DB override, not just HOME: `license_db` resolves its
    # path per call now, but relying on HOME alone would silently regress if
    # anything ever caches it again.
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
